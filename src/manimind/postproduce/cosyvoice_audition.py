"""One-shot CosyVoice3 audition through an existing, read-only engine checkout."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave


MODEL_ID = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
MODEL_FILES = {"llm.pt", "flow.pt", "hift.pt", "campplus.onnx", "speech_tokenizer_v3.onnx",
               "cosyvoice3.yaml", "config.json", "configuration.json", "CosyVoice-BlankEN/config.json",
               "CosyVoice-BlankEN/generation_config.json", "CosyVoice-BlankEN/merges.txt",
               "CosyVoice-BlankEN/model.safetensors", "CosyVoice-BlankEN/tokenizer_config.json", "CosyVoice-BlankEN/vocab.json"}


def file_sha256(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate_request(value):
    if not isinstance(value, dict) or set(value) != {"input", "instructions", "seed"}:
        raise ValueError("Supply only input, instructions and seed")
    for name, limit in (("input", 600), ("instructions", 1000)):
        text = value[name]
        if not isinstance(text, str) or not text.strip() or len(text) > limit or "<|" in text:
            raise ValueError(f"Invalid {name}")
    if type(value["seed"]) is not int or not 0 <= value["seed"] < 2**32:
        raise ValueError("Supply an unsigned 32-bit seed")
    return value


def instruction_text(request):
    return "You are a helpful assistant. " + request["instructions"] + "<|endofprompt|>"


def validate_setup(setup, model_path):
    if setup.get("model_id") != MODEL_ID or Path(setup["model_path"]).resolve() != model_path.resolve():
        raise ValueError("Use the dedicated pinned CosyVoice3 model copy")
    if (model_path / "spk2info.pt").exists():
        raise ValueError("Private speaker databases are not permitted in this audition")
    records = setup.get("files", [])
    names = {item["file"] for item in records}
    if names != MODEL_FILES or len(records) != len(names):
        raise ValueError("Pinned model manifest is incomplete")
    for item in records:
        path = (model_path / item["file"]).resolve()
        if not path.is_relative_to(model_path.resolve()) or file_sha256(path) != item["sha256"]:
            raise ValueError("Pinned model file changed")
    reference = Path(setup["reference"])
    if file_sha256(reference) != setup["reference_sha256"]:
        raise ValueError("Official reference audio changed")
    source = setup.get("reference_source", "")
    if not source.startswith("https://raw.githubusercontent.com/FunAudioLLM/CosyVoice/"):
        raise ValueError("Use the declared official demo reference, not a private voice")
    return reference


def save_result(directory, request, engine, data, elapsed):
    with wave.open(io.BytesIO(data)) as audio:
        frames = audio.getnframes()
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or frames <= 0:
            raise ValueError("Expected nonempty mono PCM16 WAV")
        if len(audio.readframes(frames)) != frames * 2:
            raise ValueError("Truncated WAV")
        rate = audio.getframerate()
    target, receipt = directory / "cosyvoice3.wav", directory / "receipt.json"
    if target.exists() or receipt.exists():
        raise ValueError("Existing audition output is not overwritten")
    record = {"schema_version": 1, "request": request, "engine": engine,
              "wav_sha256": hashlib.sha256(data).hexdigest(), "sample_rate": rate,
              "duration_seconds": frames / rate, "generation_seconds": elapsed,
              "acceptance": "generated_not_listening_approved",
              "limitations": ["Official demo reference is for this internal audition, not commercial voice clearance",
                              "Different reference voice and engine: not a model-only causal comparison",
                              "Same style guidance does not guarantee identical prosody"],
              "writer": "CosyVoice audition adapter", "consumers": ["user", "audio reviewer", "maintainer"],
              "lifecycle": "This immutable candidate and its exact inputs",
              "invalidation": "Text, guidance, reference, model, source, environment or WAV hashes change"}
    with target.open("xb") as stream:
        stream.write(data)
    with receipt.open("xb") as stream:
        stream.write(canonical(record))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--setup-receipt", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = validate_request(json.loads(args.request.read_text(encoding="utf-8-sig")))
    setup = json.loads(args.setup_receipt.read_text(encoding="utf-8-sig"))
    model_path, repo = Path(setup["model_path"]).resolve(), args.repo.resolve()
    reference = validate_setup(setup, model_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(exist_ok=False)
    state = {"pid": os.getpid(), "status": "starting", "request": request,
             "started_at": datetime.now(timezone.utc).isoformat(),
             "writer": "CosyVoice audition adapter", "consumers": ["operator"],
             "lifecycle": "One process attempt; retain failures", "invalidation": "Process exit or source/input changes"}
    state_path = args.output / "state.json"
    state_path.write_bytes(canonical(state))
    log = (args.output / "generation.log").open("x", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                       "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(repo), str(repo / "third_party" / "Matcha-TTS")]
    try:
        import numpy as np
        import soundfile
        import torch
        from cosyvoice.cli.cosyvoice import CosyVoice3
        from cosyvoice.utils.common import set_all_random_seed

        if not torch.cuda.is_available():
            raise ValueError("CUDA required; no implicit CPU fallback")
        packages = {}
        for name in ("torch", "torchaudio", "onnxruntime", "onnxruntime-gpu", "transformers", "numpy", "soundfile"):
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                pass
        source_files = ("cosyvoice/cli/cosyvoice.py", "cosyvoice/cli/frontend.py", "cosyvoice/cli/model.py",
                        "cosyvoice/utils/common.py", "cosyvoice/tokenizer/tokenizer.py")
        engine = {"model": MODEL_ID, "revision": setup["revision"],
                  "model_manifest_sha256": hashlib.sha256(canonical(setup["files"])).hexdigest(),
                  "reference_sha256": setup["reference_sha256"], "reference_source": setup["reference_source"],
                  "adapter_sha256": file_sha256(__file__),
                  "repo_commit": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
                  "source_sha256": {name: file_sha256(repo / name) for name in source_files},
                  "python": sys.version, "packages": packages, "gpu": torch.cuda.get_device_name(0),
                  "fp16": False, "stream": False, "speed": 1.0, "text_frontend": False,
                  "instruct_text": instruction_text(request)}
        started = time.monotonic()
        model = CosyVoice3(str(model_path), load_trt=False, load_vllm=False, fp16=False)
        engine["model_load_seconds"] = time.monotonic() - started
        state["status"] = "generating"
        state_path.write_bytes(canonical(state))
        set_all_random_seed(request["seed"])
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        chunks = [chunk["tts_speech"].detach().float().cpu() for chunk in model.inference_instruct2(
            request["input"], instruction_text(request), str(reference), stream=False, speed=1.0, text_frontend=False)]
        if not chunks:
            raise ValueError("Engine returned no audio")
        samples = torch.cat(chunks, dim=1).squeeze(0).numpy()
        if samples.ndim != 1 or not np.isfinite(samples).all():
            raise ValueError("Invalid engine audio")
        stream = io.BytesIO()
        soundfile.write(stream, samples, model.sample_rate, format="WAV", subtype="PCM_16")
        engine["peak_torch_allocated_mib"] = torch.cuda.max_memory_allocated() / 1024**2
        record = save_result(args.output, request, engine, stream.getvalue(), time.monotonic() - started)
        state.update({"status": record["acceptance"], "wav_sha256": record["wav_sha256"]})
        state_path.write_bytes(canonical(state))
        print(json.dumps(record, ensure_ascii=False), flush=True)
    except Exception as exc:
        state.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        state_path.write_bytes(canonical(state))
        raise


if __name__ == "__main__":
    main()
