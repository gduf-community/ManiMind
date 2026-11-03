import copy
from pathlib import Path
import wave

import pytest

from manimind.postproduce import focus_captions as subject


def write(path, value):
    subject.common.write_json(path, value)


def replace(path, value):
    path.unlink()
    write(path, value)


def review_value(stage, bindings, agent="pixel-reviewer"):
    return {"stage": stage, "bindings": bindings, "status": "pass", "release_authorized": True,
            "reviewer_role": "independent", "reviewer_agent": agent, "blocking_findings": [],
            "listening_reviewed": False}


@pytest.mark.parametrize("text", [" \n乙", "\n  \n乙", "甲\n乙", "甲\n  \n乙", "甲\n  \n"])
def test_caption_render_never_emits_hard_newlines_for_whitespace_boundaries(text):
    alignment = {"duration": 5, "segments": [{"id": "s", "text": text,
        "start": 1, "end": 4, "duration_seconds": 3}]}
    captions = subject.make_captions(alignment)
    assert "".join(row["text"] for row in captions["events"]) == text
    ass = subject.make_ass(captions, subject.DEFAULT_STYLE, 1920, 1080)
    assert r"\N" not in ass and r"\n" not in ass


@pytest.fixture
def source(monkeypatch, tmp_path):
    # Real PCM/receipts/scheduler/audio_bindings; only upstream visual approval
    # and ffmpeg I/O are mocked, never production outputs or network services.
    film, common = subject.film, subject.common
    segments = [{"id": f"N{i}", "cue": "demo", "focus": f"f{i}",
                 "text": "水平方向的速度保持不变，竖直方向的速度随时间变化。"} for i in range(2)]
    focus = tmp_path / "focus-events.json"
    write(focus, {"duration": 20, "windows": [{"id": f"f{i}", "start": i * 5 + 1,
                                             "end": i * 5 + 5} for i in range(2)]})
    write(tmp_path / "timeline.json", {"duration": 20, "cues": [{"id": "demo"}]})
    narration = tmp_path / "narration.json"
    write(narration, {"segments": segments})
    silent_video = tmp_path / "silent.mp4"
    silent_video.write_bytes(b"silent fixture")
    silent_path = tmp_path / "silent-delivery.json"
    write(silent_path, {"narration": str(narration)})
    silent = {"attempt": str(tmp_path), "duration": 20, "video": str(silent_video),
              "sha256": common.sha(silent_video), "narration": str(narration),
              "bindings": {"focuses_sha256": common.sha(focus)}}
    monkeypatch.setattr(film, "verify_delivery", lambda _: silent)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"hash-only reference fixture; no synthesis")
    plan = {"schema_version": 2, "synthetic_reference": True,
            "reference_source": str(reference),
            "reference_sha256": film.vox.REFERENCE_SHA256, "reference_text": film.vox.audition.TEXT,
            "generation": film.vox.GENERATION, "segments": segments,
            "source": {"delivery": str(silent_path), "delivery_sha256": common.sha(silent_path),
                       "video": str(silent_video), "video_sha256": common.sha(silent_video),
                       "focuses": str(focus), "focuses_sha256": common.sha(focus)}}
    plan_path = tmp_path / "speech-plan.json"
    write(plan_path, plan)
    inputs = []
    for segment in segments:
        wav = tmp_path / f"{segment['id']}.wav"
        with wave.open(str(wav), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(48000)
            stream.writeframes(b"\x10\x00\xf0\xff" * 24000)
        receipt = wav.with_suffix(".receipt.json")
        write(receipt, {"id": segment["id"], "segment": segment, "request": {"text": segment["text"]},
                        "plan_sha256": common.sha(plan_path), "wav_sha256": common.sha(wav),
                        "reference_sha256": plan["reference_sha256"], "first_take": True,
                        "segment_call_count": 1, "acceptance": film.vox.ACCEPTANCE,
                        "worker_sha256": common.sha(film.vox.__file__), "helper_sha256": film.vox.HELPER_SHA256})
        inputs.append({"wav": str(wav), "sha256": common.sha(wav), "receipt": str(receipt),
                       "receipt_sha256": common.sha(receipt)})
    rows = film.schedule(subject._read(tmp_path / "timeline.json"), {"segments": segments}, subject._read(focus), [1, 1])
    alignment = tmp_path / "alignment.json"
    write(alignment, {"plan": str(plan_path), "plan_sha256": common.sha(plan_path), "source": plan["source"],
                      "duration": 20, "segments": rows, "inputs": inputs})
    current = film.audio_bindings(alignment)
    audio_review = tmp_path / "audio-review.json"
    write(audio_review, review_value("audio_alignment", current))
    voiced_video = tmp_path / "voiced.mp4"
    voiced_video.write_bytes(b"voiced fixture")
    delivery = tmp_path / "voiced-delivery.json"
    write(delivery, {"video": str(voiced_video), "sha256": common.sha(voiced_video), "duration": 20,
                     "bindings": current, "review": str(audio_review), "review_sha256": common.sha(audio_review),
                     "full_decode_passed": True})
    calls = []
    def run(command, timeout=180):
        calls.append(command)
        if "-filters" in command:
            return " ... ass               V->V       Render ASS subtitles using libass\n"
        if "streamhash" in command:
            return "0,a,SHA256=" + "a" * 64 + "\n"
        if "-vf" in command:
            Path(command[-1]).write_bytes(b"mock caption encode")
        return ""
    monkeypatch.setattr(subject.pilot, "run", run)
    monkeypatch.setattr(subject.pilot, "probe", lambda _: {"format": {"duration": "20"}, "streams": [
        {"codec_type": "video", "duration": "20", "width": 1920, "height": 1080},
        {"codec_type": "audio", "duration": "20"}]})
    return alignment, delivery, tmp_path / "candidate", calls


def prepare(source):
    alignment, delivery, candidate, _ = source
    subject.prepare(alignment, delivery, candidate, producer_agent="caption-author")
    return candidate


def caption_review(candidate, tmp_path):
    frame = tmp_path / "pixel.png"
    frame.write_bytes(b"mock independent frame evidence")
    value = review_value("captions", subject.bindings(candidate))
    value["checks"] = {name: {"status": "pass", "evidence": [{"finding": "Actual candidate checked"}]}
                       for name in ("layout", "text_consistency", "frame_evidence")}
    value["checks"]["frame_evidence"]["evidence"][0].update(
        time=1.5, path=str(frame), sha256=subject.common.sha(frame))
    return value


def test_candidate_and_release_copy_only_after_current_independent_review(source, tmp_path):
    candidate = prepare(source)
    assert subject._read(candidate / "candidate.json")["status"] == "candidate_not_released"
    assert subject._read(candidate / "style.json") == subject.DEFAULT_STYLE
    assert not (candidate / "delivery.json").exists()
    command = next(command for command in source[3] if "-vf" in command)
    assert command[command.index("-c:a") + 1] == "copy"
    assert command[command.index("-map") + 1] == "0:v:0"
    assert "0:a:0" in command and "-sn" in command
    assert "-af" not in command and "-t" not in command
    assert not any("scale=" in str(part) for part in command)
    assert any("-xerror" in command for command in source[3])
    review = tmp_path / "caption-review.json"
    write(review, caption_review(candidate, tmp_path))
    output = tmp_path / "playback"
    result = subject.release(candidate, review, output)
    assert {path.name for path in output.iterdir()} == {"captioned.mp4", "delivery.json"}
    assert (output / "captioned.mp4").read_bytes() == (candidate / "candidate.mp4").read_bytes()
    assert result["listening_reviewed"] is False
    with pytest.raises(FileExistsError):
        subject.release(candidate, review, output)
    with pytest.raises(FileExistsError):
        subject.prepare(source[0], source[1], candidate, producer_agent="caption-author")


@pytest.mark.parametrize("mutation", ["stage", "bindings", "author", "status", "authorized", "listening", "evidence", "frame"])
def test_caption_gate_refuses_wrong_or_stale_review(source, tmp_path, mutation):
    candidate = prepare(source)
    value = caption_review(candidate, tmp_path)
    if mutation == "stage": value["stage"] = "audio_alignment"
    if mutation == "bindings": value["bindings"] = {}
    if mutation == "author": value["reviewer_agent"] = "caption-author"
    if mutation == "status": value["status"] = "revise"
    if mutation == "authorized": value["release_authorized"] = False
    if mutation == "listening": value["listening_reviewed"] = True
    if mutation == "evidence": value["checks"]["layout"]["evidence"] = []
    if mutation == "frame": (tmp_path / "pixel.png").write_bytes(b"changed pixels")
    review = tmp_path / "review.json"
    write(review, value)
    with pytest.raises(ValueError):
        subject.release(candidate, review, tmp_path / "no-release")
    assert not (tmp_path / "no-release").exists()


@pytest.mark.parametrize("name", ["support/captions.ass", "captions.json", "style.json", "candidate.mp4",
                                   "source-receipts.json", "candidate.json", "bindings.json"])
def test_candidate_changes_require_new_candidate(source, name):
    candidate = prepare(source)
    path = candidate / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        subject.bindings(candidate)


@pytest.mark.parametrize("key", ["delivery", "video", "review", "wav", "receipt", "plan", "narration"])
def test_original_chain_is_frozen(source, key):
    candidate = prepare(source)
    alignment, delivery = subject._read(source[0]), subject._read(source[1])
    if key == "delivery": path = source[1]
    elif key in {"video", "review"}: path = Path(delivery[key])
    elif key in {"wav", "receipt"}: path = Path(alignment["inputs"][0][key])
    elif key == "plan": path = Path(alignment["plan"])
    else: path = source[0].parent / "narration.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        subject.bindings(candidate)


@pytest.mark.parametrize("count", [1, 47, 51])
def test_topic_and_utterance_count_are_not_fixed(count):
    text = "甲" * 18 + "，" + "乙" * 22 + "。"
    rows = [{"id": f"u{i}", "text": text, "start": i * 2 + .001, "end": i * 2 + 1.999,
             "duration_seconds": 1.998} for i in range(count)]
    captions = subject.make_captions({"duration": count * 2, "segments": rows})
    events = captions["events"]
    assert all(a["end_cs"] <= b["start_cs"] for a, b in zip(events, events[1:]))
    for row in rows:
        parts = [event for event in events if event["utterance_id"] == row["id"]]
        assert "".join(part["text"] for part in parts) == text
        assert parts[0]["text"].endswith("，")
        assert all(subject.text_width(part["text"]) <= 60 for part in parts)
        assert all(part["start_cs"] / 100 >= row["start"] and part["end_cs"] / 100 <= row["end"] for part in parts)
        assert all(part["timing"] == "character_ratio_approximation" for part in parts)


@pytest.mark.parametrize("text", ["单行\n下一行", "甲" * 80, r"字面\N{\pos(0,0)}和\h", "\n开头\n\n末尾\n", "末尾\n\n"])
def test_split_and_escape_preserve_source_and_never_create_override(text):
    parts = subject.split_text(text)
    assert "".join(parts) == text
    escaped = subject.escape_ass(text)
    assert r"\{" in escaped if "{" in text else True
    assert "\\\u2060" in escaped if "\\" in text else True
    assert "\n" not in escaped
    captions = subject.make_captions({"duration": 10, "segments": [
        {"id": "x", "text": text, "start": 0, "end": 10, "duration_seconds": 10}]})
    ass = subject.make_ass(captions, subject.DEFAULT_STYLE, 1920, 1080)
    assert "WrapStyle: 2" in ass
    # Only literal source newlines are split boundaries; no generated two-line events.
    assert r"\N" not in "\n".join(line for line in ass.splitlines() if line.startswith("Dialogue:"))


@pytest.mark.parametrize("text", ["bad\x00", "bad\r", "bad\t", "bad\x7f", "bad\u202e"])
def test_control_characters_are_rejected(text):
    with pytest.raises(ValueError): subject.escape_ass(text)


@pytest.mark.parametrize("style", [{"fontname": "Arial\n[Events]"}, {"fontsize": "40"}, {"shadow": True},
                                   {"alignment": 8}, {"max_width": 99}])
def test_styles_cannot_inject_ass(style):
    with pytest.raises(ValueError): subject.validate_style(style)


def test_unsafe_time_and_overlap_are_rejected():
    row = {"id": "x", "text": "甲", "start": .001, "end": .009, "duration_seconds": .008}
    with pytest.raises(ValueError, match="quantization"):
        subject.make_captions({"duration": 1, "segments": [row]})
    row.update(start=0, end=1, duration_seconds=1)
    with pytest.raises(ValueError, match="Overlapping"):
        subject.make_captions({"duration": 2, "segments": [row, copy.deepcopy(row)]})


def test_libass_and_tracks_are_checked_before_candidate_creation(source, monkeypatch):
    monkeypatch.setattr(subject.pilot, "run", lambda *_ , **__: "no ass filter")
    with pytest.raises(ValueError, match="libass"):
        prepare(source)
    assert not source[2].exists()


def test_extra_subtitle_track_is_rejected(source, monkeypatch):
    original = subject.pilot.probe
    def probe(path):
        value = original(path)
        value["streams"].append({"codec_type": "subtitle"})
        return value
    monkeypatch.setattr(subject.pilot, "probe", probe)
    with pytest.raises(ValueError, match="exactly one"):
        prepare(source)
    assert not source[2].exists()


def test_audio_mutation_or_decode_error_cannot_become_candidate(source, monkeypatch):
    original = subject.pilot.run
    def run(command, **kwargs):
        if "-xerror" in command:
            raise RuntimeError("decode failure")
        return original(command, **kwargs)
    monkeypatch.setattr(subject.pilot, "run", run)
    with pytest.raises(RuntimeError, match="decode failure"):
        prepare(source)
    assert not (source[2] / "bindings.json").exists()


def test_changed_audio_packets_prevent_candidate(source, monkeypatch):
    original = subject.pilot.run
    def run(command, **kwargs):
        if "streamhash" in command and source[2] / "candidate.mp4" in command:
            return "0,a,SHA256=" + "b" * 64 + "\n"
        return original(command, **kwargs)
    monkeypatch.setattr(subject.pilot, "run", run)
    with pytest.raises(ValueError, match="audio packets"):
        prepare(source)
    assert not (source[2] / "bindings.json").exists()


def test_candidate_has_no_auto_loaded_sidecar_and_playback_rejects_them(source, tmp_path):
    candidate = prepare(source)
    assert not list(candidate.glob("*.ass")) and not list(candidate.glob("*.srt"))
    assert (candidate / "support/captions.ass").is_file()
    playback = tmp_path / "bad-playback"
    playback.mkdir()
    (playback / "captioned.zh.srt").write_text("unbound sidecar")
    with pytest.raises(ValueError, match="sidecars"):
        subject._clean_playback(playback, "captioned.mp4")
    (candidate / "candidate.zh.srt").write_text("second subtitle set")
    with pytest.raises(ValueError, match="sidecars"):
        subject.bindings(candidate)
