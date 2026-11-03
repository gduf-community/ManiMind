"""Opt-in formula-continuity gate over the frozen course publisher.

The author writes selected transitions in the rendered plan, an independent
visual reviewer writes observations, and this adapter only verifies them. Their
lifetime is one bound render; edits invalidate the native bindings and report.
No motion-count threshold or fixed lesson template is imposed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from . import preset_audition as common, unit_film


CONTRACT = "traceable-formula-v1"


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_selection(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Select the reasoning-bearing formula transitions before rendering")
    ids = set()
    for row in rows:
        if (not isinstance(row, dict) or any(not _text(row.get(key)) for key in
                ("id", "operation", "source", "target", "purpose")) or row["id"] in ids):
            raise ValueError("Each selected transition needs a unique identity and mathematical intent")
        ids.add(row["id"])
    return ids


def validate_observations(rows, report, duration, *, root=None, frame_index=None):
    expected = validate_selection(rows)
    checks = report.get("formula_continuity", {}).get("checks")
    if (not isinstance(checks, list) or len(checks) != len(expected)
            or any(not isinstance(row, dict) or not _text(row.get("id")) for row in checks)
            or {row.get("id") for row in checks} != expected):
        raise ValueError("Independently assess every selected formula transition")
    for row in checks:
        if (row.get("traceable") is not True or not _text(row.get("identity_finding"))
                or not _text(row.get("operation_finding"))):
            raise ValueError("Visible motion alone cannot establish symbol identity or a mathematical operation")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Formula continuity requires actual process pixels")
        phases = {}
        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError("Process evidence must name actual frames")
            time = item.get("time")
            if (type(time) not in (int, float) or not math.isfinite(time)
                    or not 0 <= time < duration or not _text(item.get("finding"))):
                raise ValueError("Process evidence needs an in-range observation")
            phase = item.get("phase")
            if phase not in {"before", "during", "after"} or phase in phases:
                raise ValueError("Use distinct before/during/after observations")
            if not _text(item.get("frame")) or not _text(item.get("sha256")):
                raise ValueError("Bind observations to actual frame files")
            frame = Path(item["frame"])
            if not frame.is_absolute():
                if root is None:
                    raise ValueError("Relative evidence needs an explicit repository root")
                frame = Path(root) / frame
            if not frame.is_file() or common.sha(frame) != item["sha256"]:
                raise ValueError("Formula evidence frame is missing or changed")
            if frame_index is not None and not any(
                    Path(entry["path"]).resolve() == frame.resolve()
                    and entry["sha256"] == item["sha256"]
                    and abs(entry["time"] - time) < 1e-6 for entry in frame_index):
                raise ValueError("Formula evidence must belong to the current bound media at that time")
            phases[phase] = time
        if (set(phases) != {"before", "during", "after"}
                or not phases["before"] < phases["during"] < phases["after"]):
            raise ValueError("A final formula cannot replace source/during/destination evidence")
    return report


def require_review(attempt, review):
    attempt = Path(attempt).resolve()
    profile = common.read_json(attempt / "workflow-profile.json")
    plan = common.read_json(attempt / "plan.json")
    if profile.get("formula_continuity_contract") != CONTRACT:
        raise ValueError("Use the explicitly selected traceable-formula workflow")
    declared = {(unit_film.pilot.ROOT / name).resolve() for name in plan.get("sources", [])}
    archived = common.read_json(attempt / "render.json")["input_hashes"]
    module = Path(__file__).resolve()
    if module not in declared or archived.get(str(module)) != common.sha(module):
        raise ValueError("The actual formula gate must be a frozen rendered input")
    # Native validation still enforces independent identity, current bindings,
    # science/visual review and a separate old/new regression reviewer.
    report = unit_film.require_review(attempt, review)
    duration = common.read_json(attempt / "timeline.json")["duration"]
    frames = common.read_json(attempt / "review-input.json")["frames"]
    return validate_observations(plan.get("formula_transitions"), report, duration,
                                 root=unit_film.pilot.ROOT, frame_index=frames)


def install_narration(attempt, draft, visual_review, target):
    require_review(attempt, visual_review)
    return unit_film.install_narration(attempt, draft, visual_review, target)


def release_silent(attempt, narration, visual_review, narration_review, output):
    require_review(attempt, visual_review)
    return unit_film.release_silent(attempt, narration, visual_review, narration_review, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("gate", "install", "silent"))
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--visual-review", type=Path, required=True)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--narration", type=Path)
    parser.add_argument("--narration-review", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "gate":
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
