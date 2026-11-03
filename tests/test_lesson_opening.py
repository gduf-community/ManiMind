"""Offline gates plus synthetic, real-ffmpeg compatibility checks; no TTS/GPU."""

import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import wave

import pytest

from manimind.postproduce import lesson_opening as subject
from test_unit_film import project, captioned_candidate  # noqa: F401


def write(path, value):
    subject.common.write_json(path, value)


def replace(path, value):
    path.unlink()
    write(path, value)


def pcm(path, samples, *, byte=b"\x10\x00", rate=48000):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(byte * samples)


def plan_value(root, body_path, body_video, duration, intro):
    wav = root / "intro-input.wav"
    pcm(wav, 38400)
    source = root / "opening-source.py"
    source.write_text("# hash-only synthetic source fixture\n")
    script = {"title": "An opening", "question": "Why?", "text": "First;second.",
              "subtitle_clauses": [{"id": "c1", "text": "First;", "start": 0, "end": .4},
                                   {"id": "c2", "text": "second.", "start": .4, "end": .8}]}
    identity = {"author_agent": "opening-author", "author_context": "opening-author-context"}
    receipt = root / "intro-receipt.json"
    assets = {"video": subject._receipt(intro), "wav": subject._receipt(wav),
              "sources": [subject._receipt(source)]}
    write(receipt, {"schema_version": 1, **identity, **assets, "script": script})
    contract = root / "revision-contract.json"
    write(contract, {"schema_version": 1, "assets": {"body": {"path": str(body_video),
          "sha256": subject.common.sha(body_video), "duration": duration}}, "units": [{"id": "cue1", "asset": "body",
          "function": "Keep the complete explanation", "baseline_interval": [0, duration],
          "features": [{"id": "movement", "kind": "process", "claim": "Retain the complete variable progression"}]}]})
    path = root / "opening-plan.json"
    write(path, {"schema_version": 1, **identity, **script, "body_delivery": subject._receipt(body_path),
                 "intro": {**assets, "receipt": subject._receipt(receipt)}, "revision_contract": str(contract)})
    return path


def native_video(duration):
    return {"codec_name": "h264", "profile": "High", "level": 40, "pix_fmt": "yuv420p",
            "width": 1920, "height": 1080, "r_frame_rate": "30/1", "avg_frame_rate": "30/1",
            "time_base": "1/15360", "nb_frames": str(round(duration * 30)), "duration": str(duration)}


@pytest.fixture
def opening(project, monkeypatch, request):
    root = project["root"]
    offset = getattr(request, "param", Fraction(1))
    intro_frames, intro_samples = int(offset * 30), int(offset * 48000)
    folder, report = captioned_candidate(project)
    caption_review = root / "caption-review.json"
    write(caption_review, report)
    playback = root / "body-playback"
    subject.unit.release_captioned(folder, caption_review, playback)
    body = playback / "captioned.mp4"
    intro = root / "intro.mp4"
    intro.write_bytes(b"hash-only opening fixture")
    plan = plan_value(root, playback / "delivery.json", body, 8, intro)
    old_run = subject.pilot.run
    old_probe = subject.pilot.probe
    def probe(path):
        value = old_probe(path)
        if Path(path).name == "reference-audio.m4a":
            value["streams"] = [{"codec_type": "audio"}]
        for row in value["streams"]:
            if row["codec_type"] == "audio": row.update(time_base="1/48000", sample_rate="48000", channels=1)
        return value
    monkeypatch.setattr(subject.pilot, "probe", probe)
    def run(command, timeout=180):
        project["calls"].append(command)
        if "-show_frames" in command and "a:0" in command:
            return json.dumps({"frames": [{"pts": 0, "nb_samples": intro_samples + 384000}]})
        if "framehash" in command:
            source = Path(command[command.index("-i") + 1])
            hashes = ["a" * 64] * intro_frames if source == intro else ["b" * 64] * 240
            if source.name == "candidate.mp4": hashes = ["a" * 64] * intro_frames + ["b" * 64] * 240
            assert command[command.index("-enc_time_base:v") + 1] == "demux"
            return "#tb 0: 1/15360\n" + "".join(f"0,{i*512},{i*512},512,100,{digest}\n" for i, digest in enumerate(hashes))
        if "hash" in command and "pcm_s16le" in command:
            source = Path(command[command.index("-i") + 1])
            content = (b"\x10\x00" * 38400 + b"\0" * ((intro_samples - 38400) * 2) + b"\x10\x00" * 384000
                       if source.name in {"reference-audio.m4a", "candidate.mp4"}
                       else b"\x10\x00" * (38400 if source.name == "intro-input.wav" else 384000))
            digest = hashlib.sha256(content).hexdigest()
            return "SHA256=" + digest + "\n"
        if "pcm_s16le" in command:
            if Path(command[-1]).name in {"reference-audio.wav", "candidate-audio.wav"}:
                shutil.copyfile(Path(command[-1]).parent / "mix.wav", Path(command[-1]))
            else:
                pcm(Path(command[-1]), 38400 if Path(command[-1]).name == "intro.wav" else 384000)
        elif "-c:v" in command:
            Path(command[-1]).write_bytes(b"mock stream-copy output")
        else:
            return old_run(command, timeout=timeout)
        return ""
    monkeypatch.setattr(subject.pilot, "run", run)
    monkeypatch.setattr(subject, "_video", lambda path: (
        native_video(float(offset if Path(path) == intro else offset + 8 if Path(path).name == "candidate.mp4" else 8)),
        {"sample_rate": "48000", "channels": 1}, offset if Path(path) == intro else offset + 8 if Path(path).name == "candidate.mp4" else Fraction(8)))
    monkeypatch.setattr(subject.unit, "_frame_pixels", lambda *args: "a" * 64)
    return {**project, "opening_plan": plan, "body_video": body, "intro_video": intro}


