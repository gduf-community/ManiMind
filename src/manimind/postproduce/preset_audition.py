"""Local Chinese preset auditions; no reference voices or video publication."""

from __future__ import annotations

import argparse
import array
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.request
import wave


TEXT = "同一高度，同时水平抛出。橙球横速是两倍，谁先落地？两球的竖直初速度都是零，向下的加速度也相同。重力加速度不变时，时间随高度的平方根变化，与横速无关。"
MODEL = "hexgrad/Kokoro-82M"
REVISION = "f3ff3571791e39611d31c381e3a41a3af07b4987"
QWEN = (
    ("Vivian", "女声", "普通话"), ("Serena", "女声", "普通话"),
    ("Uncle_Fu", "男声", "普通话"), ("Dylan", "男声", "北京口音"),
    ("Eric", "男声", "四川口音"),
)
KOKORO = ("zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
          "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang")
MODEL_HASHES = {
    "config.json": "5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f",
    "kokoro-v1_0.pth": "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4",
    "voices/zf_xiaobei.pt": "9b76be63dab4f4f96962030acc0126a9aee9728608fbbe115e2b58a2bd504df6",
    "voices/zf_xiaoni.pt": "95b49f169bf1640f4f43c25e13daa39f7b98d15d00823e83ef5c14b3ced59e49",
    "voices/zf_xiaoxiao.pt": "cfaf6f2ded1ee56f1ff94fcd2b0e6cdf32e5b794bdc05b44e7439d44aef5887c",
    "voices/zf_xiaoyi.pt": "b5235dbaeef85a4c613bf78af9a88ff63c25bac5f26ba77e36186d8b7ebf05e2",
    "voices/zm_yunjian.pt": "76cbf8bad35901d011d9628a2fdceb7b4f1f127e7a3269cb393b3941eb7fc417",
    "voices/zm_yunxi.pt": "dbe6e1ce7c3dbaf2f5667432947b638b1c6831ccbe154c4610dbcc44f431e27b",
    "voices/zm_yunxia.pt": "bb2b03b08e84d64e1214440ce3b624987fac177f2eeb5bab8571799a3d980acd",
    "voices/zm_yunyang.pt": "5238ac22e0c7f8b6cdd2eddd6e444b8a700b73c4674d9a047d59a94ff96379a2",
}
QWEN_MODEL_HASH = "c1d77e1fbb1a24e2474cea448e9d2e34f3b52a207d1fa7d8040bf033f7701766"
QWEN_WORKER_HASH = "555ee3544a45e2ab090d974e1f3c0f3cfb04db7eb0450b89f7f570d3e576ec93"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def qwen_request(voice):
    return {"model": "qwen3-tts-1.7b-customvoice", "input": TEXT, "voice": voice,
            "language": "Chinese", "instructions": "", "response_format": "wav"}


def validate_qwen_engine(engine):
    names = {"model", "model_files_sha256", "worker_sha256", "qwen_tts_version", "torch_version",
             "cuda_runtime", "gpu", "attention", "dtype"}
    if (set(engine) != names or engine["model"] != "qwen3-tts-1.7b-customvoice"
            or engine["model_files_sha256"] != QWEN_MODEL_HASH or engine["worker_sha256"] != QWEN_WORKER_HASH):
        raise ValueError("Qwen engine differs from the frozen local worker")


def validate_model_records(records):
    names = {item["file"] for item in records}
    if not set(MODEL_HASHES) <= names or names - set(MODEL_HASHES) - {"README.md", "VOICES.md"} or len(names) != len(records):
        raise ValueError("Incomplete, unexpected or duplicate model manifest")
    actual = {item["file"]: item["sha256"] for item in records}
    if any(actual[name] != expected for name, expected in MODEL_HASHES.items()):
        raise ValueError("Model manifest does not match pinned official files")


def request():
    return {"input": TEXT, "instructions": "", "seed": 1729, "speed": 1.0}


def validate_request(value):
    if value != request() or type(value.get("seed")) is not int or type(value.get("speed")) not in (float, int):
        raise ValueError("Use the exact shared neutral audition request")
    return value


