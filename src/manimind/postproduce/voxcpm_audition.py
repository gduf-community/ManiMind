"""Standalone, CUDA-only VoxCPM2 first takes; no reference, selection or publishing.

Copy this file alone to Windows and run:
  python voxcpm_audition.py generate --model PATH --output UNIQUE --setup-receipt PATH

Only the new output directory is writable. state.json belongs to this one process;
the operator consumes it, failures are retained, and exit/input changes invalidate
it as live status. Receipts and source snapshots describe immutable first takes,
not listening approval; changing any bound input or media invalidates them.
"""

from __future__ import annotations

import argparse
import array
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import random
import sys
import time
import traceback
import wave


MODEL = "openbmb/VoxCPM2"
REVISION = "32279effe8c19989596f05d353d1447f51d9e915"
TEXT = "同一高度，同时水平抛出。橙球横速是两倍，谁先落地？两球的竖直初速度都是零，向下的加速度也相同。重力加速度不变时，时间随高度的平方根变化，与横速无关。"
SEEDS = (42, 43, 44)
SAMPLE_RATE = 48000
LOAD_OPTIONS = {"load_denoiser": False, "optimize": False, "device": "cuda", "local_files_only": True}
SEED_METHOD = "random.seed + numpy.random.seed + torch.manual_seed + torch.cuda.manual_seed_all before each call"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value))


def request(seed):
    if type(seed) is not int or seed not in SEEDS:
        raise ValueError("Only the three registered first-take seeds are permitted")
    return {"text": TEXT, "cfg_value": 2.0, "inference_timesteps": 10,
            "normalize": False, "denoise": False, "retry_badcase": False, "seed": seed}


def generate_kwargs(seed):
    # VoxCPM 2.0.3 predates the public seed argument; seed the RNGs explicitly.
    return {key: value for key, value in request(seed).items() if key != "seed"}


def local_file(root, name):
    if (not isinstance(name, str) or not name or any(char in name for char in '\\:\0<>"|?*')
            or PurePosixPath(name).is_absolute() or PurePosixPath(name).as_posix() != name):
        raise ValueError("Model files must have canonical relative Windows-safe paths")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)}
    if any(part in (".", "..") or part.endswith((".", " ")) or part.split(".")[0].upper() in reserved
           for part in PurePosixPath(name).parts):
        raise ValueError("Unsafe model file path")
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Model file is missing or escapes the model directory")
    return path


def validate_setup(setup, model_path):
    root = Path(model_path).resolve()
    if (not isinstance(setup, dict) or type(setup.get("schema_version")) is not int
            or setup["schema_version"] != 1 or setup.get("model_id") != MODEL
            or setup.get("revision") != REVISION or not isinstance(setup.get("model_path"), str)
            or Path(setup["model_path"]).resolve() != root or not root.is_dir()):
        raise ValueError("Use the exact pinned local VoxCPM2 setup and model path")
    if not isinstance(setup.get("declared_license"), str) or not setup["declared_license"].strip():
        raise ValueError("The setup must retain its declared license")
    records = setup.get("files")
    if not isinstance(records, list) or not records:
        raise ValueError("A nonempty model file manifest is required")
    names, folded = set(), set()
    for item in records:
        if not isinstance(item, dict) or not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Invalid model file SHA256 record")
        path = local_file(root, item.get("file"))
        name = item["file"]
        if name.casefold() in folded:
            raise ValueError("Duplicate or Windows case-colliding model file")
        names.add(name)
        folded.add(name.casefold())
        if sha(path) != item["sha256"]:
            raise ValueError(f"Model file SHA256 mismatch: {name}")
    actual = set()
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(parent) / name
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise ValueError("Linked model files or directories are not permitted")
        actual.update((Path(parent) / name).relative_to(root).as_posix() for name in files)
    if actual != names:
        raise ValueError("Model directory contains undeclared or missing files")
    if "config.json" not in names:
        raise ValueError("The declared VoxCPM2 config.json is required")
    config = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    if config.get("architecture") != "voxcpm2" or config.get("audio_vae_config", {}).get("out_sample_rate") != SAMPLE_RATE:
        raise ValueError("Expected VoxCPM2 with native 48000 Hz output; no resampling")
    return root