def report(stage, current, agent="opening-reviewer", context="opening-review-context"):
    return {"stage": stage, "bindings": current, "status": "pass", "release_authorized": True,
            "reviewer_role": "independent", "reviewer_agent": agent, "reviewer_context": context,
            "blocking_findings": [], "listening_reviewed": False, "listening_status": "not_performed", "student_tested": False}


def pixel(root, video, time, **extra):
    path = root / "test-only-pixel.png"
    if not path.exists(): path.write_bytes(b"mock pixels; actual extraction tested separately")
    return {"path": str(path), "sha256": subject.common.sha(path), "video_sha256": subject.common.sha(video),
            "time": time, "finding": "Synthetic current frame evidence", **extra}


def opening_report(source):
    value = report("opening", subject.opening_bindings(source["opening_plan"]))
    evidence = [pixel(source["root"], source["intro_video"], time, subject=identity)
                for identity, time in (("title", 0), ("question", 0), ("c1", .1), ("c2", .5))]
    value["checks"] = {name: {"status": "pass", "evidence": copy.deepcopy(evidence if name != "timing" else evidence[2:])}
                       for name in ("pixels", "script", "timing")}
    return value


def make_candidate(source):
    path = source["root"] / "opening-review.json"
    write(path, opening_report(source))
    output = source["root"] / "with-opening"
    subject.candidate(source["opening_plan"], path, output)
    return output


def final_reports(source, folder):
    current = subject.bindings(folder)
    offset = current["opening_bindings"]["intro_duration"]
    result = report("content_regression", current, "comparison-reviewer", "comparison-context")
    evidence = []
    for phase, time in (("before", .1), ("during", 3), ("after", 7)):
        evidence.append(pixel(source["root"], folder / "candidate.mp4", time + offset, phase=phase,
                              baseline=pixel(source["root"], source["body_video"], time)))
    result["units"] = [{"id": "cue1", "features": [{"id": "movement", "outcome": "retained", "evidence": evidence}]}]
    final = report("opening_final", current)
    first_caption = subject.common.read_json(source["root"] / "candidate/captions.json")["events"][0]
    body_caption_time = offset + (first_caption["start_cs"] + first_caption["end_cs"]) / 200
    final["checks"] = {"seam": {"status": "pass", "evidence": [
        pixel(source["root"], folder / "candidate.mp4", time, phase=phase)
        for phase, time in (("before", offset - .1), ("during", offset), ("after", offset + .1))]},
        "captions": {"status": "pass", "evidence": [
            pixel(source["root"], folder / "candidate.mp4", time, subject=identity)
            for identity, time in (("c1", .1), ("c2", .5), ("body", body_caption_time))]}}
    return result, final


