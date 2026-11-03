"""Review-only supervision over frozen v2 pixels, without rerendering geometry.

This layer writes a new supervised index and binds its own implementation there.
It consumes the immutable render through v2; it is not an animation dependency.
The independent report owns its decision. Source, asset or supervisor changes
invalidate this extra review package, not the mathematical animation itself.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import traceable_film_v2 as previous


CONTRACT = "traceable-formula-supervision-v3"
common = previous.common
unit_film = previous.unit_film


def prepare_evidence(attempt, output):
    raw = Path(output).absolute()
    if os.path.lexists(raw):
        raise FileExistsError("Retain existing evidence paths, including dangling symlinks")
    value = previous.prepare_evidence(attempt, raw)
    value = {**value, "supervision_contract": CONTRACT,
        "supervisor_sha256": common.sha(__file__),
        "native_index": str(raw.resolve() / "formula-evidence.json"),
        "native_index_sha256": common.sha(raw.resolve() / "formula-evidence.json"),
        "writer": "v3 review-evidence supervisor over the frozen v2 extractor",
        "lifecycle": "This bound render, lossless evidence and review supervisor only",
        "invalidation": "Render, selected assets, contact sheets, source index, supervisor or report changes"}
    path = raw.resolve() / "supervised-evidence.json"
    if os.path.lexists(path):
        raise FileExistsError("Never overwrite a supervised evidence index")
    common.write_json(path, value)
    return value


def require_review(attempt, review):
    report = common.read_json(review)
    selection = report.get("formula_continuity", {})
    path = selection.get("evidence_index")
    if (not isinstance(path, str) or not Path(path).is_absolute()
            or common.sha(path) != selection.get("evidence_index_sha256")):
        raise ValueError("Bind the current supervised lossless evidence index")
    value = common.read_json(path)
    if (value.get("supervision_contract") != CONTRACT
            or value.get("supervisor_sha256") != common.sha(__file__)):
        raise ValueError("Formula review supervisor changed or was not bound")
    native = value.get("native_index")
    if (not isinstance(native, str) or not Path(native).is_absolute()
            or common.sha(native) != value.get("native_index_sha256")):
        raise ValueError("Original lossless evidence index changed")
    original = common.read_json(native)
    if any(value.get(key) != original.get(key) for key in
            ("attempt", "bindings", "video", "video_sha256", "extractor_sha256", "frames", "sheets")):
        raise ValueError("Supervised evidence differs from its actual extraction source")
    for kind in ("frames", "sheets"):
        rows = value.get(kind)
        if not isinstance(rows, list) or not rows:
            raise ValueError("Keep all declared lossless frames and review contact sheets")
        for row in rows:
            asset = row.get("path")
            if (not isinstance(asset, str) or not Path(asset).is_absolute()
                    or not Path(asset).is_file() or common.sha(asset) != row.get("sha256")):
                raise ValueError("Formula review frame or contact sheet changed")
    return previous.require_review(attempt, review)


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
