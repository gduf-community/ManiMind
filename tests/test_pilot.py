import pytest

import manimind.postproduce.pilot as pilot

from manimind.postproduce.pilot import cue_duration, srt_time, validate_review


def approved():
    return {"reviewer_role": "reviewer", "reviewer_id": "independent-test-reviewer", "status": "approved",
            "blockers": [], "hashes": {"video": "abc"}, "inspected_frames": ["frame.jpg"],
            "checks": dict.fromkeys(["mathematics", "visual_layout", "narrative", "cue_timing", "actual_zoom"], "pass")}


def test_cue_timing_preserves_speech_and_breathing_room():
    duration = cue_duration(6.017, 5)
    assert duration >= 6.017 + 0.95
    assert duration * 30 == pytest.approx(round(duration * 30))
    assert cue_duration(2, 8) == 8


@pytest.mark.parametrize("audio,minimum,fps", [(0, 5, 30), (-1, 5, 30), (2, -1, 30), (2, 5, 0)])
def test_invalid_timing(audio, minimum, fps):
    with pytest.raises(ValueError):
        cue_duration(audio, minimum, fps)


def test_srt_rollover():
    assert srt_time(59.9998) == "00:01:00,000"
    assert srt_time(3600.125) == "01:00:00,125"


def test_valid_review():
    validate_review(approved(), {"video": "abc"})


@pytest.mark.parametrize("key,value", [("status", "blocked"), ("blockers", ["overlap"]),
                                       ("reviewer_role", "lead"), ("reviewer_id", ""),
                                       ("inspected_frames", []), ("checks", {})])
def test_review_cannot_be_bypassed(key, value):
    report = approved()
    report[key] = value
    with pytest.raises(ValueError):
        validate_review(report, {"video": "abc"})


def test_modified_video_invalidates_approval():
    with pytest.raises(ValueError, match="stale"):
        validate_review(approved(), {"video": "new-video"})


def test_changed_spec_invalidates_prepared_timeline(monkeypatch):
    monkeypatch.setattr(pilot, "sha256", lambda path: "new-spec")
    with pytest.raises(ValueError, match="stale"):
        pilot.check_spec_provenance({"spec_sha256": "old-spec"})


def test_wrong_frame_cannot_satisfy_review():
    with pytest.raises(ValueError, match="different render"):
        validate_review(approved(), {"video": "abc"}, [{"path": "other.jpg", "sha256": "123"}])


def test_input_changed_during_render_is_rejected(monkeypatch):
    from types import SimpleNamespace
    state = {"source": "v1"}
    monkeypatch.setattr(pilot, "read_json", lambda path: {})
    monkeypatch.setattr(pilot, "check_spec_provenance", lambda timeline: None)
    monkeypatch.setattr(pilot, "render_input_hashes", lambda: {"source_sha256": state["source"]})
    monkeypatch.setattr(pilot, "SCENE", SimpleNamespace(read_text=lambda **kw: "old source"))
    monkeypatch.setattr(pilot, "write_json", lambda *args: None)
    def render_stub(**kwargs):
        state["source"] = "v2"
        return SimpleNamespace(success=True, code_path="copy.py", to_dict=lambda: {})
    monkeypatch.setattr(pilot, "render_manim_scene", render_stub)
    with pytest.raises(ValueError, match="changed during"):
        pilot.render("m")
