"""Single-line burned caption candidates; independent caption review gates release."""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from pathlib import Path
import re
import shutil
import unicodedata

from . import pilot, preset_audition as common, understanding_film as film


DEFAULT_STYLE = {"fontname": "PingFang SC", "fontsize": 40, "margin_v": 24,
                 "outline": 2, "shadow": 0, "max_width": 30}
PUNCTUATION = frozenset("，。！？；：、,.!?;:")
ARTIFACTS = ("candidate.json", "style.json", "captions.json", "support/captions.ass",
             "source-receipts.json", "candidate.mp4")


def _read(path):
    return common.read_json(Path(path))


def _write(path, value):
    common.write_json(Path(path), value)


def _receipt(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "sha256": common.sha(path)}


def validate_style(style=None):
    value = dict(DEFAULT_STYLE)
    if style is not None:
        if not isinstance(style, dict) or set(style) - set(value):
            raise ValueError("Unknown caption style option")
        value.update(style)
    if value["fontname"] not in {"PingFang SC", "Heiti SC", "Arial"}:
        raise ValueError("Unsupported caption fontname")
    limits = {"fontsize": (24, 64), "margin_v": (0, 160), "outline": (0, 4),
              "shadow": (0, 2), "max_width": (8, 30)}
    for key, (low, high) in limits.items():
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError(f"Invalid caption style: {key}")
    return value


def _text(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Caption text must be nonempty")
    if any(unicodedata.category(char) in {"Cc", "Cs"} and char != "\n" for char in text):
        raise ValueError("Caption text contains control characters")
    # Bidi/zero-width format controls are not allowed to hide injected content.
    if any(unicodedata.category(char) == "Cf" for char in text):
        raise ValueError("Caption text contains format controls")
    return text


def escape_ass(text):
    # libass does not decode double backslashes as a single literal backslash.
    # An invisible word joiner prevents source \\N/\\n/\\h from becoming commands.
    return (_text(text).replace("\\", "\\\u2060").replace("{", "\\{")
            .replace("}", "\\}").replace("\n", "\\N"))


def text_width(text):
    """Conservative CJK-cell estimate, not measured font glyph bounds."""
    return sum(0 if unicodedata.combining(char) or char == "\n" else
               2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in text)


def split_text(text, max_width=30):
    _text(text)
    pieces, remaining = [], text
    while remaining:
        if pieces and not remaining.strip():
            pieces[-1] += remaining
            break
        width, stop = 0, 0
        for char in remaining:
            delta = text_width(char)
            if width + delta > max_width * 2:
                break
            width += delta
            stop += 1
            if char == "\n" and remaining[:stop].strip():
                break
        if not stop:
            raise ValueError("Cannot split caption without losing text")
        if stop < len(remaining) and remaining[stop - 1] != "\n":
            boundary = max((i + 1 for i, char in enumerate(remaining[:stop])
                            if char in PUNCTUATION), default=0)
            stop = boundary or stop
        pieces.append(remaining[:stop])
        remaining = remaining[stop:]
    if "".join(pieces) != text:
        raise ValueError("Caption splitting lost text")
    return pieces


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid utterance time")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Invalid utterance time")
    return number


def make_captions(alignment, style=None):
    style = validate_style(style)
    events, previous = [], Decimal(0)
    duration = _number(alignment["duration"])
    if not alignment.get("segments"):
        raise ValueError("Caption alignment is empty")
    for row in alignment["segments"]:
        start, end = _number(row["start"]), _number(row["end"])
        if not previous <= start < end <= duration:
            raise ValueError("Overlapping or out-of-bounds utterance")
        if abs(end - start - _number(row["duration_seconds"])) > Decimal(1) / 48000:
            raise ValueError("Caption interval differs from intact WAV duration")
        previous = end
        parts = split_text(row["text"], style["max_width"])
        first = int((start * 100).to_integral_value(rounding=ROUND_CEILING))
        last = int((end * 100).to_integral_value(rounding=ROUND_FLOOR))
        if last - first < len(parts):
            raise ValueError("Utterance too short for safe ASS centisecond quantization")
        # Inward quantization prevents even one subtitle tick escaping the WAV.
        cursor, count = first, 0
        for index, part in enumerate(parts):
            count += len(part)
            boundary = first + (last - first) * count // len(row["text"])
            boundary = min(last - (len(parts) - index - 1), max(cursor + 1, boundary))
            events.append({"utterance_id": row["id"], "part": index + 1, "text": part,
                           "start_cs": cursor, "end_cs": boundary,
                           "utterance_start": row["start"], "utterance_end": row["end"],
                           "timing": "whole_utterance" if len(parts) == 1 else "character_ratio_approximation"})
            cursor = boundary
    return {"schema_version": 1, "duration": alignment["duration"], "events": events,
            "timing_scope": "Measured whole WAV intervals; split parts use character ratios, not word ASR"}


