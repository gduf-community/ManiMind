import copy

import pytest

from manimind.postproduce import formula_film as subject


def test_mux_preserves_both_reviewed_video_and_selected_audio_packets():
    command = subject.mux_command("visual.mp4", "voice.mp4", "full.mp4", 114)
    assert command[command.index("-c:v") + 1] == "copy"
    assert command[command.index("-c:a") + 1] == "copy"
    assert "0:v:0" in command and "1:a:0" in command
    assert "-filter_complex" not in command and "-vf" not in command
    assert command[command.index("-t") + 1] == "114"


def video_info():
    return {"streams": [
        {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30/1",
         "nb_frames": "3420", "codec_name": "h264", "pix_fmt": "yuv420p", "profile": "High",
         "duration": "114.0", "start_time": "0.0"},
        {"codec_type": "audio", "duration": "114.0", "start_time": "0.0"},
    ]}


def test_checks_native_player_compatibility_and_full_av_clock():
    subject.check_video(video_info(), 114)
    info = video_info()
    info["streams"].pop()
    subject.check_video(info, 114, silent=True)


@pytest.mark.parametrize(("field", "value"), [
    ("avg_frame_rate", "25/1"), ("nb_frames", "2850"), ("pix_fmt", "yuv444p"),
    ("profile", "High 4:4:4 Predictive"), ("duration", "113"), ("start_time", "1"),
])
def test_video_regressions_are_blocked(field, value):
    info = video_info()
    info["streams"][0][field] = value
    with pytest.raises(ValueError, match="playback checks"):
        subject.check_video(info, 114)


def test_audio_offset_is_not_hidden_by_matching_video_duration():
    info = video_info()
    info["streams"][1]["start_time"] = "0.5"
    with pytest.raises(ValueError, match="Audio/video"):
        subject.check_video(info, 114)


def test_reuses_original_timeline_and_only_adds_declared_landing_events(monkeypatch):
    original = {"cues": [{"id": "landing_condition", "anchors": [{"id": "ground"}]}]}
    monkeypatch.setattr(subject.common, "read_json", lambda _: copy.deepcopy(original))
    result = subject.timeline_for({"timeline": "fixture.json"})
    assert [row["id"] for row in result["cues"][0]["anchors"]] == [
        "ground", "term_relocated", "height_doubled", "square_time_isolated"]
    assert len(original["cues"][0]["anchors"]) == 1


@pytest.mark.parametrize(("relation", "start", "end", "passed"), [
    ("after", 5.04, 7, True), ("after", 4.99, 7, False),
    ("before", 2, 4.99, True), ("before", 2, 5.01, False),
])
def test_checks_real_narration_semantic_boundaries(monkeypatch, relation, start, end, passed):
    def read(path):
        if path.name == "events.json":
            return {"events": [{"id": "visible", "time": 5}]}
        return {"duration": 114, "segments": [
            {"id": "N01", "anchor": "visible", "relation": relation, "start": start, "end": end}]}
    monkeypatch.setattr(subject.common, "read_json", read)
    plan = {"alignment": "fixture.json", "original_events": "events.json"}
    events = {"duration": 114, "events": [{"id": "visible", "time": 5}]}
    if passed:
        assert subject.check_timing(plan, events)[0]["passed"]
    else:
        with pytest.raises(ValueError, match="semantic boundary"):
            subject.check_timing(plan, events)


def test_early_answer_cannot_pass_just_because_it_precedes_narration(monkeypatch):
    monkeypatch.setattr(subject.common, "read_json", lambda _: {"events": [{"id": "landing", "time": 90.4}]})
    with pytest.raises(ValueError, match="Original visual event drifted"):
        subject.check_timing({"original_events": "events.json"},
                             {"events": [{"id": "landing", "time": 89}]})


def test_no_final_composition_without_fresh_independent_review(monkeypatch, tmp_path):
    monkeypatch.setattr(subject, "bindings", lambda _: {"video_sha256": "current"})
    review = tmp_path / "review.json"
    subject.common.write_json(review, {"status": "pass", "reviewer_role": "independent",
        "reviewer_agent": "fixture", "bindings": {"video_sha256": "stale"}, "blocking_findings": []})
    with pytest.raises(ValueError, match="independent full-film review"):
        subject.release(tmp_path, review)
    assert not (tmp_path / "playback").exists()


@pytest.mark.parametrize("authorization", [None, False, "yes", 1])
def test_pass_status_does_not_override_explicit_nonpublication(monkeypatch, tmp_path, authorization):
    monkeypatch.setattr(subject, "bindings", lambda _: {"video_sha256": "current"})
    review = tmp_path / "review.json"
    subject.common.write_json(review, {"status": "pass", "reviewer_role": "independent",
        "reviewer_agent": "fixture", "bindings": {"video_sha256": "current"},
        "blocking_findings": [], "release_authorized": authorization})
    with pytest.raises(ValueError, match="independent full-film review"):
        subject.release(tmp_path, review)
    assert not (tmp_path / "playback").exists()


@pytest.fixture
def bound_attempt(tmp_path, monkeypatch):
    out = tmp_path / "attempt"
    out.mkdir()
    source, video, frame, motion = [out / name for name in ("source.py", "video.mp4", "frame.jpg", "motion.json")]
    for path in (source, video, frame, motion):
        path.write_bytes(b"Hash-only fixture, not playable media")
    subject.common.write_json(out / "plan.json", {"base_video_sha256": "base"})
    rendered = {"video": str(video), "video_sha256": subject.common.sha(video),
                "input_hashes": {str(source): subject.common.sha(source)},
                "plan_sha256": subject.common.sha(out / "plan.json")}
    subject.common.write_json(out / "render.json", rendered)
    events = {"events": []}
    subject.common.write_json(out / "visual-events.json", events)
    subject.common.write_json(out / "review-input.json", {"render": rendered, "events": events,
        "frames": [{"path": str(frame), "sha256": subject.common.sha(frame)}], "sheets": [],
        "motion_files": [{"path": str(motion), "sha256": subject.common.sha(motion)}]})
    monkeypatch.setattr(subject, "check_timing", lambda *_: [])
    return out, {"source": source, "video": video, "frame": frame, "motion": motion,
                 "plan": out / "plan.json", "events": out / "visual-events.json"}


def test_review_binds_full_media_and_all_pixel_motion_sources(bound_attempt):
    out, paths = bound_attempt
    assert subject.bindings(out)["video_sha256"] == subject.common.sha(paths["video"])


@pytest.mark.parametrize("kind", ["source", "video", "frame", "motion", "plan", "events"])
def test_review_invalidated_by_changed_sources_or_evidence(bound_attempt, kind):
    out, paths = bound_attempt
    with paths[kind].open("ab") as stream:
        stream.write(b" ")
    if kind == "events":
        # Re-serialization alone is fine; an actual measured event change is not.
        paths[kind].write_text('{"events":[{"id":"changed","time":0}]}')
    with pytest.raises(ValueError, match="changed"):
        subject.bindings(out)