def save_reports(source, comparison, final):
    paths = source["root"] / "comparison.json", source["root"] / "final.json"
    for path, value in zip(paths, (comparison, final)): write(path, value)
    return paths


def test_gated_preview_preserves_body_and_calls_actual_regression(opening, monkeypatch):
    folder = make_candidate(opening)
    assert not (folder / "delivery.json").exists()
    proof = subject.common.read_json(folder / "preservation.json")
    assert proof["video"]["body_frame_offset"] == 30
    assert proof["video"]["body_pixels_sha256"] == proof["video"]["candidate_suffix_pixels_sha256"]
    assert proof["audio"]["body"] == proof["audio"]["candidate_pcm_suffix"]
    assert proof["audio"]["intro_tail_silence_samples"] == 9600
    original = opening["body_video"].read_bytes()
    calls = []
    validate = subject.regression.validate_comparison
    monkeypatch.setattr(subject.regression, "validate_comparison", lambda *args: calls.append(args) or validate(*args))
    reviews = save_reports(opening, *final_reports(opening, folder))
    output = opening["root"] / "release"
    result = subject.release(folder, *reviews, output)
    assert calls and calls[0][2] == subject.bindings(folder)
    assert result["listening_status"] == "not_performed" and result["body_listening_reviewed"] is False
    assert {path.name for path in output.iterdir()} == {"lesson.mp4", "delivery.json"}
    assert (output / "lesson.mp4").read_bytes() == (folder / "candidate.mp4").read_bytes()
    assert original == opening["body_video"].read_bytes()
    commands = [command for command in opening["calls"] if "-c:v" in command and folder in Path(command[-1]).parents]
    assert len(commands) == 2 and all(command[command.index("-c:v") + 1] == "copy" for command in commands)
    assert all(flag not in command for command in commands for flag in ("-t", "-shortest", "-vf", "-af", "-r"))
    with pytest.raises(FileExistsError): subject.release(folder, *reviews, output)
    with pytest.raises(FileExistsError): subject.candidate(opening["opening_plan"], opening["root"] / "opening-review.json", folder)


@pytest.mark.parametrize("opening", [Fraction(308, 30)], indirect=True)
def test_nonterminating_308_frame_seam_accepts_its_json_numeric_timestamp(opening):
    folder = make_candidate(opening)
    reviews = save_reports(opening, *final_reports(opening, folder))
    subject._final_reviews(folder, *reviews, subject.bindings(folder))


@pytest.mark.parametrize("mutation", ["identity", "context", "bindings", "script", "pixels", "timing", "listening", "pixel_sha", "pixel_video"])
def test_opening_gate_before_any_concat(opening, mutation):
    value = opening_report(opening)
    if mutation == "identity": value["reviewer_agent"] = "opening-author"
    if mutation == "context": value["reviewer_context"] = "opening-author-context"
    if mutation == "bindings": value["bindings"] = {}
    if mutation in {"script", "pixels", "timing"}: value["checks"][mutation]["evidence"].pop()
    if mutation == "listening": value["listening_reviewed"] = True
    if mutation == "pixel_sha": value["checks"]["pixels"]["evidence"][0]["sha256"] = "0" * 64
    if mutation == "pixel_video": value["checks"]["pixels"]["evidence"][0]["video_sha256"] = "0" * 64
    path = opening["root"] / "bad-opening-review.json"
    write(path, value)
    output = opening["root"] / "denied"
    with pytest.raises(ValueError): subject.candidate(opening["opening_plan"], path, output)
    assert not output.exists()


@pytest.mark.parametrize("mutation", ["lost", "missing", "terminal", "author", "opening_context", "final_context", "stale", "baseline", "offset", "seam", "captions",
                                     "c1_in_body", "c2_in_body", "c1_wrong_clause", "body_in_intro", "body_without_caption"])