def _stamp(ticks):
    hours, rest = divmod(ticks, 360000)
    minutes, rest = divmod(rest, 6000)
    seconds, cs = divmod(rest, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{cs:02}"


def make_ass(captions, style, width, height):
    style = validate_style(style)
    header = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\n"
              "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
              "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
              "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
              "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
              f"Style: Default,{style['fontname']},{style['fontsize']},&H00FFFFFF,&H00FFFFFF,&H00000000,"
              f"&H00000000,0,0,0,0,100,100,0,0,1,{style['outline']},{style['shadow']},2,24,24,{style['margin_v']},1\n"
              "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = []
    for event in captions["events"]:
        # A source newline is a boundary, never an extra visible line in an event.
        text = escape_ass(event["text"].strip("\n").replace("\n", " "))
        lines.append(f"Dialogue: 0,{_stamp(event['start_cs'])},{_stamp(event['end_cs'])},Default,,0,0,0,,{text}\n")
    return header + "".join(lines)


def _audio_review(path, expected):
    review = _read(path)
    if (review.get("stage") != "audio_alignment" or review.get("bindings") != expected
            or review.get("status") != "pass" or review.get("reviewer_role") != "independent"
            or not review.get("reviewer_agent") or review.get("release_authorized") is not True
            or review.get("blocking_findings") != [] or review.get("listening_reviewed") is not False):
        raise ValueError("Require the existing independent audio-alignment review")


def _source(alignment_path, delivery_path):
    alignment_path, delivery_path = Path(alignment_path).resolve(), Path(delivery_path).resolve()
    current = film.audio_bindings(alignment_path)
    alignment, delivery = _read(alignment_path), _read(delivery_path)
    if (delivery.get("bindings") != current or delivery.get("full_decode_passed") is not True
            or common.sha(delivery["video"]) != delivery.get("sha256")
            or delivery.get("duration") != alignment["duration"]
            or common.sha(delivery["review"]) != delivery.get("review_sha256")):
        raise ValueError("Original voiced delivery changed or belongs to another alignment")
    _audio_review(delivery["review"], current)
    paths = [alignment_path, delivery_path, delivery["video"], delivery["review"], alignment["plan"]]
    plan = _read(alignment["plan"])
    for item in alignment["inputs"]:
        paths.extend((item["wav"], item["receipt"]))
    paths.extend(plan["source"][key] for key in ("delivery", "video", "focuses"))
    for key in ("reference_source", "reference_receipt"):
        if key in plan:
            paths.append(plan[key])
    silent = _read(plan["source"]["delivery"])
    for key in ("narration", "visual_review", "narration_review", "revision_review"):
        if key in silent:
            paths.append(silent[key])
    return alignment, delivery, {"audio_bindings": current, "files": sorted(
        (_receipt(path) for path in {str(Path(p).resolve()) for p in paths}), key=lambda row: row["path"])}


def _media(path, duration):
    probe = pilot.probe(Path(path))
    streams = probe["streams"]
    if len(streams) != 2 or sorted(row["codec_type"] for row in streams) != ["audio", "video"]:
        raise ValueError("Expected exactly one video and one audio stream; no subtitle tracks")
    video = next(row for row in streams if row["codec_type"] == "video")
    audio = next(row for row in streams if row["codec_type"] == "audio")
    if video.get("disposition", {}).get("attached_pic"):
        raise ValueError("Attached picture is not the film")
    for row in (probe["format"], video, audio):
        measured = _number(float(row["duration"]))
        if abs(measured - _number(duration)) > Decimal("0.1"):
            raise ValueError("Caption media duration changed")
    return {"width": int(video["width"]), "height": int(video["height"])}


def _audio_hash(path):
    result = pilot.run([pilot.FFMPEG, "-v", "error", "-i", path, "-map", "0:a:0",
                        "-c:a", "copy", "-f", "streamhash", "-hash", "sha256", "-"], timeout=600)
    match = re.fullmatch(r"0,a,SHA256=([a-fA-F0-9]{64})\s*", result)
    if not match:
        raise ValueError("Missing copied-audio packet SHA256")
    return match[1].lower()


def _decode(path):
    pilot.run([pilot.FFMPEG, "-v", "error", "-xerror", "-i", path,
               "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], timeout=1800)


def _clean_playback(directory, video_name):
    # A fresh, isolated directory also prevents language-suffixed auto-loaded sidecars.
    if any(path.name not in {video_name, "delivery.json"} for path in directory.iterdir()):
        raise ValueError("Playback directory contains unbound files or subtitle sidecars")


def prepare(alignment, delivery, output, *, producer_agent, style=None):
    if not isinstance(producer_agent, str) or not producer_agent.strip():
        raise ValueError("Identify the candidate producer for independent review")
    alignment, delivery, output = (Path(path).resolve() for path in (alignment, delivery, output))
    if output.exists():
        raise FileExistsError(output)
    style = validate_style(style)
    value, voiced, source = _source(alignment, delivery)
    size = _media(voiced["video"], value["duration"])
    filters = pilot.run([pilot.FFMPEG, "-hide_banner", "-filters"])
    if not re.search(r"\bass\s+V->V\b", filters):
        raise ValueError("FFmpeg requires the libass ass filter")
    captions = make_captions(value, style)
    ass = make_ass(captions, style, **size)
    audio_hash = _audio_hash(voiced["video"])
    output.mkdir(parents=True, exist_ok=False)
    (output / "support").mkdir()
    _write(output / "style.json", style)
    _write(output / "captions.json", captions)
    _write(output / "source-receipts.json", source)
    with (output / "support/captions.ass").open("x", encoding="utf-8") as stream:
        stream.write(ass)
    # Escape both ffmpeg option and filtergraph parsing layers; never invoke a shell.
    filename = str(output / "support/captions.ass")
    filename = filename.replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")
    filename = filename.replace("[", "\\[").replace("]", "\\]").replace(",", "\\,").replace(";", "\\;")
    video = output / "candidate.mp4"
    pilot.run([pilot.FFMPEG, "-v", "error", "-n", "-i", voiced["video"],
               "-map", "0:v:0", "-map", "0:a:0", "-map_metadata", "-1", "-map_chapters", "-1",
               "-vf", f"ass=filename='{filename}'", "-c:v", "libx264", "-crf", "18",
               "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-sn", "-dn",
               "-movflags", "+faststart", video], timeout=1800)
    if _media(video, value["duration"]) != size or _audio_hash(video) != audio_hash:
        raise ValueError("Caption encode changed image dimensions or audio packets")
    _decode(video)
    if _source(alignment, delivery)[2] != source:
        raise ValueError("Source changed during caption rendering; rebuild in a new directory")
    _write(output / "candidate.json", {"schema_version": 1, "status": "candidate_not_released",
           "alignment": str(alignment), "voiced_delivery": str(delivery), "producer_agent": producer_agent,
           "duration": value["duration"], "size": size, "audio_packet_sha256": audio_hash,
           "full_decode_passed": True, "listening_reviewed": False})
    current = _current_bindings(output)
    _write(output / "bindings.json", current)
    return current


def _current_bindings(candidate):
    candidate = Path(candidate).resolve()
    if any(path.suffix.lower() in {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"}
           for path in candidate.iterdir()):
        raise ValueError("Candidate playback directory contains auto-loaded subtitle sidecars")
    manifest = _read(candidate / "candidate.json")
    if (manifest.get("status") != "candidate_not_released" or manifest.get("full_decode_passed") is not True
            or manifest.get("listening_reviewed") is not False):
        raise ValueError("Expected a fully decoded caption candidate, not a release")
    alignment, _, source = _source(manifest["alignment"], manifest["voiced_delivery"])
    if source != _read(candidate / "source-receipts.json"):
        raise ValueError("Frozen caption source changed; rebuild candidate")
    style = validate_style(_read(candidate / "style.json"))
    captions = make_captions(alignment, style)
    if (captions != _read(candidate / "captions.json")
            or make_ass(captions, style, **manifest["size"]) != (candidate / "support/captions.ass").read_text(encoding="utf-8")
            or manifest["duration"] != alignment["duration"]):
        raise ValueError("Caption text, style, timing or ASS changed; rebuild candidate")
    return {"schema_version": 1, "stage": "captions", "candidate": str(candidate),
            "module_sha256": common.sha(__file__), "audio_bindings": source["audio_bindings"],
            "files": {name: common.sha(candidate / name) for name in ARTIFACTS}}


def bindings(candidate):
    current = _current_bindings(candidate)
    frozen = Path(candidate) / "bindings.json"
    if (current != _read(frozen)
            or frozen.read_text(encoding="utf-8") != json.dumps(current, ensure_ascii=False, indent=2)):
        raise ValueError("Frozen candidate bindings changed; rebuild candidate")
    return current


def _caption_review(path, current, producer):
    review = _read(path)
    if (review.get("stage") != "captions" or review.get("bindings") != current
            or review.get("status") != "pass" or review.get("release_authorized") is not True
            or review.get("reviewer_role") != "independent" or not review.get("reviewer_agent")
            or review.get("reviewer_agent") == producer or review.get("blocking_findings") != []
            or review.get("listening_reviewed") is not False):
        raise ValueError("Require current independent captions review; captions are not listening review")
    for name in ("layout", "text_consistency", "frame_evidence"):
        check = review.get("checks", {}).get(name, {})
        if check.get("status") != "pass" or not isinstance(check.get("evidence"), list) or not check["evidence"]:
            raise ValueError(f"Require caption review evidence: {name}")
        for item in check["evidence"]:
            if not isinstance(item, dict) or not isinstance(item.get("finding"), str) or not item["finding"].strip():
                raise ValueError("Caption review requires structured evidence")
            if name == "frame_evidence":
                if (_number(item.get("time")) < 0 or _number(item["time"]) >= _number(_read(Path(current["candidate"]) / "candidate.json")["duration"])
                        or common.sha(item["path"]) != item.get("sha256")):
                    raise ValueError("Caption frame evidence changed or is out of bounds")
    return review


def release(candidate, review, output):
    candidate, review, output = (Path(path).resolve() for path in (candidate, review, output))
    if output.exists():
        raise FileExistsError(output)
    current = bindings(candidate)
    manifest = _read(candidate / "candidate.json")
    _caption_review(review, current, manifest["producer_agent"])
    review_sha = common.sha(review)
    video = candidate / "candidate.mp4"
    if (_media(video, manifest["duration"]) != manifest["size"]
            or _audio_hash(video) != manifest["audio_packet_sha256"]
            or _audio_hash(_read(manifest["voiced_delivery"])["video"]) != manifest["audio_packet_sha256"]):
        raise ValueError("Caption candidate audio or dimensions changed")
    _decode(video)
    if bindings(candidate) != current or common.sha(review) != review_sha:
        raise ValueError("Candidate or review changed during final verification")
    _caption_review(review, current, manifest["producer_agent"])
    output.mkdir(parents=True, exist_ok=False)
    target = output / "captioned.mp4"
    with video.open("rb") as source, target.open("xb") as destination:
        shutil.copyfileobj(source, destination)
    if (common.sha(target) != current["files"]["candidate.mp4"] or bindings(candidate) != current
            or common.sha(review) != review_sha):
        raise ValueError("Caption delivery copy changed")
    _caption_review(review, current, manifest["producer_agent"])
    _clean_playback(output, target.name)
    receipt = {"video": str(target), "sha256": common.sha(target), "bindings": current,
               "review": str(review), "review_sha256": review_sha, "full_decode_passed": True,
               "audio_packet_sha256": manifest["audio_packet_sha256"], "listening_reviewed": False,
               "scope": "Independently reviewed burned captions; not a listening or content-regression approval"}
    _write(output / "delivery.json", receipt)
    _clean_playback(output, target.name)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("prepare")
    for name in ("alignment", "delivery", "output"):
        cmd.add_argument(f"--{name}", type=Path, required=True)
    cmd.add_argument("--producer-agent", required=True)
    cmd.add_argument("--style", type=Path, help="JSON with allowlisted style options")
    cmd = commands.add_parser("bindings")
    cmd.add_argument("--candidate", type=Path, required=True)
    cmd = commands.add_parser("release")
    for name in ("candidate", "review", "output"):
        cmd.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.alignment, args.delivery, args.output, producer_agent=args.producer_agent,
                         style=_read(args.style) if args.style else None)
    elif args.command == "bindings":
        result = bindings(args.candidate)
    else:
        result = release(args.candidate, args.review, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
