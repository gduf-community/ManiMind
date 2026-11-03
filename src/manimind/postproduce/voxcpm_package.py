"""Append three immutable VoxCPM2 first takes to the existing 27-choice audition.

This local packager never loads a model. It writes a new directory only; the
manifest is consumed by listeners/auditors and lasts for this exact source/media
snapshot. Any source, manifest, audio or listening-gain change invalidates it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil

from . import preset_audition as common
from . import voxcpm_audition as worker


def local_file(root, relative):
    if (not isinstance(relative, str) or not relative or any(char in relative for char in "\\:\0")
            or PurePosixPath(relative).is_absolute() or PurePosixPath(relative).as_posix() != relative
            or ".." in PurePosixPath(relative).parts):
        raise ValueError("Expected a canonical package-relative file path")
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Package file is missing or outside its source directory")
    return path


def reject_links(root):
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(parent) / name
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise ValueError("Source trees must not contain symlinks or junctions")


def validate_previous(previous):
    original = common.read_json(local_file(previous, "manifest.json"))
    items = original.get("candidates", [])
    if (original.get("request", {}).get("input") != common.TEXT or len(items) != 27
            or len({item["id"] for item in items}) != 27):
        raise ValueError("Expected the existing 27-candidate shared-text package")
    for item in items:
        raw = local_file(previous, item["raw"])
        if common.sha(raw) != item["wav_sha256"]:
            raise ValueError(f"Previous raw hash changed: {item['id']}")
        expected, gain = common.level_payload(raw)
        listening = local_file(previous, item["listening"])
        if item["listening_gain"] != gain or listening.read_bytes() != expected:
            raise ValueError(f"Previous listening copy is not bound to its raw/gain: {item['id']}")
    return original


def collect(vox):
    state = common.read_json(local_file(vox, "state.json"))
    if (state.get("status") != "generated_not_listening_approved"
            or state.get("attempted") != list(worker.SEEDS) or state.get("done") != list(worker.SEEDS)):
        raise ValueError("Require all three completed first takes, not a partial or retried run")
    setup_path = local_file(vox, "setup-receipt.json")
    setup = common.read_json(setup_path)
    engine = common.read_json(local_file(vox, "engine.json"))
    source = local_file(vox, "source/voxcpm_audition.py")
    if (setup.get("schema_version") != 1 or setup.get("model_id") != worker.MODEL
            or setup.get("revision") != worker.REVISION or engine.get("model") != worker.MODEL
            or engine.get("revision") != worker.REVISION or engine.get("model_files") != setup.get("files")
            or engine.get("setup_sha256") != common.sha(setup_path)
            or state.get("setup_sha256") != engine["setup_sha256"]
            or engine.get("worker_sha256") != common.sha(source)
            or engine.get("load_options") != worker.LOAD_OPTIONS
            or engine.get("packages", {}).get("voxcpm") != "2.0.3"
            or engine.get("model_files_sha256") != hashlib.sha256(worker.canonical(setup["files"])).hexdigest()):
        raise ValueError("Vox sources differ from their frozen worker/setup/model manifest")
    if common.read_json(local_file(vox, "requests.json")) != [worker.request(seed) for seed in worker.SEEDS]:
        raise ValueError("Vox requests changed")
    candidates = []
    for index, seed in enumerate(worker.SEEDS, 1):
        identity = f"V{index:02d}"
        receipt = common.read_json(local_file(vox, f"{identity}.receipt.json"))
        raw = local_file(vox, f"{identity}.wav")
        info, _ = common.pcm_info(raw)
        kwargs = {key: value for key, value in worker.request(seed).items() if key != "seed"}
        if (receipt.get("id") != identity or receipt.get("seed") != seed
                or receipt.get("request") != worker.request(seed) or receipt.get("generate_kwargs") != kwargs
                or receipt.get("seed_method") != worker.SEED_METHOD or receipt.get("engine") != engine
                or receipt.get("acceptance") != "generated_not_listening_approved"
                or receipt.get("wav_sha256") != common.sha(raw) or receipt.get("finite") is not True
                or info["sample_rate"] != 48000 or info["clipped_samples"] != 0
                or any(receipt.get(key) != value for key, value in info.items())
                or receipt.get("float32_file") != f"{identity}.float32"
                or receipt.get("float32_sha256") != common.sha(local_file(vox, f"{identity}.float32"))):
            raise ValueError(f"Vox first take does not match its receipt: {identity}")
        candidates.append({"id": identity, "voice": f"VoxCPM2 随机音色 {index}", "group": "vox", "kind": "unconditioned",
                           "gender": "未标注", "dialect": "普通话", "engine": "VoxCPM2 2B",
                           "seed": seed, "raw": f"vox/{identity}.wav", "wav_sha256": receipt["wav_sha256"],
                           **info, "generation_seconds": receipt["generation_seconds"]})
    return candidates


def package(previous, vox, output):
    previous, vox, output = (Path(path).resolve() for path in (previous, vox, output))
    roots = (previous, vox, output)
    if any(left.is_relative_to(right) or right.is_relative_to(left)
           for index, left in enumerate(roots) for right in roots[index + 1:]):
        raise ValueError("Source and output directories must be separate, non-overlapping trees")
    if output.exists():
        raise FileExistsError("Existing audition output is never overwritten")
    for root in (previous, vox):
        if not root.is_dir():
            raise ValueError("Both source directories must exist")
        reject_links(root)
    previous_hash = common.sha(local_file(previous, "manifest.json"))
    original = validate_previous(previous)
    additions = collect(vox)
    if {item["id"] for item in additions} & {item["id"] for item in original["candidates"]}:
        raise ValueError("New candidate IDs collide with the previous package")
    archives = {name: f"{Path(name).stem}-before-vox{Path(name).suffix}"
                for name in ("manifest.json", "index.html", "README.md", "quality-check.json", "browser-check.json")}
    if ((previous / "vox").exists() or any((previous / name).exists() for name in archives.values())
            or any((previous / "listening" / f"{item['id']}.wav").exists() for item in additions)):
        raise ValueError("Reserved Vox package paths already exist")
    groups = [dict(group) for group in original["groups"]]
    if any(group["id"] == "vox" for group in groups):
        raise ValueError("Previous package already contains a Vox group")
    reference_groups = {item.get("group") for item in original["candidates"]
                        if item["id"] in ("A", "A01") or item.get("kind") == "reference"}
    for group in groups:
        if group["id"] in reference_groups:
            group["priority"] = -1
    groups.insert(0, {"id": "vox", "title": "VoxCPM2 无参考随机音色", "detail": "新增 3 条 · seed 42/43/44", "priority": -2})
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(previous, output)
    for name, archive in archives.items():
        if (output / name).exists():
            (output / name).rename(output / archive)
    if common.sha(output / archives["manifest.json"]) != previous_hash:
        raise ValueError("Previous manifest changed while copying")
    # Verify the copied bytes too, including the retained A reference and its gain.
    copied = common.read_json(output / archives["manifest.json"])
    for item in copied["candidates"]:
        if common.sha(local_file(output, item["raw"])) != item["wav_sha256"]:
            raise ValueError("Previous raw changed while copying")
        payload, gain = common.level_payload(local_file(output, item["raw"]))
        if gain != item["listening_gain"] or local_file(output, item["listening"]).read_bytes() != payload:
            raise ValueError("Previous listening copy changed while copying")
    shutil.copytree(vox, output / "vox")
    if collect(output / "vox") != additions:
        raise ValueError("Vox sources changed while copying")
    (output / "listening").mkdir(exist_ok=True)
    for item in additions:
        target = output / "listening" / f"{item['id']}.wav"
        item["listening_gain"] = common.level_copy(local_file(output, item["raw"]), target)
        item["listening"] = f"listening/{target.name}"
    template = Path(common.__file__).with_name("templates") / "preset_audition.html"
    manifest = {**original, "title": "中文音色试听", "subtitle": "本地生成 · 新增 3 条无参考 VoxCPM2 · 原 27 条原样保留",
                "candidates": additions + original["candidates"], "groups": groups,
                "previous_manifest_sha256": previous_hash, "previous_manifest": archives["manifest.json"],
                "vox_engine_sha256": common.sha(output / "vox" / "engine.json"),
                "packager_sha256": common.sha(__file__), "template_sha256": common.sha(template),
                "accepted_voice": None, "acceptance": "awaiting_user_voice_selection",
                "footer": original.get("footer", "") + " VoxCPM2 为无描述、无参考的首轮随机音色，不保证性别；试听不是配音或商用授权验收。",
                "processing": "Previous 27 candidates and audio unchanged; only new listening copies receive constant gain",
                "writer": "VoxCPM2 audition append packager", "consumers": ["user", "audio reviewer"],
                "lifecycle": "This immutable 30-choice comparison, not final voice approval",
                "invalidation": "Any source manifest, request, worker, model, package or audio changes"}
    common.write_json(output / "manifest.json", manifest)
    page = template.read_text(encoding="utf-8").replace("__AUDITION_DATA__", json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c"))
    with (output / "index.html").open("x", encoding="utf-8") as stream:
        stream.write(page)
    with (output / "README.md").open("x", encoding="utf-8") as stream:
        stream.write("# VoxCPM2 无参考首次试听\n\n新增 V01-V03，seed 42/43/44，各一次，不挑样、不重试、不承诺女声。\n")
        stream.write("原27条（含参考A）的候选记录、原音和试听副本均原样保留；旧页面及manifest另存before-vox快照。\n")
        stream.write("新试听副本只使用固定增益，不变速、降噪或修音。原始48k PCM16、浮点证据和来源收据在vox目录。\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("package",))
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--vox", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = package(args.previous, args.vox, args.output)
    print(json.dumps({"candidates": len(result["candidates"]), "accepted_voice": result["accepted_voice"]}))


if __name__ == "__main__":
    main()