def save_audio(output, identity, samples, rate):
    if rate != SAMPLE_RATE or type(rate) is not int:
        raise ValueError("Expected native 48000 Hz; no resampling is permitted")
    if getattr(samples, "ndim", 1) != 1:
        raise ValueError("Expected a one-dimensional mono waveform")
    floating = array.array("f", samples)
    payload = array.array("f", floating)
    if sys.byteorder != "little":
        payload.byteswap()
    # Preserve the returned first take even if validation refuses a PCM audition.
    diagnostic = output / f"{identity}.float32"
    with diagnostic.open("xb") as stream:
        stream.write(payload.tobytes())
    if not floating or not all(math.isfinite(sample) for sample in floating):
        raise ValueError("Empty or nonfinite waveform; float32 evidence retained")
    peak = max(abs(sample) for sample in floating)
    if peak >= 1:
        raise ValueError("Clipping/full-scale waveform; no gain, clamp or retry; float32 evidence retained")
    pcm = array.array("h", (round(sample * 32767) for sample in floating))
    clipped = sum(abs(sample) >= 32767 for sample in pcm)
    rms = math.sqrt(sum(sample * sample for sample in pcm) / len(pcm))
    if clipped or not rms:
        raise ValueError("Clipped or silent PCM16; no repair or retry; float32 evidence retained")
    sample_peak = max(abs(sample) for sample in pcm)
    if sys.byteorder != "little":
        pcm.byteswap()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm.tobytes())
    target = output / f"{identity}.wav"
    with target.open("xb") as stream:
        stream.write(buffer.getvalue())
    return {"wav_sha256": sha(target), "sample_rate": rate, "channels": 1, "sample_width_bytes": 2,
            "frames": len(floating), "duration_seconds": len(floating) / rate,
            "float_peak": peak, "sample_peak": sample_peak, "clipped_samples": clipped,
            "rms_dbfs": 20 * math.log10(rms / 32768), "finite": True,
            "float32_file": diagnostic.name, "float32_sha256": sha(diagnostic),
            "float32_format": "mono_little_endian_float32_at_native_sample_rate",
            "pcm_conversion": "round_float_times_32767_no_gain_clamp_dither_or_other_processing"}


