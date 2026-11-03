from copy import deepcopy
import json
from pathlib import Path

import pytest

from manimind.components import pipeline as pipe
from manimind.postproduce import pilot

FIXTURE = Path(__file__).parents[1] / "configs/component-foundation.json"


def test_init_no_overwrite_and_input_mutation_invalidates(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    project = pipe.init(FIXTURE)
    out, context, session = pipe.paths(project)
    assert pipe.frozen_plan(project)["provenance"]["kind"] == "engineering_fixture"
    assert pilot.read_json(context / "component-plan.json")["is_model_benchmark"] is False
    assert pilot.read_json(session / "events.json")["events"][0]["status"] == "validated"
    with pytest.raises(ValueError, match="already exists"):
        pipe.init(FIXTURE)
    value = pilot.read_json(out / "plan.json")
    value["title"] = "Changed input"
    pilot.write_json(out / "plan.json", value)
    with pytest.raises(ValueError, match="modified"):
        pipe.frozen_plan(project)


def test_lock_is_exclusive_and_released_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    with pytest.raises(RuntimeError):
        with pipe.command_lock("test"):
            with pytest.raises(FileExistsError):
                with pipe.command_lock("test"):
                    pass
            raise RuntimeError("test")
    assert not (pipe.paths("test")[2] / "command.lock").exists()


def audit():
    return {"complete": True, "frames_checked": 4, "issues": [], "frames": [
        {"frame": 1, "shot": "a", "fraction": .5, "issues": []},
        {"frame": 2, "shot": "a", "fraction": 1., "issues": []},
        {"frame": 3, "shot": "b", "fraction": .5, "issues": []},
        {"frame": 4, "shot": "b", "fraction": 1., "issues": []}]}


def test_audit_requires_full_coverage_and_each_terminal_state():
    pipe.validate_audit(audit(), 4, ["a", "b"])
    for mutate in [lambda a: a.update(issues=["collision"]), lambda a: a["frames"].pop(),
                   lambda a: a["frames"][1].update(fraction=.8),
                   lambda a: a["frames"][1].update(frame=1),
                   lambda a: a["frames"][1].update(issues=["mismatch"]),
                   lambda a: a["frames"][1].update(shot="other"),
                   lambda a: a.update(complete=False),
                   lambda a: a["frames"][1].update(fraction=float("nan")),
                   lambda a: a["frames"].reverse(),
                   lambda a: a["frames"].append({"frame": 5, "shot": "a", "fraction": 1})]:
        value = audit()
        mutate(value)
        with pytest.raises(ValueError):
            pipe.validate_audit(value, 4, ["a", "b"])


def setup_review(tmp_path, monkeypatch):
    monkeypatch.setattr(pipe, "ROOT", tmp_path)
    project, attempt = "test", 1
    out, context, session = pipe.paths(project)
    folder = pipe.attempt_dir(project, attempt)
    first, second = folder / "one.jpg", folder / "two.jpg"
    folder.mkdir(parents=True)
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    frames = [{"shot": name, "path": str(path), "sha256": pilot.sha256(path)}
              for name, path in [("a", first), ("b", second)]]
    video = folder / "render.mp4"
    video.write_bytes(b"rendered video")
    pilot.write_json(folder / "review-input.json", {"hashes": {"video": "v1"}, "frames": frames,
                     "video_path": str(folder / "untrusted-alternate.mp4"), "duration": 1, "resolution": [1920, 1080]})
    pilot.write_json(folder / "render.json", {"preflight": {"total_frames": 4}, "video_path": str(video)})
    pilot.write_json(session / "events.json", {"events": []})
    pilot.write_json(folder / "frame-audit.json", audit())
    review = {"reviewer_role": "reviewer", "reviewer_id": "independent", "status": "approved",
              "blockers": [], "hashes": {"video": "v1"}, "inspected_frames": [str(first), str(second)],
              "reviewed_input_sha256": pilot.sha256(folder / "review-input.json"),
              "checks": dict.fromkeys(["mathematics", "visual_layout", "narrative", "cue_timing"], "pass")}
    pilot.write_json(context / "review-001.json", review)
    monkeypatch.setattr(pipe, "evidence_hashes", lambda *args: {"video": "v1"})
    monkeypatch.setattr(pipe, "frozen_plan", lambda *args: {"provenance": {"author": "producer"}, "shots": [{"id": "a"}, {"id": "b"}]})
    monkeypatch.setattr(pilot, "run", lambda *a, **kw: pytest.fail("Should not publish"))
    return project, context, review


@pytest.mark.parametrize("change", [
    lambda r: r.update(status="blocked"),
    lambda r: r.update(blockers=["math_error"]),
    lambda r: r.update(reviewer_id="producer"),
    lambda r: r.update(reviewer_role="lead"),
    lambda r: r.update(hashes={"video": "old"}),
    lambda r: r["inspected_frames"].pop(),
    lambda r: r.update(checks={}),
])
def test_publication_review_gate(tmp_path, monkeypatch, change):
    project, context, review = setup_review(tmp_path, monkeypatch)
    change(review)
    pilot.write_json(context / "review-001.json", review)
    with pytest.raises(ValueError):
        pipe.publish(project, 1)


def test_changed_frame_invalidates_review(tmp_path, monkeypatch):
    project, context, review = setup_review(tmp_path, monkeypatch)
    Path(review["inspected_frames"][0]).write_bytes(b"modified")
    with pytest.raises(ValueError, match="changed"):
        pipe.publish(project, 1)


def test_successful_publication_uses_rendered_media_and_is_immutable(tmp_path, monkeypatch):
    project, context, review = setup_review(tmp_path, monkeypatch)
    monkeypatch.setattr(pilot, "run", lambda *a, **kw: None)
    published = Path(pipe.publish(project, 1))
    assert published.read_bytes() == b"rendered video"
    delivery = pilot.read_json(published.parent / "delivery-001.json")
    assert delivery["pipeline_llm_requests"] == 0
    assert delivery["audio"] is False
    assert delivery["review_sha256"] == pilot.sha256(context / "review-001.json")
    with pytest.raises(ValueError, match="immutable"):
        pipe.publish(project, 1)


@pytest.mark.parametrize("field", ["shot", "time", "path", "sha256"])
def test_frame_manifest_mutation_cannot_reuse_approval(tmp_path, monkeypatch, field):
    project, context, review = setup_review(tmp_path, monkeypatch)
    path = pipe.attempt_dir(project, 1) / "review-input.json"
    evidence = pilot.read_json(path)
    evidence["frames"][0][field] = "replaced"
    pilot.write_json(path, evidence)
    with pytest.raises(ValueError, match="Review input changed"):
        pipe.publish(project, 1)


def test_replacing_frame_and_updating_manifest_hash_still_invalidates_approval(tmp_path, monkeypatch):
    project, context, review = setup_review(tmp_path, monkeypatch)
    path = pipe.attempt_dir(project, 1) / "review-input.json"
    evidence = pilot.read_json(path)
    image = Path(evidence["frames"][0]["path"])
    image.write_bytes(b"substituted image")
    evidence["frames"][0]["sha256"] = pilot.sha256(image)
    pilot.write_json(path, evidence)
    with pytest.raises(ValueError, match="Review input changed"):
        pipe.publish(project, 1)