def test_release_needs_existing_regression_gate_and_separate_current_pixel_review(opening, mutation):
    folder = make_candidate(opening)
    comparison, final = final_reports(opening, folder)
    feature = comparison["units"][0]["features"][0]
    if mutation == "lost": feature["outcome"] = "lost"
    if mutation == "missing": comparison["units"] = []
    if mutation == "terminal": feature["evidence"] = feature["evidence"][-1:]
    if mutation == "author": comparison["reviewer_agent"] = "opening-author"
    if mutation == "opening_context": comparison["reviewer_context"] = "opening-review-context"
    if mutation == "final_context": final["reviewer_context"] = comparison["reviewer_context"]
    if mutation == "stale": comparison["bindings"] = {}
    if mutation == "baseline": feature["evidence"][0]["baseline"]["video_sha256"] = "0" * 64
    if mutation == "offset": feature["evidence"][0]["time"] += .1
    if mutation == "seam": final["checks"]["seam"]["evidence"].pop()
    if mutation == "captions": final["checks"]["captions"]["evidence"].pop()
    if mutation == "c1_in_body": final["checks"]["captions"]["evidence"][0]["time"] = 8
    if mutation == "c2_in_body": final["checks"]["captions"]["evidence"][1]["time"] = 8
    if mutation == "c1_wrong_clause": final["checks"]["captions"]["evidence"][0]["time"] = .5
    if mutation == "body_in_intro": final["checks"]["captions"]["evidence"][2]["time"] = .1
    if mutation == "body_without_caption": final["checks"]["captions"]["evidence"][2]["time"] = 8.9
    reviews = save_reports(opening, comparison, final)
    with pytest.raises(ValueError): subject.release(folder, *reviews, opening["root"] / "denied")
    assert not (opening["root"] / "denied").exists()


@pytest.mark.parametrize("which", ["intro", "wav", "receipt", "source", "body", "old_review", "contract", "old_wav"])
def test_original_sources_are_revalidated_not_just_trusted_receipt(opening, which):
    folder = make_candidate(opening)
    plan = subject.common.read_json(opening["opening_plan"])
    paths = {"intro": plan["intro"]["video"]["path"], "wav": plan["intro"]["wav"]["path"],
             "receipt": plan["intro"]["receipt"]["path"], "source": plan["intro"]["sources"][0]["path"],
             "body": opening["body_video"], "old_review": opening["root"] / "caption-review.json",
             "contract": plan["revision_contract"], "old_wav": opening["speech"] / "U1.wav"}
    path = Path(paths[which])
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises((ValueError, RuntimeError)): subject.bindings(folder)


@pytest.mark.parametrize("name", [*subject.ARTIFACTS, "bindings.json"])
def test_all_candidate_artifacts_and_pcm_are_frozen(opening, name):
    folder = make_candidate(opening)
    path = folder / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError): subject.bindings(folder)


@pytest.mark.parametrize("mutation", ["removed", "pixels", "retimed"])
def test_full_video_suffix_checks_every_frame_and_clock(monkeypatch, mutation):
    intro = [(Fraction(0), Fraction(1, 30), "a" * 64)]
    body = [(Fraction(i, 30), Fraction(1, 30), "b" * 64) for i in range(4)]
    candidate = intro + [(time + Fraction(1, 30), duration, digest) for time, duration, digest in body]
    if mutation == "removed": candidate.pop()
    if mutation == "pixels": candidate[3] = (*candidate[3][:2], "c" * 64)
    if mutation == "retimed": candidate[3] = (candidate[3][0] + Fraction(1, 30), *candidate[3][1:])
    monkeypatch.setattr(subject, "_frames", lambda path: {"i": intro, "b": body, "c": candidate}[path])
    with pytest.raises(ValueError, match="exact untouched suffix"): subject._frame_proof("i", "b", "c")


def test_pcm_no_trimming_speed_gain_or_non_silent_padding(tmp_path):
    pcm(tmp_path / "intro.wav", 48)
    pcm(tmp_path / "body.wav", 96)
    audio = {"sample_rate": "48000"}
    subject._join_pcm(tmp_path, Fraction(1, 500), audio)
    result = subject._audio_proof(tmp_path, audio, Fraction(1, 500))
    assert result["intro_tail_silence_samples"] == 48
    pcm(tmp_path / "mix.wav", 192, byte=b"\x20\x00")
    with pytest.raises(ValueError): subject._audio_proof(tmp_path, audio, Fraction(1, 500))
    with pytest.raises(ValueError, match="trimming"): subject._join_pcm(tmp_path, Fraction(1, 2000), audio)


