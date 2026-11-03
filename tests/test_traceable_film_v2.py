"""Real-video provenance probes; synthetic reviews never approve a lesson."""

import csv
from pathlib import Path
import subprocess

from PIL import Image
import pytest

from manimind.postproduce import traceable_film_v2 as gate
from manimind.review.learning_quality import DIMENSIONS


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Mutable fixtures only; production code uses create-only records.
    if path.exists():
        path.unlink()
    gate.common.write_json(path, value)


def report(stage, current):
    value = dict(action="review", stage=stage, status="pass", reviewer_role="independent",
                 reviewer_agent="fixture-" + stage, reviewer_context="fixture-context-" + stage,
                 bindings=current, blocking_findings=[], release_authorized=True,
                 listening_reviewed=False, student_tested=False, test_fixture_only=True)
    if stage == "visual":
        value.update(viewer_test=dict(can_explain="fixture", missing_links=[],
                     transfer_question="fixture", supported_answer="fixture"),
                     quality={name: dict(rating=4, evidence="synthetic fixture") for name in DIMENSIONS},
                     editorial_checks={name: dict(status="pass", evidence=[dict(time=1, finding="fixture")])
                                       for name in gate.unit_film.quality.CHECKS})
    return value


@pytest.fixture
def native_attempt(tmp_path, monkeypatch):
    unit = gate.unit_film
    monkeypatch.setattr(unit.pilot, "ROOT", tmp_path)
    profile, course, catalogue = (tmp_path / name for name in ("profile.json", "course.json", "catalogue.csv"))
    write(profile, dict(version="understanding-first-v3", delivery_contract=unit.units.SOURCE_CONTRACT,
          formula_continuity_contract=gate.CONTRACT, formula_continuity_gate="traceable_film_v2"))
    with catalogue.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(unit.curriculum.CATALOGUE_FIELDS))
        writer.writeheader()
        writer.writerow({key: "" if key == "requires" else "topic" for key in unit.curriculum.CATALOGUE_FIELDS})
    write(course, dict(schema_version=1, catalogue="catalogue.csv", unit_id="course", title="Course",
          audience="students", scope="fixture", lessons=[dict(project_id="lesson", catalogue_ids=["topic"],
          new_understanding="relation", exit_task="predict", handoff="next")]))
    context = tmp_path / "runtime/projects/lesson/context.json"
    unit.curriculum.write_context(course, "lesson", context, tmp_path)
    scene = tmp_path / "scene.py"
    scene.write_text("# no production scene executed\n", encoding="ascii")
    inputs = [context, course, catalogue, Path(unit.curriculum.__file__).resolve(),
              Path(gate.previous.__file__).resolve(), Path(gate.__file__).resolve()]
    plan = dict(title="Fixture", project_id="lesson", scene="scene.py", workflow_profile="profile.json",
                author_agent="fixture-author", author_context="fixture-author-context", revision_mode="fresh",
                lesson_context=str(context.relative_to(tmp_path)), sources=list(map(str, inputs)),
                formula_transitions=[dict(id="ratio", operation="divide", source="dy,dx", target="dy/dx", purpose="ratio")],
                cues=[dict(id="demo", duration=8, heading="Demo", visual="fixture", learning_purpose="ratio",
                           anchors=[dict(id="event", meaning="ratio")])])
    folder = tmp_path / "attempt"
    write(folder / "plan.json", plan)
    write(folder / "workflow-profile.json", gate.common.read_json(profile))
    write(folder / "timeline.json", unit.visual.visual_timeline(plan))
    write(folder / "visual-events.json", dict(duration=8, events=[dict(id="event", time=1)]))
    write(folder / "focus-events.json", dict(duration=8, windows=[dict(id="f1", start=0, end=8)]))
    video = folder / "changing-test-source.mp4"
    subprocess.run([unit.pilot.FFMPEG, "-v", "error", "-n", "-f", "lavfi", "-i",
                    "testsrc2=size=64x64:rate=30:duration=8", "-an", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(video)], check=True, capture_output=True)
    frames = []
    for phase, time in (("before", 1), ("during", 2), ("after", 3)):
        path = folder / f"{phase}.png"
        subprocess.run([unit.pilot.FFMPEG, "-v", "error", "-n", "-ss", str(time), "-i", str(video),
                        "-frames:v", "1", str(path)], check=True, capture_output=True)
        frames.append(dict(time=time, path=str(path), sha256=gate.common.sha(path)))
    record = dict(video=str(video), video_sha256=gate.common.sha(video), duration=8,
                  plan_sha256=gate.common.sha(folder / "plan.json"),
                  input_hashes={str(path): gate.common.sha(path) for path in (profile, scene, *inputs)})
    write(folder / "render.json", record)
    write(folder / "review-input.json", dict(render=record, frames=frames, sheets=[]))
    review = tmp_path / "review-fixture-not-approval.json"
    lossless = tmp_path / "lossless"

    def refresh_index():
        if lossless.exists():
            value = gate.common.read_json(lossless / "formula-evidence.json")
            value["bindings"] = unit.bindings(folder)
            write(lossless / "formula-evidence.json", value)
        else:
            gate.prepare_evidence(folder, lossless)

    def refresh():
        refresh_index()
        value = report("visual", unit.bindings(folder))
        index = lossless / "formula-evidence.json"
        rows = gate.common.read_json(index)["frames"]
        value["formula_continuity"] = dict(checks=[dict(id="ratio", traceable=True,
            identity_finding="fixture only", operation_finding="fixture only",
            evidence=[dict(phase=phase, time=row["time"], frame=row["path"], sha256=row["sha256"], finding="fixture")
                      for phase, row in zip(("before", "during", "after"), rows, strict=True)])])
        value["formula_continuity"].update(evidence_index=str(index), evidence_index_sha256=gate.common.sha(index))
        write(review, value)
        return value
    refresh()
    return dict(root=tmp_path, folder=folder, review=review, refresh=refresh, lossless=lossless)


