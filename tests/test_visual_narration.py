import array
import wave

import pytest

from manimind.postproduce import visual_narration as subject


def sentence(identity, anchor, relation="after", cue="one"):
    return {"id": identity, "cue": cue, "anchor": "event", "anchor_time": anchor,
            "relation": relation, "text": "原审核句子"}


def timeline():
    return {"duration": 20, "cues": [{"id": "one", "start": 0, "duration": 10},
                                    {"id": "two", "start": 10, "duration": 10}]}


def test_after_waits_for_event_and_measured_previous_full_clip():
    segments = [sentence("N01", 1), sentence("N02", 2)]
    rows = subject.schedule(timeline(), segments, [3, 2])
    assert rows[0]["start"] == pytest.approx(1.04)
    assert rows[1]["start"] >= rows[0]["end"] + .25
    assert rows[0]["duration_seconds"] == 3
    assert segments[0] == sentence("N01", 1)


def test_before_entire_utterance_finishes_before_event():
    rows = subject.schedule(timeline(), [sentence("N01", 3, "before")], [2])
    assert rows[0]["end"] <= 2.96


def test_tight_before_does_not_silently_retime_trim_or_move_to_previous_cue():
    with pytest.raises(ValueError, match="cannot fit"):
        subject.schedule(timeline(), [sentence("N01", 11, "before", "two")], [2])


def test_late_after_does_not_overrun_cue_or_pad_visual_master():
    with pytest.raises(ValueError, match="cannot fit"):
        subject.schedule(timeline(), [sentence("N01", 8)], [3])


def test_complete_clip_can_end_at_scene_boundary_without_arbitrary_padding():
    row = subject.schedule(timeline(), [sentence("N01", 5)], [4.96])[0]
    assert row["end"] == pytest.approx(10)


def test_during_contains_actual_visual_anchor():
    row = subject.schedule(timeline(), [sentence("N01", 5, "during")], [2])[0]
    assert row["start"] <= 5 <= row["end"]


def test_every_clip_required():
    with pytest.raises(ValueError, match="exactly one"):
        subject.schedule(timeline(), [sentence("N01", 1)], [])


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), -1, 0])
def test_invalid_audio_duration(duration):
    with pytest.raises(ValueError, match="duration"):
        subject.schedule(timeline(), [sentence("N01", 1)], [duration])


@pytest.mark.parametrize("gap", [float("nan"), float("inf"), -.1, .01])
def test_real_sentence_gap_required(gap):
    with pytest.raises(ValueError, match="gap"):
        subject.schedule(timeline(), [sentence("N01", 1)], [1], gap)


def test_sentence_never_crosses_into_next_scene():
    rows = subject.schedule(timeline(), [sentence("N01", 1), sentence("N02", 12, cue="two")], [2, 3])
    assert rows[0]["end"] < 10 < rows[1]["start"]


def test_release_rejects_missing_independent_gate_before_creating_audio(tmp_path):
    alignment = tmp_path / "alignment.json"
    value = {"source": {"video_sha256": "v"}, "plan_sha256": "p"}
    subject.common.write_json(alignment, value)
    review = tmp_path / "review.json"
    subject.common.write_json(review, {"status": "pass"})
    with pytest.raises(ValueError, match="independent timing review"):
        subject.release(alignment, review)
    assert not (tmp_path / "voice-mix-raw.wav").exists()
    assert not (tmp_path / "playback").exists()


def test_release_binds_current_alignment_hash_and_honest_listening_scope(tmp_path):
    alignment = tmp_path / "alignment.json"
    subject.common.write_json(alignment, {"source": {"video_sha256": "v"}, "plan_sha256": "p"})
    review = tmp_path / "review.json"
    subject.common.write_json(review, {"status": "pass", "reviewer_role": "independent", "reviewer_agent": "reviewer",
                                     "listening_reviewed": False,
                                     "bindings": {"alignment_sha256": "stale", "video_sha256": "v", "plan_sha256": "p"}})
    with pytest.raises(ValueError, match="independent timing review"):
        subject.release(alignment, review)


@pytest.mark.parametrize("unexpected_subtitle", [False, True])
def test_release_exports_only_audio_video_and_separates_optional_subtitle(tmp_path, monkeypatch, unexpected_subtitle):
    wav = tmp_path / "N01.wav"
    with wave.open(str(wav), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(array.array("h", [1000, -1000] * 240).tobytes())
    receipt = tmp_path / "N01.receipt.json"
    plan = tmp_path / "plan.json"
    subject.common.write_json(receipt, {})
    subject.common.write_json(plan, {})
    source = {"config": "fixture", "video": str(tmp_path / "silent.mp4"), "video_sha256": "fixture-video"}
    value = {"source": source, "duration": 1.0, "plan": str(plan), "plan_sha256": subject.common.sha(plan),
             "segments": [{"id": "N01", "start": .2, "end": .21, "duration_seconds": .01, "text": "已审核句子"}],
             "inputs": [{"wav": str(wav), "sha256": subject.common.sha(wav), "receipt": str(receipt),
                         "receipt_sha256": subject.common.sha(receipt)}]}
    alignment = tmp_path / "alignment.json"
    subject.common.write_json(alignment, value)
    review = tmp_path / "review.json"
    subject.common.write_json(review, {"status": "pass", "reviewer_role": "independent", "reviewer_agent": "fixture",
                                     "listening_reviewed": False, "bindings": {"alignment_sha256": subject.common.sha(alignment),
                                     "plan_sha256": value["plan_sha256"], "video_sha256": source["video_sha256"]}})
    monkeypatch.setattr(subject, "approved_source", lambda _: (source, {}, {}))
    commands = []

    def run(command, timeout=180):
        commands.append([str(arg) for arg in command])
        if "-n" in command:
            command[-1].write_bytes(b"fixture exported media")
        return "SHA256=identical-packets"

    monkeypatch.setattr(subject.pilot, "run", run)
    kinds = ["video", "audio"] + (["subtitle"] if unexpected_subtitle else [])
    monkeypatch.setattr(subject.pilot, "probe", lambda _: {"format": {"duration": "1.0"},
                                                         "streams": [{"codec_type": kind} for kind in kinds]})
    if unexpected_subtitle:
        with pytest.raises(ValueError, match="stream layout"):
            subject.release(alignment, review)
        assert not (tmp_path / "delivery.json").exists()
    else:
        result = subject.release(alignment, review)
        assert result["video_packets_unchanged"] and result["full_decode_passed"]
        assert (tmp_path / "support/narration.srt").exists()
        assert not list((tmp_path / "playback").glob("*.srt"))
    mux = next(command for command in commands if "-n" in command)
    assert [mux[index + 1] for index, arg in enumerate(mux) if arg == "-map"] == ["0:v:0", "1:a:0"]
    assert "mov_text" not in mux
    assert not any(arg.endswith(".srt") for arg in mux)
