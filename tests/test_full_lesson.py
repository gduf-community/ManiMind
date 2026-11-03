import copy

import pytest

from manimind.postproduce import full_lesson as full


def script():
    return {"title": "Instantaneous speed", "cues": [
        {"id": cue, "heading": "Read the graph", "subtitle_lines": ["First sentence.", "Second sentence."],
         "spoken": "First sentence. Second sentence.", "min_duration": 14 if cue == "algebra" else 9}
        for cue in full.CUE_IDS]}


def test_complete_script_is_valid():
    full.validate_script(script())


@pytest.mark.parametrize("edit", [
    lambda s: s.update(code="print(1)"),
    lambda s: s["cues"].pop(),
    lambda s: s["cues"].reverse(),
    lambda s: s["cues"][0].update(min_duration=True),
    lambda s: s["cues"][0].update(min_duration=float("nan")),
    lambda s: s["cues"][0].update(min_duration=8.1),
    lambda s: s["cues"][0].update(subtitle_lines=["x" * 37, "Second sentence."]),
    lambda s: s["cues"][0].update(spoken=""),
    lambda s: s["cues"][8].update(min_duration=10),
])
def test_invalid_script_rejected(edit):
    data = script()
    edit(data)
    with pytest.raises(ValueError):
        full.validate_script(data)


@pytest.mark.parametrize("name", ["../other", "A", "x/y", "", "a" * 81])
def test_project_path_cannot_escape(name):
    with pytest.raises(ValueError):
        full.Lesson(name)


def test_init_freezes_script_and_components_without_executing_model(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    answer = tmp_path / "answer.json"
    full.write_json(answer, script())
    lesson = full.Lesson("test-lesson")
    lesson.init(answer)
    frozen = (lesson.out / "scene.py").read_text()
    assert "class FullVelocity(InstantaneousVelocity):" in frozen
    assert str(lesson.out / "timeline.json") in frozen
    assert full.read_json(lesson.out / "model-script.json") == script()
    data = full.read_json(lesson.out / "spec.json")
    assert data["facts"] == full.read_json(full.pilot.SPEC)["facts"]
    assert data["cues"][8]["visual"]
    full.write_json(answer, {"changed": True})
    assert full.read_json(lesson.out / "model-script.json") == script()
    full.write_json(answer, script())
    with pytest.raises(ValueError, match="overwritten"):
        lesson.init(answer)


def test_changed_spec_rejects_old_narration(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    lesson = full.Lesson("test-lesson")
    full.write_json(lesson.out / "timeline.json", {"spec_sha256": "old"})
    full.write_json(lesson.out / "spec.json", {})
    with pytest.raises(ValueError, match="Stale narration"):
        lesson.hashes()


def test_assemble_requires_coverage_of_every_cue(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    lesson = full.Lesson("test-lesson")
    full.write_json(lesson.out / "review-input.json", {
        "video_path": "unused.mp4", "hashes": {},
        "frames": [{"cue": "hook", "path": "one.png"}]})
    full.write_json(lesson.context / "review.json", {"inspected_frames": ["one.png"]})
    monkeypatch.setattr(full.Lesson, "hashes", lambda *a: {})
    monkeypatch.setattr(full.pilot, "validate_review", lambda *a: None)
    monkeypatch.setattr(full.pilot, "run", lambda *a, **kw: pytest.fail("Must not mux"))
    with pytest.raises(ValueError, match="Every cue"):
        lesson.assemble()


def test_stale_evidence_cannot_mux(tmp_path, monkeypatch):
    monkeypatch.setattr(full, "ROOT", tmp_path)
    lesson = full.Lesson("test-lesson")
    full.write_json(lesson.out / "review-input.json", {"video_path": "unused.mp4", "hashes": {"video": "old"}})
    full.write_json(lesson.context / "review.json", {})
    monkeypatch.setattr(full.Lesson, "hashes", lambda *a: {"video": "new"})
    with pytest.raises(ValueError, match="Stale evidence"):
        lesson.assemble()
