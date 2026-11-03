"""Reproducible local VoiceDesign casting and a combined, non-publishing audition."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import time

if __package__:
    from . import preset_audition as common
else:
    import preset_audition as common


MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
REVISION = "5ecdb67327fd37bb2e042aab12ff7391903235d3"
WEIGHTS = {
    "model.safetensors": "391e8db219f292c515297cdceeb43e4eae67cdde35fa57e79a6a8a532fca0522",
    "speech_tokenizer/model.safetensors": "836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258",
}
BLOBS = {
    ".gitattributes": "a6344aac8c09253b3b630fb776ae94478aa0275b",
    "README.md": "7474784d52d29a8d370e1d6bbd6044a7af61e3e8",
    "config.json": "2c2c027c574a85c0d5a5d48e3cfed1a8a051ff9d",
    "generation_config.json": "1872b16d4535564abf2db5d6debe6cddd82b7f2e",
    "merges.txt": "20024bfe7c83998e9aeaf98a0cd6a2ce6306c2f0",
    "preprocessor_config.json": "0525dd953bb9241912f7147666f0d535165d5d4f",
    "speech_tokenizer/config.json": "06cc8dc4c5ec8a1929086b71b98c313020d9268b",
    "speech_tokenizer/configuration.json": "ab58e2eaf53cd14a1a2a7527d9261ceea93a24cd",
    "speech_tokenizer/preprocessor_config.json": "ba40914f4f49ab98a8ca545d4892ef7291a39592",
    "tokenizer_config.json": "6ff9fd60cc623bb54bbd603cbd418c97a11528d7",
    "vocab.json": "4783fe10ac3adce15ac8f358ef5462739852c569",
}
DELIVERY = "用自然、放松的普通话说话，像日常交谈。正常语速，句尾最后几个字读完整，再自然收住。不要老师腔、播音腔或广告推销腔，不做夸张强调，不模仿具体人物。"
PROFILES = (
    ("D01", "清亮自然", "女声", "成年年轻女声，中音偏亮，清楚但不尖细，音色干净，不甜腻。"),
    ("D02", "温润松弛", "女声", "成年女性的温润中音，声音有自然厚度，放松亲近，气息稳定，不软糯。"),
    ("D03", "清爽利落", "女声", "成年女性的清爽声线，中音略低，咬字利落但不生硬，带一点自然颗粒感，不沙哑。"),
    ("D04", "低柔沉静", "女声", "成年女性的自然低中音，柔和而清晰，胸腔共鸣稍多，平静但不低语、不气声。"),
    ("D05", "明快亲近", "女声", "成年年轻女声，中音明亮有活力，轻盈但不幼态，亲近自然，不嗲、不刻意卖萌。"),
    ("D06", "成熟通透", "女声", "三十岁左右成年女性声线，中音饱满通透，质感成熟，语气平实，不端着说话。"),
    ("D07", "清澈青年", "男声", "成年年轻男性声线，清澈的自然中音，不刻意压低，音色清爽，语气轻松。"),
    ("D08", "温和醇厚", "男声", "成年男性的温和中低音，声音醇厚但不浑浊，共鸣自然，不刻意营造磁性。"),
    ("D09", "明亮松弛", "男声", "成年男性的明亮中音，带自然口语感，声音舒展轻松，不油腻，不用主持人式语调。"),
    ("D10", "低沉自然", "男声", "成年男性的自然低中音，质地结实，清楚平稳，不故意压嗓子，不沙哑、不低语。"),
)
MINIMAL_PROFILES = (
    ("N01", "极简女声 1", "成年女性，正常音量，用平实口吻说普通话。"),
    ("N02", "极简女声 2", "成年女声，中音，正常音量，平实地说普通话。"),
    ("N03", "极简女声 3", "成年女声，音高略低，正常音量，平实地说普通话。"),
)


def plan(profile_set="original"):
    value = {"schema_version": 1, "input": common.TEXT, "language": "Chinese", "seed": 1729,
            "non_streaming_mode": True, "max_new_tokens": 2048,
            "context": {"writer": "Voice audition coordinator", "consumers": ["worker", "packager", "auditor", "user"],
                        "lifecycle": "This original Mandarin casting set", "invalidation": "Text, design descriptions or generation settings change"},
            "profiles": [{"id": identity, "label": label, "gender": gender, "description": description,
                          "instructions": description + DELIVERY} for identity, label, gender, description in PROFILES]}
    if profile_set == "minimal-female":
        value["profiles"] = [{"id": identity, "label": label, "gender": "女声", "description": description,
                              "instructions": description} for identity, label, description in MINIMAL_PROFILES]
        value["context"] = {**value["context"], "audition_set": "minimal_female",
                            "lifecycle": "Three minimal-description female first takes for comparison with existing auditions",
                            "guidance_goal": "Ordinary adult speech, not teacher or character performance; short positive descriptions only"}
    elif profile_set != "original":
        raise ValueError("Unknown audition profile set")
    return value


def validate_plan(value):
    if (not any(value == plan(name) for name in ("original", "minimal-female"))
            or type(value.get("seed")) is not int or value.get("non_streaming_mode") is not True):
        raise ValueError("Use the exact shared-text, original-voice casting plan")
    return value


def validate_records(setup):
    if setup.get("model_id") != MODEL or setup.get("revision") != REVISION:
        raise ValueError("Use the pinned official VoiceDesign model")
    records = setup.get("files", [])
    if len(records) != len(WEIGHTS) + len(BLOBS) or {item["file"] for item in records} != set(WEIGHTS) | set(BLOBS):
        raise ValueError("Unexpected, missing or duplicate model files")
    for item in records:
        if item["file"] in WEIGHTS:
            if item["sha256"] != WEIGHTS[item["file"]]:
                raise ValueError("Official VoiceDesign weight mismatch")
        elif item["official_blob"] != BLOBS[item["file"]]:
            raise ValueError("Official VoiceDesign configuration mismatch")


def validate_setup(setup):
    validate_records(setup)
    root = Path(setup["model_path"]).resolve()
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() or path.is_symlink()}
    if actual_files != {item["file"] for item in setup["files"]}:
        raise ValueError("Model directory contains undeclared or missing files")
    for item in setup["files"]:
        path = local_file(root, item["file"])
        if common.sha(path) != item["sha256"]:
            raise ValueError("Dedicated model file changed")
        if item["file"] in BLOBS:
            data = path.read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if blob != BLOBS[item["file"]]:
                raise ValueError("Configuration differs from the official pinned Git blob")
    config = common.read_json(root / "config.json")
    if config.get("tts_model_type") != "voice_design" or config.get("tts_model_size") != "1b7":
        raise ValueError("Wrong Qwen model type or size")
    return root


def local_file(root, relative):
    if not isinstance(relative, str) or not relative or ":" in relative or Path(relative).is_absolute():
        raise ValueError("Media must use an audition-relative local path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Media must remain inside this local audition directory")
    return path


def generate(output, plan_path, setup_path):
    value = validate_plan(common.read_json(plan_path))
    setup = common.read_json(setup_path)
    model_path = validate_setup(setup)
    output.mkdir(parents=True, exist_ok=False)
    common.write_json(output / "plan.json", value)
    common.write_json(output / "setup-receipt.json", setup)
    source = output / "source"
    source.mkdir()
    sources = {}
    for module in (Path(__file__), Path(common.__file__)):
        target = source / module.name
        shutil.copyfile(module, target)
        sources[module.name] = common.sha(target)
    state = {"status": "loading", "pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat(),
             "completed": [], "writer": "VoiceDesign audition worker", "consumers": ["operator"],
             "lifecycle": "One immutable process attempt; keep failures", "invalidation": "Exit, inputs or source changes"}

    def update(**changes):
        state.update(changes)
        (output / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    update()
    try:
        import numpy as np
        import soundfile
        import torch
        from qwen_tts import Qwen3TTSModel

        if not torch.cuda.is_available():
            raise ValueError("CUDA is required; no implicit CPU fallback")
        started = time.monotonic()
        model = Qwen3TTSModel.from_pretrained(str(model_path), device_map="cuda:0", dtype=torch.bfloat16,
                                             attn_implementation="sdpa", local_files_only=True)
        engine = {"model": MODEL, "revision": REVISION, "model_files": setup["files"], "sources": sources,
                  "packages": {name: importlib.metadata.version(name) for name in ("qwen-tts", "torch", "transformers", "soundfile", "numpy")},
                  "gpu": torch.cuda.get_device_name(0), "device": "cuda:0", "dtype": "bfloat16", "attention": "sdpa",
                  "python": sys.version, "model_load_seconds": time.monotonic() - started}
        for profile in value["profiles"]:
            update(status="generating", current_voice=profile["id"])
            torch.manual_seed(value["seed"])
            np.random.seed(value["seed"])
            torch.cuda.reset_peak_memory_stats()
            started = time.monotonic()
            with torch.inference_mode():
                wavs, rate = model.generate_voice_design(text=value["input"], language=value["language"],
                    instruct=profile["instructions"], non_streaming_mode=True, max_new_tokens=value["max_new_tokens"])
            if len(wavs) != 1 or np.asarray(wavs[0]).ndim != 1 or not np.isfinite(wavs[0]).all():
                raise ValueError("Invalid VoiceDesign waveform")
            target = output / f"{profile['id']}.wav"
            with target.open("xb") as stream:
                soundfile.write(stream, wavs[0], rate, format="WAV", subtype="PCM_16")
            measured, _ = common.pcm_info(target)
            record = {"schema_version": 1, "request": {key: value[key] for key in value if key not in {"profiles", "context"}},
                      "profile": profile, "engine": engine, "wav_sha256": common.sha(target), **measured,
                      "generation_seconds": time.monotonic() - started,
                      "peak_torch_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
                      "acceptance": "generated_not_listening_approved", "writer": "VoiceDesign audition worker",
                      "consumers": ["user", "audio reviewer"], "lifecycle": "This exact first take and its sources",
                      "invalidation": "Text, description, seed, model, packages, code or audio changes"}
            common.write_json(target.with_suffix(".receipt.json"), record)
            state["completed"].append(profile["id"])
            update()
            print(json.dumps({"id": profile["id"], "label": profile["label"], "duration_seconds": measured["duration_seconds"],
                              "generation_seconds": record["generation_seconds"]}, ensure_ascii=False), flush=True)
        update(status="generated_not_listening_approved", finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise


def collect(design):
    value = validate_plan(common.read_json(design / "plan.json"))
    minimal = value["context"].get("audition_set") == "minimal_female"
    setup = common.read_json(design / "setup-receipt.json")
    validate_records(setup)
    sources = {name: common.sha(design / "source" / name) for name in ("voicedesign_audition.py", "preset_audition.py")}
    candidates = []
    request = {key: value[key] for key in value if key not in {"profiles", "context"}}
    fields = {"model", "revision", "model_files", "sources", "packages", "gpu", "device", "dtype", "attention", "python", "model_load_seconds"}
    for profile in value["profiles"]:
        path = design / f"{profile['id']}.wav"
        receipt = common.read_json(path.with_suffix(".receipt.json"))
        engine = receipt["engine"]
        if (receipt["request"] != request or receipt["profile"] != profile or set(engine) != fields
                or engine["model"] != MODEL or engine["revision"] != REVISION or engine["sources"] != sources
                or engine["model_files"] != setup["files"] or engine["device"] != "cuda:0"
                or engine["attention"] != "sdpa" or engine["dtype"] != "bfloat16" or common.sha(path) != receipt["wav_sha256"]):
            raise ValueError("VoiceDesign candidate differs from its exact plan or local source")
        measured, _ = common.pcm_info(path)
        candidates.append({"id": profile["id"], "voice": profile["label"], "group": "minimal" if minimal else "design",
                           "gender": profile["gender"], "description": profile["description"], "dialect": "普通话",
                           "engine": "Qwen3-TTS VoiceDesign 1.7B", "raw": path.name,
                           "wav_sha256": receipt["wav_sha256"], **measured, "generation_seconds": receipt["generation_seconds"]})
        if minimal:
            candidates[-1]["kind"] = "design"
    return candidates


def package_combined(baseline, design, output):
    designed = collect(design)
    if len(designed) != 10 or any(item["group"] != "design" for item in designed):
        raise ValueError("Use the original ten-voice set for this combination")
    validated = common.collect(baseline)
    original = common.read_json(baseline / "manifest.json")
    if original["request"] != common.request() or len(original["candidates"]) != len(validated):
        raise ValueError("Original audition manifest changed")
    for actual, item in zip(validated, original["candidates"]):
        if any(item.get(key) != actual[key] for key in ("id", "voice", "raw", "wav_sha256", "gender", "dialect", "engine")):
            raise ValueError("Original audition identity changed")
        path = local_file(baseline, item["listening"])
        if common.sha(path) != item["listening_gain"]["wav_sha256"]:
            raise ValueError("Original listening copy changed")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(baseline, output / "baseline", symlinks=True)
    shutil.copytree(design, output / "voicedesign", symlinks=True)
    (output / "listening").mkdir()
    candidates = []
    for item in designed:
        item["raw"] = "voicedesign/" + item["raw"]
        target = output / "listening" / f"{item['id']}.wav"
        item["listening_gain"] = common.level_copy(output / item["raw"], target)
        item["listening"] = "listening/" + target.name
        candidates.append(item)
    for old in original["candidates"]:
        candidates.append({**old, "group": "qwen" if old["id"] <= "05" else "kokoro",
                           "raw": "baseline/" + old["raw"], "listening": "baseline/" + old["listening"]})
    manifest = {"schema_version": 1, "title": "中文音色试听", "subtitle": "RTX 5080 本地生成 · 同文 · 10 条设计声线 + 13 条固定预设",
                "request": {"input": common.TEXT}, "design_plan": "voicedesign/plan.json", "candidates": candidates,
                "groups": [{"id": "design", "title": "VoiceDesign 设计声线", "detail": "新增 10 款 · 6 女声 / 4 男声"},
                           {"id": "qwen", "title": "Qwen3-TTS 固定预设", "detail": "1.7B · 原 5 款"},
                           {"id": "kokoro", "title": "Kokoro 固定预设", "detail": "82M v1.0 · 原 8 款"}],
                "footer": "声线名称与描述是设计目标，实际听感以音频为准。原始 WAV 与来源收据保留；试听选择不是整片配音或商业授权验收。",
                "acceptance": "awaiting_user_voice_selection", "accepted_voice": None,
                "processing": "Original presets are byte-identical; new listening copies use constant gain only, no time stretch, denoise, compression or added pauses",
                "writer": "Combined local voice audition packager", "consumers": ["user", "audio reviewer"],
                "lifecycle": "This combined audition set, not final video acceptance",
                "invalidation": "Any voice, model, plan, audio, source or selection change"}
    common.write_json(output / "manifest.json", manifest)
    template = Path(common.__file__).with_name("templates") / "preset_audition.html"
    page = template.read_text(encoding="utf-8").replace("__AUDITION_DATA__", json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c"))
    with (output / "index.html").open("x", encoding="utf-8") as stream:
        stream.write(page)
    with (output / "README.md").open("x", encoding="utf-8") as stream:
        stream.write("# 中文音色试听\n\n打开index.html。新增D01至D10为VoiceDesign设计声线，原01至13为固定预设，全部同文。\n\n")
        stream.write(common.TEXT + "\n\n")
        stream.write("新组6女4男，每条一次完整生成，未模仿具体人物或借用广告录音；声线描述是目标而不是自然度评分。VoiceDesign不是广告里微软晓晓/晓伊的本地版本。\n\n")
        stream.write("新组同种子1729、Chinese、bfloat16/SDPA、non_streaming_mode=True，原始PCM16保留。试听副本只施加单一增益，目标RMS -23dBFS、采样峰值上限-1dBFS，不是LUFS归一化。可切回原音；无变速、降噪、动态压缩、补停顿或人工改字。\n\n")
        stream.write("原13条的原音及音量副本逐字节保留，不重新生成。全部是本地模型推理，没有云TTS费用；公开依赖/模型准备需要联网。未听审、未批准整片配音、商用或学生理解效果。\n")
    return manifest


def validate_combined(previous):
    manifest = common.read_json(previous / "manifest.json")
    expected = {}
    for item in collect(previous / "voicedesign"):
        expected[item["id"]] = {**item, "raw": "voicedesign/" + item["raw"]}
    for item in common.collect(previous / "baseline"):
        expected[item["id"]] = {**item, "group": "qwen" if item["id"] <= "05" else "kokoro",
                                "raw": "baseline/" + item["raw"]}
    items = manifest.get("candidates", [])
    if (manifest.get("request") != {"input": common.TEXT} or len(items) != 23
            or len(expected) != 23 or {item["id"] for item in items} != set(expected)):
        raise ValueError("Expected the original 23-voice comparison package")
    for item in items:
        actual = expected[item["id"]]
        fields = ("id", "voice", "engine", "group", "gender", "dialect", "raw", "wav_sha256", "duration_seconds", "sample_rate")
        if any(item.get(key) != actual[key] for key in fields) or ("description" in actual and item.get("description") != actual["description"]):
            raise ValueError("Previous candidate identity or description changed")
        expected_path = ("listening/" if item["group"] == "design" else "baseline/listening/") + Path(actual["raw"]).name
        _, expected_gain = common.level_payload(local_file(previous, actual["raw"]))
        if item["listening"] != expected_path or item["listening_gain"] != expected_gain:
            raise ValueError("Previous listening copy is not bound to its exact voice and constant gain")
        for field, expected_hash in (("raw", item["wav_sha256"]), ("listening", item["listening_gain"]["wav_sha256"])):
            if common.sha(local_file(previous, item[field])) != expected_hash:
                raise ValueError("Previous candidate audio changed")
    return manifest


def append_minimal(previous, minimal, output):
    sources = (previous.resolve(), minimal.resolve())
    target = output.resolve()
    if (any(target.is_relative_to(source) or source.is_relative_to(target) for source in sources)
            or sources[0].is_relative_to(sources[1]) or sources[1].is_relative_to(sources[0])):
        raise ValueError("Source and output directories must be separate, non-nested trees")
    additions = collect(minimal)
    if len(additions) != 3 or any(item["group"] != "minimal" for item in additions):
        raise ValueError("Append exactly the three minimal female first takes")
    original = validate_combined(previous)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(previous, output, symlinks=True)
    for name, archive in (("manifest.json", "manifest-23.json"), ("index.html", "index-23.html"),
                          ("README.md", "README-23.md"), ("quality-check.json", "quality-check-23.json")):
        if (output / name).exists():
            if (output / archive).exists():
                raise ValueError("Previous snapshot archive name already exists")
            (output / name).rename(output / archive)
    shutil.copytree(minimal, output / "minimal", symlinks=True)
    for item in additions:
        item["raw"] = "minimal/" + item["raw"]
        target = output / "listening" / f"{item['id']}.wav"
        item["listening_gain"] = common.level_copy(output / item["raw"], target)
        item["listening"] = "listening/" + target.name
    manifest = {**original, "subtitle": "RTX 5080 本地生成 · 同文 · 新增 3 条极简女声 + 原 23 条候选",
                "candidates": additions + original["candidates"], "minimal_plan": "minimal/plan.json",
                "groups": [{"id": "minimal", "title": "VoiceDesign 极简女声", "detail": "新增 3 条 · N01–N03", "priority": 0}] + original["groups"],
                "previous_manifest_sha256": common.sha(previous / "manifest.json"),
                "writer": "Minimal-description audition append packager",
                "processing": "Previous 23 candidates and their listening copies unchanged; new copies use constant gain only",
                "lifecycle": "This 26-voice audition; descriptions are targets, not listening approval"}
    common.write_json(output / "manifest.json", manifest)
    template = Path(common.__file__).with_name("templates") / "preset_audition.html"
    page = template.read_text(encoding="utf-8").replace("__AUDITION_DATA__", json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c"))
    with (output / "index.html").open("x", encoding="utf-8") as stream:
        stream.write(page)
    with (output / "README.md").open("x", encoding="utf-8") as stream:
        stream.write("# 中文音色试听：极简女声对照\n\n打开index.html。新增N01至N03，保留原D01至D10和01至13，共26条。\n\n")
        stream.write(common.TEXT + "\n\n")
        for identity, label, description in MINIMAL_PROFILES:
            stream.write(f"- {identity} {label}：{description}\n")
        stream.write("\n三条只使用以上完整描述，没有再拼接旧语气提示。相同本地模型/版本、原文、种子1729和生成参数，每条一次完整生成；不加老师或角色人设，不用旧广告录音。\n")
        stream.write("原始PCM16保留；试听副本只调整固定增益，不变速、不降噪、不压缩动态、不补停顿。旧23条的原音和试听副本全部逐字节保留，旧页面另存index-23.html。\n")
        stream.write("去除角色腔和自然度仍需实际试听；工程检查不等于听审通过，也未批准整片配音或商用声线。\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "generate", "package", "append-minimal"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--setup-receipt", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--design", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--profile-set", choices=("original", "minimal-female"), default="original")
    args = parser.parse_args()
    if args.mode == "prepare":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        common.write_json(args.output, plan(args.profile_set))
    elif args.mode == "generate":
        if args.plan is None or args.setup_receipt is None:
            parser.error("generate requires --plan and --setup-receipt")
        generate(args.output, args.plan, args.setup_receipt)
    elif args.mode == "package":
        if args.baseline is None or args.design is None:
            parser.error("package requires --baseline and --design")
        result = package_combined(args.baseline, args.design, args.output)
        print(json.dumps({"candidates": len(result["candidates"]), "accepted_voice": result["accepted_voice"]}))
    else:
        if args.previous is None or args.design is None:
            parser.error("append-minimal requires --previous and --design")
        result = append_minimal(args.previous, args.design, args.output)
        print(json.dumps({"candidates": len(result["candidates"]), "accepted_voice": result["accepted_voice"]}))


if __name__ == "__main__":
    main()