def generate(model_path, output, setup_path):
    model_path, output, setup_path = (Path(path).resolve() for path in (model_path, output, setup_path))
    if output.is_relative_to(model_path) or model_path.is_relative_to(output) or setup_path.is_relative_to(output):
        raise ValueError("Use a non-nested, unique output outside all source inputs")
    output.mkdir(parents=True, exist_ok=False)
    started_run = time.monotonic()
    state = {"schema_version": 1, "status": "validating", "pid": os.getpid(),
             "started_at": datetime.now(timezone.utc).isoformat(), "attempted": [], "done": [],
             "seeds": list(SEEDS), "writer": "VoxCPM2 audition worker", "consumers": ["operator"],
             "lifecycle": "One process attempt in a create-only directory; keep failures",
             "invalidation": "Process exit or bound input/source changes"}

    def update(**changes):
        state.update(changes)
        temporary = output / "state.json.tmp"
        write_json(temporary, state)
        os.replace(temporary, output / "state.json")

    update()
    try:
        setup_bytes = setup_path.read_bytes()
        setup = json.loads(setup_bytes.decode("utf-8-sig"))
        with (output / "setup-receipt.json").open("xb") as stream:
            stream.write(setup_bytes)
        update(setup_sha256=hashlib.sha256(setup_bytes).hexdigest())
        root = validate_setup(setup, model_path)
        source = output / "source"
        source.mkdir()
        worker = source / "voxcpm_audition.py"
        with worker.open("xb") as stream:
            stream.write(Path(__file__).read_bytes())
        write_json(output / "requests.json", [request(seed) for seed in SEEDS])
        os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                           "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"})
        with (output / "generation.log").open("x", encoding="utf-8", buffering=1) as log, redirect_stdout(log), redirect_stderr(log):
            update(status="loading")
            import torch
            import numpy as np

            if not torch.cuda.is_available():
                raise ValueError("CUDA is required; no implicit CPU fallback")
            from voxcpm import VoxCPM

            packages = {}
            for name in ("voxcpm", "torch", "torchaudio", "transformers", "numpy", "safetensors", "huggingface-hub", "tokenizers", "sentencepiece"):
                try:
                    packages[name] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    packages[name] = None
            if packages["voxcpm"] != "2.0.3":
                raise ValueError("This audition adapter requires the verified VoxCPM 2.0.3 API")
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            started = time.monotonic()
            model = VoxCPM.from_pretrained(str(root), **LOAD_OPTIONS)
            torch.cuda.synchronize()
            engine = {"model": MODEL, "revision": setup["revision"], "declared_license": setup["declared_license"],
                      "model_files": setup["files"], "model_files_sha256": hashlib.sha256(canonical(setup["files"])).hexdigest(),
                      "worker_sha256": sha(worker), "setup_sha256": state["setup_sha256"],
                      "packages": packages, "python": sys.version, "platform": sys.platform,
                      "cuda_runtime": torch.version.cuda, "gpu": torch.cuda.get_device_name(),
                      "load_options": LOAD_OPTIONS, "model_load_seconds": time.monotonic() - started,
                      "load_peak_torch_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2}
            rate = model.tts_model.sample_rate
            if type(rate) is not int or rate != SAMPLE_RATE:
                raise ValueError("Loaded model does not provide native 48000 Hz output")
            write_json(output / "engine.json", engine)
            for index, seed in enumerate(SEEDS, 1):
                identity = f"V{index:02d}"
                state["attempted"].append(seed)
                update(status="generating", current_candidate=identity, current_seed=seed, current_request=request(seed))
                random.seed(seed)
                np.random.seed(seed)
                torch.manual_seed(seed)
                torch.cuda.manual_seed_all(seed)
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                started = time.monotonic()
                with torch.inference_mode():
                    samples = model.generate(**generate_kwargs(seed))
                torch.cuda.synchronize()
                elapsed = time.monotonic() - started
                allocated = torch.cuda.max_memory_allocated() / 1024**2
                reserved = torch.cuda.max_memory_reserved() / 1024**2
                measured = save_audio(output, identity, samples, rate)
                record = {"schema_version": 1, "id": identity, "seed": seed, "request": request(seed),
                          "generate_kwargs": generate_kwargs(seed), "seed_method": SEED_METHOD,
                          "engine": engine, **measured, "generation_seconds": elapsed,
                          "peak_torch_allocated_mib": allocated, "peak_torch_reserved_mib": reserved,
                          "acceptance": "generated_not_listening_approved",
                          "limitations": ["Unconditioned random voice; no gender or speaker identity guarantee",
                                          "All three registered first takes retained; no selection, retake or automatic repair",
                                          "Declared model license is not final voice or commercial-use clearance"],
                          "writer": "VoxCPM2 audition worker", "consumers": ["user", "audio reviewer", "packager"],
                          "lifecycle": "This immutable first take and its exact inputs",
                          "invalidation": "Text, seed, model, setup, software, worker or media changes"}
                write_json(output / f"{identity}.receipt.json", record)
                state["done"].append(seed)
                update()
                print(json.dumps({"id": identity, "seed": seed, "duration_seconds": measured["duration_seconds"],
                                  "generation_seconds": elapsed}), flush=True)
        update(status="generated_not_listening_approved", current_candidate=None, current_seed=None, current_request=None,
               finished_at=datetime.now(timezone.utc).isoformat(), total_seconds=time.monotonic() - started_run)
        return state
    except BaseException as exc:
        write_json(output / "failure.json", {"error_type": type(exc).__name__, "error": str(exc),
                   "traceback": traceback.format_exc(), "attempted": state["attempted"], "done": state["done"]})
        update(status="failed", error_type=type(exc).__name__, error=str(exc),
               finished_at=datetime.now(timezone.utc).isoformat(), total_seconds=time.monotonic() - started_run)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("generate", help="Generate the three fixed, unconditioned first takes")
    command.add_argument("--model", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--setup-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    state = generate(args.model, args.output, args.setup_receipt)
    print(json.dumps({"output": str(args.output), "status": state["status"], "done": state["done"]}), flush=True)


if __name__ == "__main__":
    main()