def test_final_aac_must_be_the_complete_mix_not_only_valid_intermediate_pcm(opening, monkeypatch):
    monkeypatch.setattr(subject, "_mix_aac_hash", lambda _: "b" * 64)
    path = opening["root"] / "opening-review.json"
    write(path, opening_report(opening))
    with pytest.raises(ValueError, match="Candidate AAC"):
        subject.candidate(opening["opening_plan"], path, opening["root"] / "denied-audio")
    assert not (opening["root"] / "denied-audio/bindings.json").exists()


def test_nonzero_audio_origin_is_rejected_without_silently_shifting_the_body(monkeypatch):
    monkeypatch.setattr(subject.pilot, "probe", lambda _: {"format": {"duration": "1"}, "streams": [
        {**native_video(1), "codec_type": "video"},
        {"codec_type": "audio", "codec_name": "aac", "duration": "1", "start_time": "0.02"}]})
    with pytest.raises(ValueError, match="zero-origin AAC"):
        subject._video("test-only-body.mp4")


@pytest.fixture
def actual_media(tmp_path):
    if not Path(subject.pilot.FFMPEG).exists(): pytest.skip("Local ffmpeg unavailable")
    intro, body = tmp_path / "intro.mp4", tmp_path / "body.mp4"
    for path, frames, frequency in ((intro, 30, 440), (body, 39, 660)):
        subject.pilot.run([subject.pilot.FFMPEG, "-v", "error", "-n", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000", "-t", str(frames / 30),
            "-c:v", "libx264", "-profile:v", "high", "-level:v", "4.0", "-pix_fmt", "yuv420p",
            "-video_track_timescale", "15360", "-c:a", "aac", "-ac", "1", path])
    for path in (intro, body):
        video, audio, _ = subject._video(path)
        assert video["profile"] == "High" and video["level"] == 40 and video["time_base"] == "1/15360"
    body_path = tmp_path / "delivery.json"
    write(body_path, {"video": str(body)})
    plan = plan_value(tmp_path, body_path, body, 1.3, intro)
    value = subject.common.read_json(plan)
    support = tmp_path / "support"
    support.mkdir()
    (support / "concat.txt").write_text(subject._concat_path(intro) + "duration 1.000000000000\n" + subject._concat_path(body))
    video = support / "video.mp4"
    subject.pilot.run([subject.pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-f", "concat", "-safe", "0",
                      "-i", support / "concat.txt", "-map", "0:v:0", "-an", "-c:v", "copy", video])
    subject._decode_pcm(value["intro"]["wav"]["path"], support / "intro.wav", audio)
    subject._decode_pcm(body, support / "body.wav", audio)
    subject._join_pcm(support, Fraction(1), audio)
    target = tmp_path / "candidate.mp4"
    subject.pilot.run([subject.pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-i", video, "-i", support / "mix.wav",
                      "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", target])
    subject._reference_audio(support, audio, target)
    return {"intro": intro, "body": body, "target": target, "support": support,
            "audio": audio, "intro_wav": value["intro"]["wav"]["path"]}


def test_real_ffmpeg_high40_tbn15360_video_copy_and_complete_pcm(actual_media):
    intro, body, target = (actual_media[key] for key in ("intro", "body", "target"))
    proof = subject._frame_proof(intro, body, target)
    assert proof["intro_frames"] == 30 and proof["body_frames"] == 39 and proof["candidate_frames"] == 69
    assert proof["body_clock_sha256"] == proof["candidate_suffix_clock_sha256"]
    assert subject._audio_proof(actual_media["support"], actual_media["audio"], Fraction(1), body_source=body,
                               intro_source=actual_media["intro_wav"], candidate_source=target)["candidate_pcm_suffix"] == subject._pcm(actual_media["support"] / "body.wav")
    subject._video(target)
    subject.captions._decode(target)