def test_current_actual_pixels_pass(native_attempt):
    x = native_attempt
    assert gate.require_review(x["folder"], x["review"])["status"] == "pass"


@pytest.mark.parametrize("change", ["foreign", "wrong_time"])
def test_self_consistent_but_false_frame_index_is_rejected(native_attempt, change):
    x = native_attempt
    path = x["lossless"] / "formula-evidence.json"
    value = gate.common.read_json(path)
    if change == "foreign":
        frame = x["root"] / "foreign.png"
        Image.new("RGB", (64, 64), "blue").save(frame)
        value["frames"][1].update(path=str(frame), sha256=gate.common.sha(frame))
    else:
        value["frames"][1]["time"] = 2.5
    write(path, value)
    x["refresh"]()
    with pytest.raises(ValueError, match="pixels"):
        gate.require_review(x["folder"], x["review"])


def test_same_rgb_bytes_with_wrong_dimensions_are_rejected(native_attempt):
    x = native_attempt
    path = x["lossless"] / "formula-evidence.json"
    value = gate.common.read_json(path)
    frame = x["root"] / "reshaped.png"
    with Image.open(value["frames"][1]["path"]) as image:
        Image.frombytes("RGB", (128, 32), image.convert("RGB").tobytes()).save(frame)
    value["frames"][1].update(path=str(frame), sha256=gate.common.sha(frame))
    write(path, value)
    x["refresh"]()
    with pytest.raises(ValueError, match="dimensions"):
        gate.require_review(x["folder"], x["review"])


def test_lossless_preparation_accepts_native_jpeg_timestamps(native_attempt):
    from manimind.render.manim_renderer import extract_keyframes
    x = native_attempt
    record = gate.common.read_json(x["folder"] / "render.json")
    extracted = extract_keyframes(video_path=record["video"], output_dir=x["root"] / "native-jpg",
        timestamps=[1, 2, 3], ffmpeg_executable=gate.unit_film.pilot.FFMPEG)
    assert extracted.success and all(Path(path).suffix == ".jpg" for path in extracted.frame_paths)
    native_index = gate.common.read_json(x["folder"] / "review-input.json")
    native_index["frames"] = [dict(time=time, path=path, sha256=gate.common.sha(path))
                              for time, path in zip([1, 2, 3], extracted.frame_paths, strict=True)]
    write(x["folder"] / "review-input.json", native_index)
    # Re-extract real PNGs from the video, not from the lossy JPEG files.
    lossless = x["root"] / "lossless-from-native-jpg"
    prepared = gate.prepare_evidence(x["folder"], lossless)
    assert all(Path(row["path"]).suffix == ".png" for row in prepared["frames"])
    assert prepared["bindings"] == gate.unit_film.bindings(x["folder"])
    with pytest.raises(FileExistsError):
        gate.prepare_evidence(x["folder"], lossless)


@pytest.mark.parametrize("same_context", [False, True])
def test_regression_requires_distinct_real_context(native_attempt, same_context):
    x = native_attempt
    folder = x["folder"]
    baseline = folder / "changing-test-source.mp4"
    contract, comparison = x["root"] / "contract.json", x["root"] / "comparison-fixture-not-approval.json"
    write(contract, dict(schema_version=1, assets=dict(old=dict(path=str(baseline),
        sha256=gate.common.sha(baseline), duration=8)), units=[dict(id="reason", asset="old",
        function="reason", baseline_interval=[1, 4], features=[dict(id="motion", kind="process", claim="reason")])]))
    plan = gate.common.read_json(folder / "plan.json")
    plan.update(revision_mode="revision", revision_contract=str(contract), revision_review=str(comparison))
    write(folder / "plan.json", plan)
    record = gate.common.read_json(folder / "render.json")
    record["plan_sha256"] = gate.common.sha(folder / "plan.json")
    record["input_hashes"][str(contract)] = gate.common.sha(contract)
    write(folder / "render.json", record)
    evidence = gate.common.read_json(folder / "review-input.json")
    evidence["render"] = record
    write(folder / "review-input.json", evidence)
    first = x["refresh"]()
    value = report("content_regression", gate.unit_film.bindings(folder))
    if same_context:
        value["reviewer_context"] = first["reviewer_context"]
    value["units"] = [dict(id="reason", features=[dict(id="motion", outcome="retained",
        evidence=[dict(phase=phase, time=time, finding="fixture")
                  for phase, time in (("before", 1), ("during", 2), ("after", 3))])])]
    write(comparison, value)
    if same_context:
        with pytest.raises(ValueError, match="distinct"):
            gate.require_review(folder, x["review"])
    else:
        assert gate.require_review(folder, x["review"])["status"] == "pass"


def test_actual_v2_source_pin_is_required(native_attempt):
    x = native_attempt
    path = x["folder"] / "render.json"
    value = gate.common.read_json(path)
    value["input_hashes"][str(Path(gate.__file__).resolve())] = "0" * 64
    write(path, value)
    with pytest.raises(ValueError, match="v2"):
        gate.require_review(x["folder"], x["review"])
