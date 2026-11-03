from types import SimpleNamespace

import pytest

from manimind.experiments import freeform_review_cycle
from manimind.experiments import sol_learning_v3 as module
from manimind.postproduce import pilot
from manimind.review.learning_quality import DIMENSIONS


@pytest.fixture
def value(tmp_path, monkeypatch):
    monkeypatch.setattr(freeform_review_cycle, "ROOT", tmp_path)
    item = module.SolLearningV3.__new__(module.SolLearningV3)
    item.id = "test-v3"
    item.out = tmp_path / "out"
    item.session = tmp_path / "session"
    item.spec_path = item.out / "spec.json"
    item.config = {"workflow_profile": str(pilot.ROOT / "configs/learning-workflow-v3.json")}
    item.team = {"actors": {"creator": {"observed": []}}}
    item.review_session.mkdir(parents=True)
    pilot.write_json(item.out / "timeline.json", {"duration": 30, "cues": [{"id": name, "start": i * 10, "duration": 10} for i, name in enumerate("abc")]})
    return item


def test_many_cues_keep_every_image_without_fake_observation(value, monkeypatch):
    batches = []

    def inspect(self, ids, state):
        batches.append(ids)
        state.update(images=[f"{i}.jpg" for i in ids], pending_cues=ids)
        return [{"cue": {"id": i}} for i in ids]

    monkeypatch.setattr(module.SolLearningV2, "inspect_segments", inspect)
    state = {}
    result = value.dispatch_role("creator", {"action": "inspect_segments", "args": {"ids": list("abc")}}, state)
    assert batches == [["a", "b"], ["c"]]
    assert len(result) == 3 and state["images"] == ["a.jpg", "b.jpg", "c.jpg"]
    assert value.team["actors"]["creator"]["pending_cues"] == list("abc")
    assert value.team["actors"]["creator"]["observed"] == []


@pytest.mark.parametrize("ids", [[], ["a", "a"], ["other"], [1]])
def test_bad_or_foreign_cues_are_rejected(value, ids):
    with pytest.raises(ValueError, match="current cue"):
        value.inspect_segments(ids, {})


def test_api_queries_are_batched_locally_not_extra_model_calls(value, monkeypatch):
    calls = []
    monkeypatch.setattr(module, "api_reference", lambda names: calls.append(names) or [{"symbol": n} for n in names])
    names = [f"Class{i}" for i in range(9)]
    result = value.dispatch_role("creator", {"action": "read_api", "args": {"symbols": names}}, {})
    assert [len(c) for c in calls] == [4, 4, 1]
    assert [r["symbol"] for r in result] == names
    with pytest.raises(ValueError, match="not available"):
        value.dispatch_role("reviewer", {"action": "read_api", "args": {"symbols": names}}, {})


@pytest.mark.parametrize("success", [True, False])
def test_only_successful_render_supplies_inspection(value, monkeypatch, success):
    def dispatch(self, role, command, state):
        state["latest_render"] = {"tool_success": success}
        return {"rendered": success}

    def inspect(ids, state):
        state.update(images=["actual.jpg"], pending_cues=ids)
        return [{"cue": {"id": i}} for i in ids]

    monkeypatch.setattr(module.SolLearningV2, "dispatch_role", dispatch)
    monkeypatch.setattr(value, "inspect_segments", inspect)
    result = value.dispatch_role("creator", {"action": "render", "args": {}}, {})
    assert ("automatic_inspection" in result) == success
    assert value.team["actors"]["creator"]["observed"] == []


def judgment(status):
    return {"review": {"action": "review", "status": status,
            "viewer_test": {"can_explain": "Visible relation", "missing_links": [],
                            "transfer_question": "Change a condition", "supported_answer": "A supported prediction"},
            "quality": {k: {"rating": 4, "evidence": "Actual supplied pixels"} for k in DIMENSIONS}}}


@pytest.mark.parametrize("cold_status,source_status,expected", [("revise", "pass", "revise"), ("pass", "revise", "revise"), ("pass", "pass", "pass")])
@pytest.mark.parametrize("blockers", [[], [{"cue": "a", "problem": "Orphan punctuation"}]])
def test_two_reviews_cover_all_cues_and_neither_can_override(value, monkeypatch, cold_status, source_status, expected, blockers):
    video = value.out / "video.mp4"
    video.write_bytes(b"video")
    hashes = {"video": pilot.sha256(video)}
    pilot.write_json(value.state_path, {"latest_render": {"tool_success": True}})
    pilot.write_json(value.out / "review-input.json", {"hashes": hashes, "cue_ids": list("abc"),
                     "frames": [{"cue": n, "path": str(value.out / f"{n}.jpg"), "time": i * 10 + 1} for i, n in enumerate("abc")],
                     "subtitle_audit": {"blockers": blockers}})
    monkeypatch.setattr(value, "verify", lambda: None)
    monkeypatch.setattr(value, "latest_video", lambda state: (video, 30))
    monkeypatch.setattr(module.media, "Production", lambda path: SimpleNamespace(hashes=lambda video: hashes))
    monkeypatch.setattr(value, "reviewer_context", lambda: "PUBLIC_COLD_VIEW")
    monkeypatch.setattr(module.ReviewCycleExperiment, "reviewer_context", lambda self: "SOURCE_SCRIPT_SENTINEL")
    calls = []

    def review(label, context, ids, frames, images, state):
        calls.append((label, context, ids, frames))
        return judgment(cold_status if len(calls) == 1 else source_status)

    monkeypatch.setattr(value, "review_batch", review)
    _, report = value.independent_review(1)
    assert len(calls) == 2 and all(c[2] == list("abc") and len(c[3]) == 3 for c in calls)
    assert "SOURCE_SCRIPT_SENTINEL" not in calls[0][1]
    assert "SOURCE_SCRIPT_SENTINEL" in calls[1][1]
    assert "PUBLIC_COLD_VIEW" not in calls[1][1]
    assert report["status"] == ("revise" if blockers else expected)
    assert report["segments"][0]["review"]["status"] == cold_status


def test_v3_retains_the_fixed_learning_rubric():
    first = pilot.read_json(pilot.ROOT / "configs/learning-workflow-v1.json")
    third = pilot.read_json(pilot.ROOT / "configs/learning-workflow-v3.json")
    assert third["evaluation"] == first["evaluation"]
    assert third["author_guidance"] == first["author_guidance"]
