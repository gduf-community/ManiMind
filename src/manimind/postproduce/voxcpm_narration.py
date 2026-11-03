"""One-shot CUDA narration using the user's selected AI-generated V01 reference.

Deploy this file beside the frozen voxcpm_audition.py helper, then run:
  python voxcpm_narration.py generate --model PATH --output NEW \
    --setup-receipt PATH --plan PATH --reference V01.wav

The schema-1 plan supplies exactly N01..N17 and their approved text. Additional
metadata is preserved, never interpreted as generation instructions. Only a new
output directory is writable. The operator consumes process state; it ceases to
be live on exit and failures remain. Immutable receipts bind the exact inputs,
code and audio; any change invalidates them. This worker does no editing,
alignment, video assembly, retakes or final listening approval.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import traceback
import wave

if __package__:
    from . import voxcpm_audition as audition
else:
    import voxcpm_audition as audition


REFERENCE_SHA256 = "b36f1c933b6d452df52e85571bd8de995f8513c2033e8c3d1d923a7cb79c0be9"
HELPER_SHA256 = "10766c863d5f6f1f7c4dd337e9f0ca267ce9198bac1f8bbe6d2e80b4a0d567fc"
GENERATION = {"seed": 42, "cfg_value": 2.0, "inference_timesteps": 10,
              "normalize": False, "denoise": False, "retry_badcase": False}
SEED_METHOD = audition.SEED_METHOD


def validate_plan(value):
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or value.get("reference_sha256") != REFERENCE_SHA256
            or value.get("reference_text") != audition.TEXT
            or audition.canonical(value.get("generation")) != audition.canonical(GENERATION)):
        raise ValueError("Use the exact V01 reference, reference text and fixed generation settings")
    segments = value.get("segments")
    if not isinstance(segments, list) or len(segments) != 17:
        raise ValueError("Require exactly the 17 approved segments N01..N17")
    for index, segment in enumerate(segments, 1):
        if not isinstance(segment, dict) or segment.get("id") != f"N{index:02d}":
            raise ValueError("Segments must retain their unique N01..N17 order")
        if any(not isinstance(segment.get(key), str) or not segment[key].strip()
               for key in ("cue", "anchor", "relation", "text")):
            raise ValueError("Each segment needs its unchanged text and cue/anchor/relation")
        anchor_time = segment.get("anchor_time")
        if type(anchor_time) not in (int, float) or not math.isfinite(anchor_time) or anchor_time < 0:
            raise ValueError("Each anchor_time must be a finite nonnegative number")
    return value


def generate_kwargs(segment, reference, reference_text):
    return {"text": segment["text"], "reference_wav_path": str(reference),
            "prompt_wav_path": str(reference), "prompt_text": reference_text,
            **{key: value for key, value in GENERATION.items() if key != "seed"}}


def generate(model_path, output, setup_path, plan_path, reference_path):
    model_path, output, setup_path, plan_path, reference_path = (
        Path(path).resolve() for path in (model_path, output, setup_path, plan_path, reference_path))
    if (output.is_relative_to(model_path) or model_path.is_relative_to(output)
            or any(path.is_relative_to(output) for path in (setup_path, plan_path, reference_path,
                                                          Path(__file__).resolve(), Path(audition.__file__).resolve()))):
        raise ValueError("Use a new output directory separate from all source inputs")
    output.mkdir(parents=True, exist_ok=False)
    started_run = time.monotonic()
    progress = sys.stdout
    state = {"schema_version": 1, "pid": os.getpid(), "status": "validating",
             "started_at": datetime.now(timezone.utc).isoformat(), "attempted": [], "done": [],
             "call_count": 0, "model_load_count": 0, "seed_method": SEED_METHOD,
             "writer": "VoxCPM V01 narration adapter", "consumers": ["operator", "narration assembler"],
             "lifecycle": "One exclusive process attempt; preserve partial results and failures",
             "invalidation": "Process exit or any bound input/code/media change"}

    def update(**changes):
        state.update(changes)
        temporary = output / "state.json.tmp"
        audition.write_json(temporary, state)
        os.replace(temporary, output / "state.json")

    def emit(event, **details):
        print(json.dumps({"event": event, "pid": state["pid"], "call_count": state["call_count"],
                          "done_count": len(state["done"]), **details}), file=progress, flush=True)

    update()
    try:
        plan_bytes, setup_bytes = plan_path.read_bytes(), setup_path.read_bytes()
        for name, payload in (("plan.json", plan_bytes), ("setup-receipt.json", setup_bytes)):
            with (output / name).open("xb") as stream:
                stream.write(payload)
        source = output / "source"
        source.mkdir()
        for module in (Path(__file__), Path(audition.__file__)):
            with (source / module.name).open("xb") as stream:
                stream.write(module.read_bytes())
        bindings = {"plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                    "setup_sha256": hashlib.sha256(setup_bytes).hexdigest(),
                    "worker_sha256": audition.sha(source / "voxcpm_narration.py"),
                    "helper_sha256": audition.sha(source / "voxcpm_audition.py")}
        update(**bindings)
        if bindings["helper_sha256"] != HELPER_SHA256:
            raise ValueError("Use the frozen, hash-bound audition helper deployed with this adapter")
        plan = validate_plan(json.loads(plan_bytes.decode("utf-8-sig")))
        setup = json.loads(setup_bytes.decode("utf-8-sig"))
        root = audition.validate_setup(setup, model_path)
        if audition.sha(reference_path) != REFERENCE_SHA256:
            raise ValueError("Only the user-selected AI-generated V01 reference is allowed")
        reference = output / "reference.wav"
        with reference_path.open("rb") as original, reference.open("xb") as archived:
            for block in iter(lambda: original.read(1024 * 1024), b""):
                archived.write(block)
        if audition.sha(reference) != REFERENCE_SHA256:
            raise ValueError("V01 reference changed during copying")
        with wave.open(str(reference), "rb") as audio:
            if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (48000, 1, 2) or audio.getnframes() <= 0:
                raise ValueError("V01 must remain its original nonempty mono 48k PCM16 WAV")
        bindings["reference_sha256"] = REFERENCE_SHA256
        update(**bindings, reference_input_path=str(reference_path), reference_path=str(reference))
        requests = [{"id": segment["id"], "request": generate_kwargs(segment, reference, plan["reference_text"]),
                     "seed": GENERATION["seed"], "seed_method": SEED_METHOD} for segment in plan["segments"]]
        audition.write_json(output / "requests.json", requests)
        os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                           "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"})
        emit("loading", total_segments=len(requests))
        with (output / "generation.log").open("x", encoding="utf-8", buffering=1) as log, redirect_stdout(log), redirect_stderr(log):
            update(status="loading")
            packages = {}
            for name in ("voxcpm", "torch", "torchaudio", "transformers", "numpy", "safetensors", "huggingface-hub", "tokenizers", "sentencepiece"):
                try:
                    packages[name] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    packages[name] = None
            if packages["voxcpm"] != "2.0.3":
                raise ValueError("This adapter requires the verified VoxCPM 2.0.3 reference API")
            import torch
            import numpy as np

            if not torch.cuda.is_available():
                raise ValueError("CUDA is required; no CPU fallback")
            from voxcpm import VoxCPM

            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            update(model_load_count=1)
            started = time.monotonic()
            model = VoxCPM.from_pretrained(str(root), **audition.LOAD_OPTIONS)
            torch.cuda.synchronize()
            engine = {"model": audition.MODEL, "revision": setup["revision"], "declared_license": setup["declared_license"],
                      "model_files": setup["files"], "model_files_sha256": hashlib.sha256(audition.canonical(setup["files"])).hexdigest(),
                      **bindings, "packages": packages, "python": sys.version, "platform": sys.platform,
                      "cuda_runtime": torch.version.cuda, "gpu": torch.cuda.get_device_name(),
                      "load_options": audition.LOAD_OPTIONS, "seed_method": SEED_METHOD,
                      "model_load_seconds": time.monotonic() - started,
                      "load_peak_torch_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2}
            rate = model.tts_model.sample_rate
            if type(rate) is not int or rate != audition.SAMPLE_RATE:
                raise ValueError("Require native 48000 Hz output; no resampling")
            audition.write_json(output / "engine.json", engine)
            for segment, planned_request in zip(plan["segments"], requests):
                identity, kwargs = segment["id"], planned_request["request"]
                state["attempted"].append(identity)
                update(status="generating", current_segment=identity, current_request=kwargs)
                emit("segment_started", id=identity)
                random.seed(GENERATION["seed"])
                np.random.seed(GENERATION["seed"])
                torch.manual_seed(GENERATION["seed"])
                torch.cuda.manual_seed_all(GENERATION["seed"])
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                update(call_count=state["call_count"] + 1)
                started = time.monotonic()
                with torch.inference_mode():
                    samples = model.generate(**kwargs)
                torch.cuda.synchronize()
                elapsed = time.monotonic() - started
                allocated, reserved = torch.cuda.max_memory_allocated() / 1024**2, torch.cuda.max_memory_reserved() / 1024**2
                measured = audition.save_audio(output, identity, samples, rate)
                record = {"schema_version": 1, "id": identity, "segment": segment, "request": kwargs,
                          "generate_kwargs": kwargs, "seed": GENERATION["seed"], "seed_method": SEED_METHOD,
                          **bindings, **measured, "generation_seconds": elapsed, "engine": engine,
                          "pid": state["pid"], "call_count": state["call_count"], "segment_call_count": 1,
                          "peak_torch_allocated_mib": allocated, "peak_torch_reserved_mib": reserved,
                          "attempted": list(state["attempted"]), "done": state["done"] + [identity],
                          "acceptance": "generated_not_listening_or_alignment_approved",
                          "writer": "VoxCPM V01 narration adapter", "consumers": ["user", "audio reviewer", "narration assembler"],
                          "lifecycle": "This immutable first take and its approved plan segment",
                          "invalidation": "Plan text, reference, seed, model, setup, software, code or audio changes"}
                audition.write_json(output / f"{identity}.receipt.json", record)
                state["done"].append(identity)
                update()
                emit("segment_done", id=identity, duration_seconds=measured["duration_seconds"], generation_seconds=elapsed)
        update(status="generated_not_listening_or_alignment_approved", current_segment=None, current_request=None,
               finished_at=datetime.now(timezone.utc).isoformat(), total_seconds=time.monotonic() - started_run)
        emit("completed", total_segments=len(state["done"]))
        return state
    except BaseException as exc:
        audition.write_json(output / "failure.json", {"error_type": type(exc).__name__, "error": str(exc),
                            "traceback": traceback.format_exc(), "attempted": state["attempted"],
                            "done": state["done"], "call_count": state["call_count"]})
        update(status="failed", error_type=type(exc).__name__, error=str(exc),
               finished_at=datetime.now(timezone.utc).isoformat(), total_seconds=time.monotonic() - started_run)
        emit("failed", id=state.get("current_segment"), error_type=type(exc).__name__, error=str(exc))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("generate", help="Generate the 17 unchanged plan segments using selected V01")
    for name in ("model", "output", "setup-receipt", "plan", "reference"):
        command.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    state = generate(args.model, args.output, args.setup_receipt, args.plan, args.reference)
    print(json.dumps({"output": str(args.output), "status": state["status"], "done": state["done"]}), flush=True)


if __name__ == "__main__":
    main()
