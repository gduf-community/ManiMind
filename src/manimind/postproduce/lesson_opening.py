"""Supervised opening extension of an already released continuous-unit lesson.

No authoring, TTS, body editing or legacy publisher changes. Project plans and
baseline inventories are long lived; independent reports/frames are session
evidence; candidate PCM and copied media are create-only output artifacts.
Every consumer revalidates provenance. Identity fields are attestations, not an
authentication service; actual independent viewing/listening is still required.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import wave

from manimind.review import content_regression as regression
from . import focus_captions as captions, pilot, preset_audition as common
from . import unit_film as unit


CONTRACT = "supervised-lesson-opening-v1"
SCRIPT_FIELDS = ("title", "question", "text", "subtitle_clauses")
ARTIFACTS = ("candidate.json", "candidate.mp4", "preservation.json", "support/concat.txt",
             "support/video.mp4", "support/intro.wav", "support/body.wav", "support/mix.wav",
             "support/reference-audio.m4a", "support/reference-audio.wav", "support/candidate-audio.wav")


def _receipt(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": common.sha(path)}


def _bound(row):
    if (not isinstance(row, dict) or not isinstance(row.get("path"), str)
            or not Path(row["path"]).is_absolute() or _receipt(row["path"]) != row):
        raise ValueError("Require an unchanged absolute path/sha256 receipt")
    return Path(row["path"]).resolve()


def _number(value):
    if not regression.finite(value):
        raise ValueError("Require a finite numeric time")
    return Fraction(str(value))


def _body(path):
    """Re-run the old caption release gates without calling its publisher."""
    delivery = common.read_json(path)
    current = delivery.get("bindings", {})
    folder = Path(current.get("candidate", ""))
    current = unit.caption_bindings(folder)
    manifest = common.read_json(folder / "candidate.json")
    if (delivery.get("source_contract") != unit.units.SOURCE_CONTRACT
            or delivery.get("bindings") != current or delivery.get("caption_status") != "single_burned_set"
            or delivery.get("full_decode_passed") is not True or delivery.get("listening_reviewed") is not False
            or delivery.get("duration") != manifest["duration"]
            or common.sha(delivery["video"]) != delivery.get("sha256")
            or delivery["sha256"] != current["files"]["candidate.mp4"]
            or common.sha(delivery["review"]) != delivery.get("review_sha256")
            or delivery.get("audio_packet_sha256") != manifest["audio_packet_sha256"]):
        raise ValueError("Require the unchanged unit_film.release_captioned body delivery")
    authors, prior = unit._alignment_people(common.read_json(manifest["alignment"]))
    authors.append(unit._identity(manifest, "producer"))
    voiced = common.read_json(manifest["voiced_delivery"])
    prior.append(common.read_json(voiced["review"]))
    report = unit._review(common.read_json(delivery["review"]), "captions", current,
                          authors=authors, prior_reviews=prior)
    captions._caption_review(delivery["review"], current, manifest["producer_agent"])
    if (captions._media(delivery["video"], delivery["duration"]) != manifest["size"]
            or captions._audio_hash(delivery["video"]) != manifest["audio_packet_sha256"]
            or captions._audio_hash(voiced["video"]) != manifest["audio_packet_sha256"]):
        raise ValueError("Body dimensions or original AAC packets changed")
    captions._clean_playback(Path(delivery["video"]).parent, Path(delivery["video"]).name)
    return delivery, authors, [*prior, report]


def _video(path):
    info = pilot.probe(Path(path))
    streams = info["streams"]
    if len(streams) != 2 or sorted(row["codec_type"] for row in streams) != ["audio", "video"]:
        raise ValueError("Require exactly one video and one audio track, no subtitles")
    video = next(row for row in streams if row["codec_type"] == "video")
    audio = next(row for row in streams if row["codec_type"] == "audio")
    if (video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p"
            or video.get("disposition", {}).get("attached_pic")
            or Fraction(video["avg_frame_rate"]) != Fraction(video["r_frame_rate"])
            or Fraction(video.get("start_time", "0")) != 0
            or Fraction(audio.get("start_time", "0")) != 0
            or audio.get("codec_name") != "aac"):
        raise ValueError("Require zero-origin CFR H.264/yuv420p and a zero-origin AAC track")
    duration = Fraction(int(video["nb_frames"]), 1) / Fraction(video["r_frame_rate"])
    if duration <= 0:
        raise ValueError("Empty video")
    for row in (info["format"], video, audio):
        if abs(Fraction(row["duration"]) - duration) > Fraction(1, 10):
            raise ValueError("Video/audio duration mismatch")
    return video, audio, duration


def _plan(path):
    value = common.read_json(path)
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Unknown opening plan schema")
    unit._identity(value, "author")
    body, authors, prior = _body(_bound(value["body_delivery"]))
    intro = value["intro"]
    for key in ("video", "wav", "receipt"):
        _bound(intro[key])
    if not isinstance(intro.get("sources"), list) or not intro["sources"]:
        raise ValueError("Declare opening authoring sources")
    paths = [_bound(row) for row in intro["sources"]]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate opening sources")
    receipt = common.read_json(intro["receipt"]["path"])
    script = {key: value[key] for key in SCRIPT_FIELDS}
    if (receipt.get("schema_version") != 1 or unit._identity(receipt, "author") != unit._identity(value, "author")
            or any(receipt.get(key) != intro[key] for key in ("video", "wav", "sources"))
            or receipt.get("script") != script):
        raise ValueError("Opening receipt, original author, sources or script changed")
    for key in ("title", "question", "text"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError("Opening title, question and text are required")
        captions._text(value[key])
    iv, _, duration = _video(intro["video"]["path"])
    bv, ba, body_duration = _video(body["video"])
    keys = ("codec_name", "profile", "level", "pix_fmt", "width", "height", "time_base", "r_frame_rate", "sample_aspect_ratio")
    if any(iv.get(key) != bv.get(key) for key in keys):
        raise ValueError("Opening/body video streams are incompatible; fix only the opening")
    if abs(body_duration - _number(body["duration"])) > Fraction(1, 1000):
        raise ValueError("Body frame clock differs from published duration")
    clauses, seen, end = value["subtitle_clauses"], set(), Fraction(0)
    if not isinstance(clauses, list) or not clauses:
        raise ValueError("Require timed subtitle clauses")
    for row in clauses:
        if (not regression.safe_id(row.get("id")) or row["id"] in seen or row["id"] in {"title", "question", "body"}
                or not isinstance(row.get("text"), str) or not row["text"].strip()
                or not end <= _number(row["start"]) < _number(row["end"]) <= duration):
            raise ValueError("Require unique ordered, nonoverlapping in-opening clauses")
        captions._text(row["text"])
        seen.add(row["id"])
        end = _number(row["end"])
    if "".join(row["text"] for row in clauses) != value["text"]:
        raise ValueError("Subtitle clauses must preserve the entire opening text")
    with wave.open(intro["wav"]["path"], "rb") as wav:
        if (wav.getcomptype() != "NONE" or wav.getnframes() <= 0
                or Fraction(wav.getnframes(), wav.getframerate()) > duration):
            raise ValueError("Opening WAV must be intact PCM and fit the visual clock; never trim it")
        if end > Fraction(wav.getnframes(), wav.getframerate()):
            raise ValueError("Caption clauses exceed the complete opening WAV")
    contract_path = Path(value["revision_contract"])
    if not contract_path.is_absolute():
        raise ValueError("revision_contract must be an absolute path")
    contract, contract_hashes = regression.contract_bindings(contract_path, pilot.ROOT)
    if (set(contract["assets"]) != {"body"}
            or Path(pilot.ROOT / contract["assets"]["body"]["path"]).resolve() != Path(body["video"]).resolve()
            or contract["assets"]["body"]["sha256"] != body["sha256"]
            or _number(contract["assets"]["body"]["duration"]) != _number(body["duration"])):
        raise ValueError("The task-selected baseline must be this complete released body")
    return value, body, authors, prior, duration, bv, ba, contract_hashes


def opening_bindings(plan):
    plan = Path(plan).resolve()
    value, body, _, _, duration, _, _, hashes = _plan(plan)
    return {"stage": "opening", "source_contract": CONTRACT, "plan": _receipt(plan),
            "publisher_sha256": common.sha(__file__), "body_publisher_sha256": common.sha(unit.__file__),
            "caption_tools_sha256": common.sha(captions.__file__), "body_bindings": body["bindings"],
            "body_video_sha256": body["sha256"], "intro": value["intro"],
            "intro_duration": float(duration), **hashes}


def _review(path, stage, current, authors, *, separate=()):
    value = common.read_json(path)
    reviewer = unit._identity(value, "reviewer")
    if (value.get("stage") != stage or value.get("bindings") != current
            or value.get("status") != "pass" or value.get("release_authorized") is not True
            or value.get("reviewer_role") != "independent" or value.get("blocking_findings") != []
            or type(value.get("listening_reviewed")) is not bool or value.get("student_tested") is not False
            or value.get("listening_status") != ("performed" if value["listening_reviewed"] else "not_performed")
            or (not value["listening_reviewed"] and any(value.get(key, False) is not False for key in
                                                       ("naturalness_approved", "pronunciation_approved")))
            or any(value.get(key, False) is not False for key in ("asr_accuracy_certified", "pronunciation_certified"))):
        raise ValueError("Require a current independent stage approval with honest evidence scope")
    if (any(reviewer[0] == person[0] or reviewer[1] == person[1] for person in authors)
            or any(reviewer[1] == unit._identity(report, "reviewer")[1] for report in separate)):
        raise ValueError("Author self-review or reused comparison context is forbidden")
    return value


def _pixel(item, video, duration):
    if (not isinstance(item.get("finding"), str) or not item["finding"].strip()
            or not 0 <= _number(item.get("time")) < duration
            or item.get("video_sha256") != common.sha(video)):
        raise ValueError("Require in-range actual video-bound pixel observations")
    _bound({"path": item.get("path"), "sha256": item.get("sha256")})
    if unit._frame_pixels(item["path"]) != unit._frame_pixels(video, item["time"]):
        raise ValueError("Review frame does not contain the cited current video pixels")


def _check(report, name):
    check = report.get("checks", {}).get(name, {})
    rows = check.get("evidence")
    if (check.get("status") != "pass" or not isinstance(rows, list) or not rows
            or any(not isinstance(row, dict) or not isinstance(row.get("finding"), str)
                   or not row["finding"].strip() for row in rows)):
        raise ValueError(f"Require actual structured review evidence: {name}")
    return rows


def require_opening_review(plan, review):
    current = opening_bindings(plan)
    value, body, authors, _, duration, _, _, _ = _plan(plan)
    authors.append(unit._identity(value, "author"))
    report = _review(review, "opening", current, authors)
    clauses = {row["id"]: row for row in value["subtitle_clauses"]}
    for name in ("pixels", "script", "timing") + (("listening",) if report["listening_reviewed"] else ()):
        evidence = _check(report, name)
        expected = set(clauses) | ({"title", "question"} if name in {"pixels", "script"} else set())
        if {row.get("subject") for row in evidence} != expected:
            raise ValueError(f"Opening {name} review must cover every declared subject")
        for item in evidence:
            time = _number(item.get("time"))
            if not 0 <= time < duration:
                raise ValueError("Opening evidence time outside the current intro")
            clause = clauses.get(item["subject"])
            if clause and not _number(clause["start"]) <= time < _number(clause["end"]):
                raise ValueError("Clause evidence time outside its declared interval")
            if name == "pixels":
                _pixel(item, value["intro"]["video"]["path"], duration)
    if opening_bindings(plan) != current:
        raise ValueError("Opening inputs changed during review validation")
    return report


def _frames(path):
    # ffmpeg decodes every frame; aggregate hashes are persisted, not huge logs.
    result = pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", path,
                        "-map", "0:v:0", "-an", "-fps_mode", "passthrough", "-pix_fmt", "yuv420p",
                        "-enc_time_base:v", "demux", "-f", "framehash", "-hash", "sha256", "-"], timeout=1800)
    match = re.search(r"^#tb 0: (\d+/\d+)$", result, re.M)
    if not match:
        raise ValueError("Missing decoded frame time base")
    clock = Fraction(match[1])
    if clock != Fraction(_video(path)[0]["time_base"]):
        raise ValueError("Decoded frame hashes must retain the original demux time base")
    rows = []
    for line in result.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 6 or fields[0] != "0" or not re.fullmatch(r"[a-fA-F0-9]{64}", fields[-1]):
            raise ValueError("Malformed decoded frame fingerprint")
        rows.append((int(fields[2]) * clock, int(fields[3]) * clock, fields[-1].lower()))
    if not rows or rows[0][0] != 0 or any(b[0] != a[0] + a[1] for a, b in zip(rows, rows[1:])):
        raise ValueError("Empty, nonzero-origin or discontinuous decoded frame clock")
    return rows


def _frame_proof(intro, body, candidate):
    opening, original, combined = _frames(intro), _frames(body), _frames(candidate)
    offset = opening[-1][0] + opening[-1][1]
    expected = opening + [(pts + offset, duration, digest) for pts, duration, digest in original]
    if combined != expected:
        raise ValueError("Full decoded video frames/timing differ: body must be an exact untouched suffix")
    def digest(rows):
        return hashlib.sha256("".join(row[2] for row in rows).encode("ascii")).hexdigest()
    def clock_digest(rows, start):
        return hashlib.sha256("".join(f"{pts-start},{duration}\n" for pts, duration, _ in rows).encode("ascii")).hexdigest()
    suffix = combined[len(opening):]
    return {"intro_frames": len(opening), "body_frames": len(original), "candidate_frames": len(combined),
            "body_frame_offset": len(opening), "body_time_offset": float(offset),
            "body_pixels_sha256": digest(original), "candidate_suffix_pixels_sha256": digest(suffix),
            "body_clock_sha256": clock_digest(original, 0), "candidate_suffix_clock_sha256": clock_digest(suffix, offset)}


def _pcm(path, *, start=0):
    digest, count = hashlib.sha256(), 0
    with wave.open(str(path), "rb") as wav:
        params = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
        if start > wav.getnframes():
            raise ValueError("PCM suffix starts beyond the complete track")
        wav.setpos(start)
        while chunk := wav.readframes(65536):
            digest.update(chunk)
            count += len(chunk) // (params[0] * params[1])
    return {"channels": params[0], "sample_width": params[1], "sample_rate": params[2],
            "samples": count, "pcm_sha256": digest.hexdigest()}


def _source_pcm_hash(path, audio):
    result = pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", path, "-map", "0:a:0", "-vn",
                        "-ar", str(audio["sample_rate"]), "-ac", str(audio["channels"]),
                        "-c:a", "pcm_s16le", "-f", "hash", "-hash", "sha256", "-"], timeout=1800)
    match = re.fullmatch(r"SHA256=([a-fA-F0-9]{64})\s*", result)
    if not match:
        raise ValueError("Missing complete source PCM fingerprint")
    return match[1].lower()


def _mix_aac_hash(path):
    # An independent encode fingerprint verifies the output audio, not listening.
    result = pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", path, "-map", "0:a:0",
                        "-c:a", "aac", "-b:a", "192k", "-f", "streamhash", "-hash", "sha256", "-"], timeout=1800)
    match = re.fullmatch(r"0,a,SHA256=([a-fA-F0-9]{64})\s*", result)
    if not match:
        raise ValueError("Missing independently encoded full-mix AAC fingerprint")
    return match[1].lower()


def _audio_clock(path):
    audio = next(row for row in pilot.probe(Path(path))["streams"] if row["codec_type"] == "audio")
    clock, rate = Fraction(audio["time_base"]), int(audio["sample_rate"])
    frames = json.loads(pilot.run([pilot.FFPROBE, "-v", "error", "-select_streams", "a:0", "-show_frames",
                         "-show_entries", "frame=pts,nb_samples", "-of", "json", path], timeout=1800))["frames"]
    digest, end, count = hashlib.sha256(), Fraction(0), 0
    for row in frames:
        pts, samples = int(row["pts"]) * clock, int(row["nb_samples"])
        if pts != end or samples <= 0:
            raise ValueError("AAC presented sample clock must start at zero and remain continuous")
        digest.update(f"{pts},{samples}\n".encode("ascii"))
        end, count = pts + Fraction(samples, rate), count + samples
    if not count:
        raise ValueError("Empty AAC presentation")
    return {"samples": count, "sample_rate": rate, "end": str(end), "clock_sha256": digest.hexdigest()}


def _reference_audio(support, audio, candidate):
    reference = support / "reference-audio.m4a"
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-i", support / "mix.wav", "-map", "0:a:0",
               "-c:a", "aac", "-b:a", "192k", "-map_metadata", "-1", "-map_chapters", "-1",
               "-movflags", "+faststart", reference], timeout=1800)
    _decode_pcm(reference, support / "reference-audio.wav", audio)
    _decode_pcm(candidate, support / "candidate-audio.wav", audio)


def _audio_proof(support, body_audio, offset, *, body_source=None, intro_source=None, candidate_source=None):
    intro, body, mix = (_pcm(support / name) for name in ("intro.wav", "body.wav", "mix.wav"))
    samples = offset * int(body_audio["sample_rate"])
    if samples.denominator != 1 or intro["samples"] > samples:
        raise ValueError("Opening PCM cannot fit the exact video seam without trimming")
    samples = int(samples)
    suffix = _pcm(support / "mix.wav", start=samples)
    if suffix != body or mix["samples"] != samples + body["samples"]:
        raise ValueError("Complete decoded body PCM is not the unchanged mix suffix")
    for path, decoded in ((body_source, body), (intro_source, intro)):
        if path is not None and _source_pcm_hash(path, body_audio) != decoded["pcm_sha256"]:
            raise ValueError("Archived PCM differs from a full current source decode")
    with wave.open(str(support / "intro.wav"), "rb") as source, wave.open(str(support / "mix.wav"), "rb") as target:
        remaining = source.getnframes()
        while remaining:
            count = min(remaining, 65536)
            if source.readframes(count) != target.readframes(count):
                raise ValueError("Opening PCM prefix changed")
            remaining -= count
        padding = samples - intro["samples"]
        while padding:
            count = min(padding, 65536)
            if any(target.readframes(count)):
                raise ValueError("Opening tail padding is not silence")
            padding -= count
    encoded = {}
    if candidate_source is not None:
        expected, actual = _mix_aac_hash(support / "mix.wav"), captions._audio_hash(candidate_source)
        reference = support / "reference-audio.m4a"
        if expected != actual or captions._audio_hash(reference) != expected:
            raise ValueError("Candidate AAC is not the independently encoded complete PCM mix")
        reference_pcm, actual_pcm = _pcm(support / "reference-audio.wav"), _pcm(support / "candidate-audio.wav")
        if (reference_pcm != actual_pcm
                or _source_pcm_hash(reference, body_audio) != reference_pcm["pcm_sha256"]
                or _source_pcm_hash(candidate_source, body_audio) != actual_pcm["pcm_sha256"]):
            raise ValueError("Candidate AAC presentation differs from the full independently encoded reference")
        reference_clock, actual_clock = _audio_clock(reference), _audio_clock(candidate_source)
        if reference_clock != actual_clock or actual_clock["samples"] != actual_pcm["samples"]:
            raise ValueError("Candidate AAC presentation clock differs from the complete reference")
        encoded = {"expected_mix_aac_packet_sha256": expected, "candidate_aac_packet_sha256": actual,
                   "reference_presented_pcm": reference_pcm, "candidate_presented_pcm": actual_pcm,
                   "reference_presentation_clock": reference_clock, "candidate_presentation_clock": actual_clock}
    return {"mode": "complete_pcm_then_single_aac_encode", "body_input_preserved": True, **encoded,
            "intro": intro, "body": body, "mix": mix, "body_pcm_sample_offset": samples,
            "intro_tail_silence_samples": samples - intro["samples"], "candidate_pcm_suffix": suffix,
            "body_gain_db": 0, "body_trimmed_samples": 0, "body_speed": 1}


def _decode_pcm(source, target, audio):
    # These are the original body rate/channels. Only the opening may resample.
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-i", source,
               "-map", "0:a:0", "-vn", "-ar", str(audio["sample_rate"]), "-ac", str(audio["channels"]),
               "-c:a", "pcm_s16le", target], timeout=1800)


def _join_pcm(support, offset, audio):
    count = offset * int(audio["sample_rate"])
    if count.denominator != 1:
        raise ValueError("Video seam must land on an audio sample")
    with wave.open(str(support / "intro.wav"), "rb") as opening, wave.open(str(support / "body.wav"), "rb") as body:
        if opening.getparams()[:3] != body.getparams()[:3] or opening.getnframes() > count:
            raise ValueError("PCM formats differ or opening requires trimming")
        with wave.open(str(support / "mix.wav"), "wb") as output:
            output.setparams(body.getparams())
            while chunk := opening.readframes(65536):
                output.writeframesraw(chunk)
            remaining = int(count) - opening.getnframes()
            while remaining:
                size = min(remaining, 65536)
                output.writeframesraw(b"\0" * size * body.getnchannels() * body.getsampwidth())
                remaining -= size
            while chunk := body.readframes(65536):
                output.writeframesraw(chunk)


def _concat_path(path):
    name = str(Path(path).resolve())
    if "\n" in name or "\r" in name:
        raise ValueError("Newlines are not supported in concat paths")
    return "file '" + name.replace("'", "'\\''") + "'\n"


def candidate(plan, review, output):
    output = unit._fresh(output)
    plan, review = Path(plan).resolve(), Path(review).resolve()
    require_opening_review(plan, review)
    current, review_receipt = opening_bindings(plan), _receipt(review)
    value, body, _, _, offset, _, audio, _ = _plan(plan)
    output.mkdir(parents=True, exist_ok=False)
    support = output / "support"
    support.mkdir()
    with (support / "concat.txt").open("x", encoding="utf-8") as stream:
        stream.write(_concat_path(value["intro"]["video"]["path"]))
        stream.write(f"duration {float(offset):.12f}\n")
        stream.write(_concat_path(body["video"]))
    video = support / "video.mp4"
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-f", "concat", "-safe", "0",
               "-i", support / "concat.txt", "-map", "0:v:0", "-an", "-c:v", "copy",
               "-map_metadata", "-1", "-map_chapters", "-1", video], timeout=1800)
    _decode_pcm(value["intro"]["wav"]["path"], support / "intro.wav", audio)
    _decode_pcm(body["video"], support / "body.wav", audio)
    _join_pcm(support, offset, audio)
    target = output / "candidate.mp4"
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-n", "-i", video, "-i", support / "mix.wav",
               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-map_metadata", "-1", "-map_chapters", "-1", "-sn", "-dn", "-movflags", "+faststart", target], timeout=1800)
    _reference_audio(support, audio, target)
    _video(target)
    captions._decode(target)
    proof = {"video": _frame_proof(value["intro"]["video"]["path"], body["video"], target),
             "audio": _audio_proof(support, audio, offset, body_source=body["video"],
                                   intro_source=value["intro"]["wav"]["path"], candidate_source=target), "body_input": _receipt(body["video"]),
             "intro_wav_input": value["intro"]["wav"], "full_decode_passed": True}
    if proof["video"]["body_time_offset"] != float(offset):
        raise ValueError("Actual seam differs from the approved opening clock")
    unit._write(output / "preservation.json", proof)
    if opening_bindings(plan) != current or _receipt(review) != review_receipt:
        raise ValueError("Opening sources/review changed during concatenation")
    unit._write(output / "candidate.json", {"source_contract": CONTRACT, "status": "candidate_not_released",
                "plan": str(plan), "opening_bindings": current, "opening_review": review_receipt,
                "duration": float(offset) + body["duration"], "body_duration": body["duration"],
                "author_agent": value["author_agent"], "author_context": value["author_context"],
                **unit._state("Supervised opening concatenator", ["regression reviewer", "final pixel/listening reviewer", "publisher"],
                              "Create-only candidate; never itself a release", "Any plan, source, code, PCM, media or approval change")})
    result = _bindings(output)
    unit._write(output / "bindings.json", result)
    return result


def _bindings(folder):
    folder = Path(folder).resolve()
    allowed = {"support", "candidate.json", "candidate.mp4", "preservation.json", "bindings.json"}
    if any(path.name not in allowed for path in folder.iterdir()):
        raise ValueError("Unbound files or auto-loaded subtitle sidecars in candidate")
    value = common.read_json(folder / "candidate.json")
    if value.get("source_contract") != CONTRACT or value.get("status") != "candidate_not_released":
        raise ValueError("Require a new opening candidate")
    current = opening_bindings(value["plan"])
    if (value["opening_bindings"] != current or _receipt(_bound(value["opening_review"])) != value["opening_review"]
            or unit._identity(value, "author") != unit._identity(common.read_json(value["plan"]), "author")):
        raise ValueError("Candidate opening sources, original identity or approval changed")
    require_opening_review(value["plan"], value["opening_review"]["path"])
    expected = current["intro_duration"] + value["body_duration"]
    if (value["duration"] != expected
            or value["body_duration"] != common.read_json(common.read_json(value["plan"])["body_delivery"]["path"])["duration"]):
        raise ValueError("Candidate duration/source clock changed")
    return {"stage": "lesson_opening_candidate", "source_contract": CONTRACT, "candidate": str(folder),
            "opening_bindings": current, "files": {name: common.sha(folder / name) for name in ARTIFACTS}}


def bindings(candidate):
    result = _bindings(candidate)
    frozen = Path(candidate) / "bindings.json"
    if (common.read_json(frozen) != result
            or frozen.read_text(encoding="utf-8") != json.dumps(result, ensure_ascii=False, indent=2)):
        raise ValueError("Frozen candidate bindings changed; reviews are stale")
    return result


def _final_reviews(folder, comparison, final, current):
    manifest = common.read_json(folder / "candidate.json")
    value, body, authors, _, offset, _, _, _ = _plan(manifest["plan"])
    authors.append(unit._identity(value, "author"))
    opening = require_opening_review(manifest["plan"], manifest["opening_review"]["path"])
    final_report = _review(final, "opening_final", current, authors)
    report = _review(comparison, "content_regression", current, authors,
                     separate=[opening, final_report])
    contract, _ = regression.contract_bindings(value["revision_contract"], pilot.ROOT)
    regression.validate_comparison(report, contract, current, manifest["duration"])
    video = folder / "candidate.mp4"
    for row in report["units"]:
        selected = next(item for item in contract["units"] if item["id"] == row["id"])
        for feature in row["features"]:
            for item in feature["evidence"]:
                baseline = item.get("baseline", {})
                _pixel(item, video, _number(manifest["duration"]))
                _pixel(baseline, body["video"], _number(body["duration"]))
                if (not _number(selected["baseline_interval"][0]) <= _number(baseline["time"]) < _number(selected["baseline_interval"][1])
                        or abs(_number(item["time"]) - _number(baseline["time"]) - offset) > Fraction(1, 1000000)):
                    raise ValueError("Regression pixels must compare the selected body interval at the actual intro offset")
    for name in ("seam", "captions") + (("audio_continuity",) if final_report["listening_reviewed"] else ()):
        evidence = _check(final_report, name)
        for item in evidence:
            if name != "audio_continuity":
                _pixel(item, video, _number(manifest["duration"]))
            elif not 0 <= _number(item.get("time")) < _number(manifest["duration"]):
                raise ValueError("Audio seam listening evidence must cite the actual candidate clock")
        if name in {"seam", "audio_continuity"}:
            phases = {item.get("phase"): _number(item.get("time")) for item in evidence}
            if (set(phases) != {"before", "during", "after"} or not phases["before"] < offset
                    or abs(phases["during"] - offset) > Fraction(1, 1000000) or not offset < phases["after"]
                    or offset - phases["before"] > 1 or phases["after"] - offset > 1):
                raise ValueError("Inspect/listen immediately before, at and after the actual seam")
        else:
            subjects = {item.get("subject") for item in evidence}
            if not {"body", *(row["id"] for row in value["subtitle_clauses"])} <= subjects:
                raise ValueError("Final captions require every opening clause and the body after the seam")
            clauses = {row["id"]: row for row in value["subtitle_clauses"]}
            body_captions = common.read_json(Path(body["bindings"]["candidate"]) / "captions.json")["events"]
            for item in evidence:
                time = _number(item["time"])
                clause = clauses.get(item.get("subject"))
                if ((item.get("subject") == "body" and not any(
                        Fraction(event["start_cs"], 100) <= time - offset < Fraction(event["end_cs"], 100)
                        for event in body_captions))
                        or (clause and not _number(clause["start"]) <= time < _number(clause["end"]))):
                    raise ValueError("Final caption pixels must be inside the cited clause/body interval")
    return {"regression_review": _receipt(comparison), "final_review": _receipt(final)}


def release(candidate, regression_review, final_review, output):
    output = unit._fresh(output)
    folder = Path(candidate).resolve()
    current = bindings(folder)
    reviews = _final_reviews(folder, regression_review, final_review, current)
    manifest = common.read_json(folder / "candidate.json")
    value, body, _, _, offset, _, audio, _ = _plan(manifest["plan"])
    video = folder / "candidate.mp4"
    _video(video)
    captions._decode(video)
    actual = {"video": _frame_proof(value["intro"]["video"]["path"], body["video"], video),
              "audio": _audio_proof(folder / "support", audio, offset, body_source=body["video"],
                                    intro_source=value["intro"]["wav"]["path"], candidate_source=video), "body_input": _receipt(body["video"]),
              "intro_wav_input": value["intro"]["wav"], "full_decode_passed": True}
    if actual != common.read_json(folder / "preservation.json"):
        raise ValueError("Full decoded preservation proof changed")
    if bindings(folder) != current or _final_reviews(folder, regression_review, final_review, current) != reviews:
        raise ValueError("Candidate or independent review changed during verification")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "lesson.mp4"
    unit._copy(video, target)
    if (common.sha(target) != current["files"]["candidate.mp4"] or bindings(folder) != current
            or _final_reviews(folder, regression_review, final_review, current) != reviews):
        raise ValueError("Release copy or review/source changed")
    result = {"source_contract": CONTRACT, "video": str(target), "sha256": common.sha(target),
              "duration": manifest["duration"], "bindings": current, **reviews,
              "opening_review": manifest["opening_review"], "body_delivery": value["body_delivery"],
              "preservation": actual, "full_decode_passed": True, "caption_status": "single_burned_set",
              "listening_reviewed": False, "listening_status": "not_performed",
              "scope": "Complete captioned preview awaiting human listening review; technical continuity is not naturalness approval",
              "listening_scope": "No whole-lesson listening approval; stage-specific claims remain in original reports",
              "body_listening_reviewed": body["listening_reviewed"], "student_tested": False,
              **unit._state("Supervised opening publisher", ["viewer", "auditor"], "Create-only copied release",
                            "Any bound input, source, media, code, pixel evidence or independent report change")}
    unit._write(output / "delivery.json", result)
    captions._clean_playback(output, target.name)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("opening-bindings", "require-opening-review", "candidate", "bindings", "release"):
        command = sub.add_parser(name)
        for flag in ({"opening-bindings": ("plan",), "require-opening-review": ("plan", "review"),
                      "candidate": ("plan", "review", "output"), "bindings": ("candidate",),
                      "release": ("candidate", "regression-review", "final-review", "output")}[name]):
            command.add_argument("--" + flag, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command").replace("-", "_")
    print(json.dumps(globals()[command](**args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
