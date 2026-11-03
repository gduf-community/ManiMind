"""Versioned repair of context isolation and actual formula-frame provenance.

The v1 module and its diagnostic renders remain frozen. This adapter owns no
approval state: current independent reports and selected transitions retain
their original writer/consumer/lifetime contracts. Changed sources or pixels
invalidate their native bindings. Decoding is read-only and never calls TTS.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from . import traceable_film as previous


CONTRACT = previous.CONTRACT
validate_selection = previous.validate_selection
validate_observations = previous.validate_observations
unit_film = previous.unit_film
common = previous.common


def _inputs(attempt):
    attempt = Path(attempt).resolve()
    plan = common.read_json(attempt / "plan.json")
    profile = common.read_json(attempt / "workflow-profile.json")
    if profile.get("formula_continuity_gate") != "traceable_film_v2":
        raise ValueError("Select the actual-pixels and independent-context formula workflow")
    module = Path(__file__).resolve()
    declared = {(unit_film.pilot.ROOT / name).resolve() for name in plan.get("sources", [])}
    record = common.read_json(attempt / "render.json")
    if module not in declared or record["input_hashes"].get(str(module)) != common.sha(module):
        raise ValueError("The actual v2 continuity gate must be a frozen rendered input")
    base_module = Path(previous.__file__).resolve()
    if base_module not in declared or record["input_hashes"].get(str(base_module)) != common.sha(base_module):
        raise ValueError("The inherited continuity validator must also be a frozen input")
    current = unit_film.bindings(attempt)
    validate_selection(plan.get("formula_transitions"))
    return plan, record, current


def prepare_evidence(attempt, output):
    """Extract genuine lossless PNGs at native review times, never convert JPEGs."""
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    _, record, current = _inputs(attempt)
    native = common.read_json(attempt / "review-input.json")
    output.mkdir(parents=True, exist_ok=False)
    frames = []
    for index, row in enumerate(native["frames"]):
        frame = output / f"frame_{index:04d}.png"
        unit_film.pilot.run([unit_film.pilot.FFMPEG, "-v", "error", "-n", "-ss", str(row["time"]),
            "-i", record["video"], "-frames:v", "1", "-update", "1", frame], timeout=60)
        frames.append({"time": row["time"], "path": str(frame), "sha256": common.sha(frame)})
    sheets = []
    for offset in range(0, len(frames), 9):
        sheet = Image.new("RGB", (1920, 1152), "#202226")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(frames[offset:offset + 9]):
            with Image.open(row["path"]) as source:
                thumb = source.convert("RGB")
                thumb.thumbnail((640, 360))
            x, y = index % 3 * 640, index // 3 * 384
            sheet.paste(thumb, (x, y + 24))
            draw.text((x + 7, y + 6), f"{row['time']:.3f}s", fill="white")
        path = output / f"contact-{offset // 9 + 1:02d}.jpg"
        sheet.save(path, quality=94)
        sheets.append({"path": str(path), "sha256": common.sha(path)})
    if unit_film.bindings(attempt) != current:
        raise ValueError("Formula source changed while preparing lossless evidence")
    value = {"attempt": str(attempt), "bindings": current, "frames": frames, "sheets": sheets,
        "extractor_sha256": common.sha(__file__), "video": record["video"],
        "video_sha256": record["video_sha256"], "writer": "v2 current-video lossless extractor",
        "consumers": ["independent visual reviewer", "formula-continuity gate"],
        "lifecycle": "This current bound video and native review timestamps",
        "invalidation": "Source, media, index, frame, extractor or review changes",
        "scope": "Evidence preparation only, not media approval"}
    common.write_json(output / "formula-evidence.json", value)
    return value


def require_review(attempt, review):
    attempt = Path(attempt).resolve()
    plan, record, current = _inputs(attempt)
    report = unit_film.require_review(attempt, review)
    selection = report.get("formula_continuity", {})
    index = selection.get("evidence_index")
    if not isinstance(index, str) or not Path(index).is_absolute():
        raise ValueError("Prepare and bind the explicit current-video lossless evidence index")
    if common.sha(index) != selection.get("evidence_index_sha256"):
        raise ValueError("Formula lossless evidence index changed")
    pixels = common.read_json(index)
    if (pixels.get("attempt") != str(attempt) or pixels.get("bindings") != current
            or pixels.get("extractor_sha256") != common.sha(__file__)
            or pixels.get("video") != record["video"]
            or pixels.get("video_sha256") != record["video_sha256"]):
        raise ValueError("Formula evidence belongs to a different source or extractor")
    validate_observations(plan.get("formula_transitions"), report,
        common.read_json(attempt / "timeline.json")["duration"], root=unit_film.pilot.ROOT,
        frame_index=pixels["frames"])
    comparison = unit_film.require_regression(attempt)
    if comparison is not None:
        other = common.read_json(comparison)
        current_identity = unit_film._identity(report, "reviewer")
        comparison_identity = unit_film._identity(other, "reviewer")
        if (current_identity[0] == comparison_identity[0]
                or current_identity[1] == comparison_identity[1]):
            raise ValueError("First-look and regression require distinct reviewer agents and contexts")
    # Index membership is a routing check, not proof of pixels. Verify against
    # the actual current video even for frames already named by its index.
    checked = set()
    streams = unit_film.pilot.probe(record["video"])["streams"]
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    if len(video_streams) != 1:
        raise ValueError("Formula evidence requires one unambiguous bound video stream")
    dimensions = (video_streams[0]["width"], video_streams[0]["height"])
    for row in report["formula_continuity"]["checks"]:
        for item in row["evidence"]:
            frame = Path(item["frame"])
            if not frame.is_absolute():
                frame = unit_film.pilot.ROOT / frame
            key = (str(frame.resolve()), item["sha256"], item["time"])
            if key not in checked:
                with Image.open(frame) as image:
                    if image.format != "PNG" or image.size != dimensions:
                        raise ValueError("Formula frame format or dimensions differ from the current video")
                    image.verify()
                if (frame.suffix.lower() != ".png" or unit_film._frame_pixels(frame)
                        != unit_film._frame_pixels(record["video"], item["time"])):
                    raise ValueError("Formula review pixels do not match the current video at that time")
                checked.add(key)
    return report


def install_narration(attempt, draft, visual_review, target):
    require_review(attempt, visual_review)
    return unit_film.install_narration(attempt, draft, visual_review, target)


def release_silent(attempt, narration, visual_review, narration_review, output):
    require_review(attempt, visual_review)
    return unit_film.release_silent(attempt, narration, visual_review, narration_review, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("evidence", "gate", "install", "silent"))
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--visual-review", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--narration", type=Path)
    parser.add_argument("--narration-review", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "evidence":
        if args.output is None:
            parser.error("evidence needs --output")
        result = prepare_evidence(args.attempt, args.output)
    elif args.visual_review is None:
        parser.error("reviewed stages need --visual-review")
    elif args.command == "gate":
        result = require_review(args.attempt, args.visual_review)
    elif args.command == "install":
        if args.draft is None or args.output is None:
            parser.error("install needs --draft and --output")
        result = install_narration(args.attempt, args.draft, args.visual_review, args.output)
    else:
        if any(value is None for value in (args.narration, args.narration_review, args.output)):
            parser.error("silent needs --narration, --narration-review and --output")
        result = release_silent(args.attempt, args.narration, args.visual_review,
                                args.narration_review, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