def pcm_info(path):
    with wave.open(str(path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getnframes() <= 0:
            raise ValueError("Expected nonempty mono PCM16 WAV")
        count, rate = audio.getnframes(), audio.getframerate()
        data = audio.readframes(count)
    if len(data) != count * 2:
        raise ValueError("Truncated WAV")
    samples = array.array("h", data)
    if sys.byteorder != "little":
        samples.byteswap()
    peak = max(abs(sample) for sample in samples)
    rms = math.sqrt(sum(sample * sample for sample in samples) / count)
    if not rms:
        raise ValueError("Silent audition")
    return {"duration_seconds": count / rate, "sample_rate": rate,
            "rms_dbfs": 20 * math.log10(rms / 32768), "sample_peak": peak,
            "clipped_samples": sum(abs(sample) >= 32767 for sample in samples)}, samples


def level_payload(source):
    info, samples = pcm_info(source)
    rms = 10 ** (info["rms_dbfs"] / 20)
    gain = min(10 ** (-23 / 20) / rms, 10 ** (-1 / 20) * 32767 / info["sample_peak"])
    result = array.array("h", (round(sample * gain) for sample in samples))
    if sys.byteorder != "little":
        result.byteswap()
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(info["sample_rate"])
        audio.writeframes(result.tobytes())
    data = stream.getvalue()
    return data, {"method": "constant_gain_rms_target_minus23_dbfs_sample_peak_ceiling_minus1_dbfs",
                  "gain_db": 20 * math.log10(gain), "wav_sha256": hashlib.sha256(data).hexdigest()}


def level_copy(source, target):
    data, record = level_payload(source)
    with Path(target).open("xb") as stream:
        stream.write(data)
    return record


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "request.json", request())
    return request()


def qwen_batch(output, token):
    from manimind.postproduce.remote_speech import NoRedirect, audio_request

    validate_request(read_json(output / "request.json"))
    auth = token.read_text(encoding="utf-8").strip()
    health = urllib.request.Request("http://127.0.0.1:17666/health", headers={"Authorization": "Bearer " + auth})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(health, timeout=15) as response:
        engine = json.load(response)["engine"]
    validate_qwen_engine(engine)
    engine_path = output / "qwen-engine.json"
    if engine_path.exists():
        if read_json(engine_path)["engine"] != engine:
            raise ValueError("Stored Qwen engine changed")
    else:
        write_json(engine_path, {"engine": engine, "writer": "Authenticated loopback health client",
                   "consumers": ["packager", "auditor"], "lifecycle": "This pinned audition engine",
                   "invalidation": "Model, worker or environment changes"})
    directory = output / "qwen"
    directory.mkdir(exist_ok=True)
    for number, (voice, _, _) in enumerate(QWEN, 1):
        payload = qwen_request(voice)
        target = directory / f"{number:02d}-{voice}.wav"
        receipt = target.with_suffix(".receipt.json")
        if target.exists() or receipt.exists():
            previous = read_json(receipt)
            if previous["request"] != payload or previous["wav_sha256"] != sha(target):
                raise ValueError("Existing Qwen candidate differs; do not restart or overwrite")
            print(f"Verified existing Qwen candidate: {voice}", flush=True)
            continue
        record = audio_request("http://127.0.0.1:17666", token, payload, target)
        print(json.dumps({"voice": voice, "duration": record["duration_seconds"],
                          "server": record["server"]}), flush=True)


def validate_setup(setup):
    if setup.get("model_id") != MODEL or setup.get("revision") != REVISION:
        raise ValueError("Use the pinned official Kokoro model")
    root = Path(setup["model_path"]).resolve()
    records = setup.get("files", [])
    validate_model_records(records)
    for item in records:
        path = (root / item["file"]).resolve()
        if not path.is_relative_to(root) or sha(path) != item["sha256"]:
            raise ValueError("Pinned model file changed")
    return root


def kokoro_batch(output, request_path, setup_path):
    value = validate_request(read_json(request_path))
    setup = read_json(setup_path)
    root = validate_setup(setup)
    output.mkdir(parents=True, exist_ok=True)
    source = output / "generation-adapter.py"
    if source.exists():
        if sha(source) != sha(__file__):
            raise ValueError("Generation adapter changed; keep original evidence")
    else:
        with source.open("xb") as stream:
            stream.write(Path(__file__).read_bytes())
    directory = output / "kokoro"
    directory.mkdir(parents=True, exist_ok=False)
    state = {"status": "loading", "pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat(),
             "writer": "Kokoro audition worker", "consumers": ["operator"],
             "lifecycle": "This process attempt; retain failure evidence", "invalidation": "Exit or source/input change"}
    state_path = directory / "state.json"

    def update(**changes):
        state.update(changes)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    update()
    try:
        import numpy as np
        import soundfile
        import torch
        from kokoro import KModel, KPipeline

        if not torch.cuda.is_available():
            raise ValueError("CUDA required for this 5080 audition; no implicit fallback")
        torch.set_num_threads(4)
        started = time.monotonic()
        model = KModel(repo_id=MODEL, config=str(root / "config.json"), model=str(root / "kokoro-v1_0.pth")).to("cuda").eval()
        pipeline = KPipeline(lang_code="z", repo_id=MODEL, model=model)
        engine = {"model": MODEL, "revision": REVISION, "adapter_sha256": sha(__file__),
                  "model_files": setup["files"], "gpu": torch.cuda.get_device_name(0),
                  "model_load_seconds": time.monotonic() - started,
                  "packages": {name: importlib.metadata.version(name) for name in
                               ("kokoro", "misaki", "torch", "transformers", "soundfile", "numpy")},
                  "python": sys.version, "device": str(model.device), "dtype": str(next(model.parameters()).dtype)}
        for number, voice in enumerate(KOKORO, 6):
            update(status="generating", voice=voice)
            torch.manual_seed(value["seed"])
            np.random.seed(value["seed"])
            torch.cuda.reset_peak_memory_stats()
            started = time.monotonic()
            pack = torch.load(root / "voices" / f"{voice}.pt", map_location="cpu", weights_only=True)
            chunks = list(pipeline(value["input"], voice=pack, speed=1.0))
            samples = np.concatenate([part.audio.detach().float().cpu().numpy() for part in chunks])
            if samples.ndim != 1 or not np.isfinite(samples).all():
                raise ValueError("Invalid generated audio")
            target = directory / f"{number:02d}-{voice}.wav"
            with target.open("xb") as stream:
                soundfile.write(stream, samples, 24000, format="WAV", subtype="PCM_16")
            measured, _ = pcm_info(target)
            record = {"schema_version": 1, "request": {**value, "voice": voice}, "engine": engine,
                      "wav_sha256": sha(target), **measured, "generation_seconds": time.monotonic() - started,
                      "peak_torch_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
                      "chunks": [{"graphemes": part.graphemes, "phonemes": part.phonemes} for part in chunks],
                      "acceptance": "generated_not_listening_approved", "writer": "Kokoro audition worker",
                      "consumers": ["user", "audio reviewer"], "lifecycle": "This exact candidate",
                      "invalidation": "Text, voice, model, packages, adapter or audio changes"}
            write_json(target.with_suffix(".receipt.json"), record)
            print(json.dumps({"voice": voice, "seconds": measured["duration_seconds"],
                              "generation_seconds": record["generation_seconds"]}), flush=True)
        update(status="generated_not_listening_approved", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise


def collect(output):
    validate_request(read_json(output / "request.json"))
    qwen_engine = read_json(output / "qwen-engine.json")["engine"]
    validate_qwen_engine(qwen_engine)
    setup = read_json(output / "kokoro-setup-receipt.json")
    if setup["model_id"] != MODEL or setup["revision"] != REVISION:
        raise ValueError("Kokoro deployment source mismatch")
    validate_model_records(setup["files"])
    adapter_hash = sha(output / "generation-adapter.py")
    candidates = []
    specs = [(n, "qwen", v, gender, dialect) for n, (v, gender, dialect) in enumerate(QWEN, 1)]
    specs += [(n, "kokoro", v, "女声" if v.startswith("zf_") else "男声", "普通话") for n, v in enumerate(KOKORO, 6)]
    for number, engine, voice, gender, dialect in specs:
        path = output / engine / f"{number:02d}-{voice}.wav"
        receipt = read_json(path.with_suffix(".receipt.json"))
        if receipt["wav_sha256"] != sha(path) or receipt["request"]["input"] != TEXT or receipt["request"]["instructions"]:
            raise ValueError("Candidate hash, text or neutral instructions mismatch")
        if engine == "qwen":
            request_id = hashlib.sha256(canonical({"request": qwen_request(voice), "engine": qwen_engine})).hexdigest()
            if receipt["request"] != qwen_request(voice) or receipt["server"]["X-Request-ID"] != request_id:
                raise ValueError("Qwen request or frozen engine binding mismatch")
        if engine == "kokoro":
            expected_names = {"model", "revision", "adapter_sha256", "model_files", "gpu", "model_load_seconds", "packages", "python", "device", "dtype"}
            source = receipt["engine"]
            if (receipt["request"] != {**request(), "voice": voice} or set(source) != expected_names
                    or source["model"] != MODEL or source["revision"] != REVISION
                    or source["model_files"] != setup["files"] or source["adapter_sha256"] != adapter_hash):
                raise ValueError("Kokoro request or local model source mismatch")
            validate_model_records(source["model_files"])
        measured, _ = pcm_info(path)
        candidates.append({"id": f"{number:02d}", "voice": voice,
                           "engine": "Qwen3-TTS 1.7B" if engine == "qwen" else "Kokoro 82M v1.0",
                           "gender": gender, "dialect": dialect, "raw": path.relative_to(output).as_posix(),
                           "wav_sha256": receipt["wav_sha256"], **measured,
                           "generation_seconds": receipt.get("generation_seconds"),
                           "cache_hit": receipt.get("server", {}).get("X-Cache-Hit")})
    return candidates


def package(output):
    candidates = collect(output)
    targets = [output / name for name in ("listening", "manifest.json", "index.html", "README.md")]
    if any(path.exists() for path in targets):
        raise ValueError("Existing listening package is not overwritten")
    listening = output / "listening"
    listening.mkdir()
    for item in candidates:
        source = output / item["raw"]
        target = listening / source.name
        item["listening_gain"] = level_copy(source, target)
        item["listening"] = target.relative_to(output).as_posix()
    manifest = {"schema_version": 1, "request": request(), "candidates": candidates,
                "acceptance": "awaiting_user_voice_selection", "accepted_voice": None,
                "writer": "Preset audition packager", "consumers": ["user", "audio reviewer"],
                "lifecycle": "This thirteen-voice audition set; not final video acceptance",
                "invalidation": "Audio, request, model or user selection changes",
                "processing": "Raw PCM16 kept; listening copies use one constant gain, no time stretch, denoise or compression"}
    write_json(output / "manifest.json", manifest)
    template = Path(__file__).with_name("templates") / "preset_audition.html"
    payload = json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c")
    page = template.read_text(encoding="utf-8").replace("__AUDITION_DATA__", payload)
    with (output / "index.html").open("x", encoding="utf-8") as stream:
        stream.write(page)
    with (output / "README.md").open("x", encoding="utf-8") as stream:
        stream.write("# 本地中文预设试听\n\n打开 index.html，或直接播放 qwen/、kokoro/ 内的原始 WAV。\n\n")
        stream.write(TEXT + "\n\n")
        stream.write("共13条，来自Windows RTX5080本地模型。Qwen空语气指令，Kokoro默认speed=1；无老师人设。\n")
        stream.write("网页默认使用统一试听音量副本：仅固定增益，目标RMS -23dBFS且采样峰值不超过-1dBFS；不是LUFS归一化。可切回原音。无变速、降噪、补静音、动态压缩或人工改读音。\n")
        stream.write("北京/四川口音为该预设本身特性；同一随机种子不代表跨引擎相同随机分布。既有Qwen缓存可复用，不冒充本次重新生成。\n")
        stream.write("原始请求、模型/软件与音频收据保留；机器可解码不等于听审通过，不合成视频、不批准商用声线。\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "qwen", "kokoro", "package"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--setup-receipt", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.output)
    elif args.mode == "qwen":
        if args.token_file is None:
            parser.error("qwen requires --token-file")
        qwen_batch(args.output, args.token_file)
    elif args.mode == "kokoro":
        if args.request is None or args.setup_receipt is None:
            parser.error("kokoro requires --request and --setup-receipt")
        kokoro_batch(args.output, args.request, args.setup_receipt)
    else:
        manifest = package(args.output)
        print(json.dumps({"candidates": len(manifest["candidates"]), "acceptance": manifest["acceptance"]}))


if __name__ == "__main__":
    main()
