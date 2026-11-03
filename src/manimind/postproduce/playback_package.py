"""Copy approved, burned-caption previews without auto-loadable subtitle sidecars."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil

from . import pilot


def package_playback(deliveries: dict[str, Path], output: Path) -> dict:
    """Preserve approved media bytes; this is packaging, not a new review or render."""
    if not deliveries:
        raise ValueError("At least one delivery is required")
    if output.exists():
        raise FileExistsError("Use a new playback directory; existing files are never replaced")

    records = []
    for name, delivery_path in deliveries.items():
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name):
            raise ValueError("Playback names must be simple file stems")
        delivery_path = delivery_path.resolve()
        delivery_hash = pilot.sha256(delivery_path)
        delivery = pilot.read_json(delivery_path)
        source = Path(delivery["video"])
        review_path = Path(delivery["review"])
        if not source.is_absolute() or not review_path.is_absolute():
            raise ValueError("Delivery media and review paths must be absolute")
        source = source.resolve()
        review_path = review_path.resolve()
        if source.suffix.lower() != ".mp4" or pilot.sha256(source) != delivery["sha256"]:
            raise ValueError("Published video hash mismatch")
        if pilot.sha256(review_path) != delivery["review_sha256"]:
            raise ValueError("Published review hash mismatch")
        pilot.validate_review(pilot.read_json(review_path), delivery["hashes"], require_zoom=False)
        if delivery.get("full_decode_passed") is not True:
            raise ValueError("Published full-decode check is required")
        metadata = pilot.probe(source)
        types = sorted(stream["codec_type"] for stream in metadata["streams"])
        if types != ["audio", "video"]:
            raise ValueError("Burned-caption playback requires only one video and one audio stream")
        records.append({
            "video": f"{name}.mp4", "sha256": delivery["sha256"],
            "source_video": str(source), "source_delivery": str(delivery_path),
            "source_delivery_sha256": delivery_hash,
            "review": str(review_path), "review_sha256": delivery["review_sha256"],
            "stream_types": types, "duration": delivery["duration"],
            "limitations": delivery.get("limitations", []),
        })

    output.mkdir(parents=True)
    for record in records:
        target = output / record["video"]
        shutil.copyfile(record["source_video"], target)
        if pilot.sha256(target) != record["sha256"]:
            raise ValueError("Playback copy differs from the published video")
        # Recheck provenance after copying so concurrent changes cannot be published.
        for path_key, hash_key in [("source_delivery", "source_delivery_sha256"),
                                   ("review", "review_sha256")]:
            if pilot.sha256(Path(record[path_key])) != record[hash_key]:
                raise ValueError("Publication evidence changed during packaging")

    manifest = {
        "writer": "postproduce.playback_package", "consumers": ["viewer", "auditor"],
        "lifecycle": "Immutable playback export; rebuild into a new directory",
        "invalidation": "Any copied media or bound publication evidence hash changes",
        "scope": "Byte-identical copies of published previews; no content edits or new approval",
        "subtitle_policy": "Burned captions only; no external subtitle files copied",
        "videos": records,
    }
    pilot.write_json(output / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    deliveries = {}
    for value in args.delivery:
        name, separator, path = value.partition("=")
        if not separator or not path or name in deliveries:
            parser.error("Each --delivery must have a unique NAME=PATH")
        deliveries[name] = Path(path)
    manifest = package_playback(deliveries, args.output)
    for record in manifest["videos"]:
        print(args.output / record["video"])


if __name__ == "__main__":
    main()
