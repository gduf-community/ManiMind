"""Index existing local viewing packages without moving or publishing media."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = [
    ("derivative-01-motion-revision-20261103", "导数入门：变量动效修订预览", "01-知识动画/02-展示与对比/导数动效修订-20261103", "captioned_revision_preview_delivered"),
    ("derivative-original-20261103", "导数及其应用", "高中数学-导数整章-配音字幕版-20261103", "existing_original_edition"),
    ("waves-20261031", "机械波小单元", "机械波小单元-完整版-20261031", "existing_viewing_package"),
    ("knowledge-trio-20261028", "三题知识动画", "三题知识动画-配音字幕版-20261028", "existing_viewing_package"),
    ("projectile-20261027", "平抛运动", "平抛运动-非线性配音字幕版-20261027", "existing_viewing_package"),
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def native_pointers(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and item.startswith(str(ROOT) + "/"):
                relative = Path(item).relative_to(ROOT).as_posix()
                if relative.startswith(("outputs/", "runtime/projects/")) and (
                    "delivery" in Path(item).name or Path(item).name in {"plan.json", "manifest.json"}
                ):
                    yield relative
            yield from native_pointers(item)
    elif isinstance(value, list):
        for item in value:
            yield from native_pointers(item)


def build(desktop: Path):
    entries = []
    for identifier, title, folder, stage in PACKAGES:
        package = desktop / folder if folder.startswith("01-知识动画/") else desktop / "01-知识动画/01-当前成片" / folder
        if not package.is_dir():
            continue
        records, manifest_hashes, expected = [], [], {}
        pointers = set()
        candidates = list(package.glob("*.json")) + list((package / "制作资料").glob("*发布清单.json"))
        for source in sorted(candidates):
            value = json.loads(source.read_text(encoding="utf-8"))
            manifest_hashes.append({"relative_to": "Desktop", "path": source.relative_to(desktop).as_posix(), "sha256": sha(source)})
            pointers.update(native_pointers(value))
            rows = []
            for section in ("files", "videos"):
                items = value.get(section, [])
                if isinstance(items, dict):
                    for name, row in items.items():
                        if isinstance(row, dict):
                            rows.append({"path": name, **row})
                        elif isinstance(row, str) and len(row) == 64:
                            rows.append({"path": name, "sha256": row})
                elif isinstance(items, list):
                    rows.extend(items)
            for row in rows:
                if isinstance(row, dict) and "path" in row and "sha256" in row:
                    expected[Path(row["path"]).name] = row["sha256"]
            records.append(value)
        videos = []
        for video in sorted(package.glob("*.mp4")):
            checksum = sha(video)
            if video.name in expected and expected[video.name] != checksum:
                raise ValueError("Viewing file differs from existing manifest: " + video.name)
            videos.append({"filename": video.name, "sha256": checksum, "size_bytes": video.stat().st_size,
                           "manifest_match": video.name in expected})
        listening = "passed" if any(r.get("listening_reviewed") is True for r in records) else (
            "pending" if any(r.get("listening_reviewed") is False for r in records) else "not_recorded")
        entries.append({"id": identifier, "title": title, "stage": stage,
                        "location": {"kind": "local_viewing_package", "relative_to": "Desktop", "path": package.relative_to(desktop).as_posix()},
                        "public_url": None, "videos": videos, "source_manifests": manifest_hashes,
                        "native_source_pointers": sorted(pointers), "listening_review": listening,
                        "verification": "Existing local bytes hashed; manifest compared where available; no new content approval"})
    return {"schema_version": 1, "publication_scope": "local_only_20261103", "created_at": datetime.now(timezone.utc).isoformat(),
            "writer": "build_work_catalog local indexing tool", "consumers": ["viewers", "lead", "maintainers"],
            "lifecycle": "Snapshot of existing viewing packages; retain with the named edition",
            "invalidation": "Package filenames, bytes, source manifests or release status change requires a new catalog snapshot",
            "media_operation": "read_only", "entries": entries,
            "current_revision": {"project": "derivative-eight-lessons", "stage": "in_progress",
                                 "lesson_01": "Captioned revision preview delivered; listening and student review pending",
                                 "registration": "Lead creates and confirms new viewing package before registration"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desktop", type=Path, default=Path.home() / "Desktop")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-output", type=Path)
    args = parser.parse_args()
    result = build(args.desktop)
    if args.previous_output:
        previous = args.output.read_bytes()
        with args.previous_output.open("xb") as stream:
            stream.write(previous)
        result["previous_catalog_sha256"] = hashlib.sha256(previous).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w" if args.previous_output else "x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"packages": len(result["entries"]), "videos": sum(len(e["videos"]) for e in result["entries"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