@pytest.mark.parametrize("mutation", ["wrong_track", "trimmed_track"])
def test_real_ffmpeg_rejects_wrong_or_trimmed_current_final_aac(actual_media, tmp_path, mutation):
    target = tmp_path / "wrong-audio.mp4"
    inputs = (["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=2.3"] if mutation == "wrong_track"
              else ["-i", actual_media["support"] / "mix.wav"])
    trim = ["-af", "atrim=end=2.25"] if mutation == "trimmed_track" else []
    subject.pilot.run([subject.pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-i", actual_media["target"],
                      *inputs, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", *trim,
                      "-c:a", "aac", "-b:a", "192k", target])
    subject._video(target)  # Duration/decodability alone intentionally cannot catch this.
    subject.captions._decode(target)
    subject._frame_proof(actual_media["intro"], actual_media["body"], target)
    with pytest.raises(ValueError, match="Candidate AAC"):
        subject._audio_proof(actual_media["support"], actual_media["audio"], Fraction(1),
                             body_source=actual_media["body"], intro_source=actual_media["intro_wav"], candidate_source=target)


def test_real_ffmpeg_rejects_subframe_jitter_in_original_15360_clock(actual_media, tmp_path):
    target = tmp_path / "subframe-jitter.mp4"
    subject.pilot.run([subject.pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-i", actual_media["target"],
                      "-map", "0:v:0", "-map", "0:a:0", "-c", "copy", "-bsf:v",
                      "setts=pts='if(eq(PTS,22528),PTS+200,PTS)'", target])
    def timestamps(path):
        value = json.loads(subject.pilot.run([subject.pilot.FFPROBE, "-v", "error", "-select_streams", "v:0",
                          "-show_frames", "-show_entries", "frame=pts", "-of", "json", path]))
        return [row["pts"] for row in value["frames"]]
    original, jittered = timestamps(actual_media["target"]), timestamps(target)
    assert 22528 in original and 22728 in jittered
    assert [(before, after) for before, after in zip(original, jittered) if before != after] == [(22528, 22728)]
    assert subject.pilot.probe(target)["streams"][0]["time_base"] == "1/15360"
    subject._video(target)
    with pytest.raises(ValueError, match="discontinuous|exact untouched suffix"):
        subject._frame_proof(actual_media["intro"], actual_media["body"], target)


@pytest.mark.parametrize("seek", ["0.005", "0.01", "0.02", "0.05"])
def test_real_ffmpeg_rejects_equal_payload_edit_list_sample_loss(actual_media, tmp_path, seek):
    target = tmp_path / "edit-list-trim.mp4"
    subject.pilot.run([subject.pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-i", actual_media["support"] / "video.mp4",
                      "-ss", seek, "-i", actual_media["target"], "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", target])
    subject._video(target)
    subject.captions._decode(target)
    subject._frame_proof(actual_media["intro"], actual_media["body"], target)
    assert subject.captions._audio_hash(target) == subject.captions._audio_hash(actual_media["target"])
    presented = tmp_path / "trimmed-presentation.wav"
    subject._decode_pcm(target, presented, actual_media["audio"])
    assert subject._pcm(presented)["samples"] == subject._pcm(actual_media["support"] / "candidate-audio.wav")["samples"] - round(float(seek) * 48000)
    with pytest.raises(ValueError, match="AAC presentation"):
        subject._audio_proof(actual_media["support"], actual_media["audio"], Fraction(1),
                             body_source=actual_media["body"], intro_source=actual_media["intro_wav"], candidate_source=target)


@pytest.mark.parametrize("command, flags", [
    ("opening-bindings", ["--plan", "p"]), ("require-opening-review", ["--plan", "p", "--review", "r"]),
    ("candidate", ["--plan", "p", "--review", "r", "--output", "o"]), ("bindings", ["--candidate", "c"]),
    ("release", ["--candidate", "c", "--regression-review", "g", "--final-review", "f", "--output", "o"])])
def test_cli_dispatch(monkeypatch, capsys, command, flags):
    calls = []
    monkeypatch.setattr(subject, command.replace("-", "_"), lambda **kwargs: calls.append(kwargs) or {"ok": True})
    subject.main([command, *flags])
    assert calls and '"ok": true' in capsys.readouterr().out
