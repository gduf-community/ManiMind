"""Loopback-only Qwen3-TTS worker, usable as a standalone Windows script."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Literal
import wave

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

MODEL = "qwen3-tts-1.7b-customvoice"
VOICES = ("Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def wav_info(data: bytes) -> dict:
    with wave.open(io.BytesIO(data)) as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getnframes() <= 0:
            raise ValueError("Expected nonempty mono PCM16 WAV")
        return {"sample_rate": audio.getframerate(), "duration_seconds": audio.getnframes() / audio.getframerate()}


def validate_model_path(model_path: Path):
    config = model_path / "config.json"
    if not model_path.is_dir() or not config.is_file():
        raise ValueError("Supply an existing local CustomVoice model directory")
    value = json.loads(config.read_text(encoding="utf-8"))
    if value.get("tts_model_type") != "custom_voice" or value.get("tts_model_size") != "1b7":
        raise ValueError("This worker requires the 1.7B CustomVoice variant, not a clone or design model")
    if not any(model_path.rglob("*.safetensors")):
        raise ValueError("Local model weights are missing")


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    input: str = Field(min_length=1, max_length=600)
    voice: str = "Uncle_Fu"
    instructions: str = Field(default="", max_length=1000)
    language: Literal["Chinese", "English", "Auto"] = "Chinese"
    model: Literal["qwen3-tts-1.7b-customvoice"] = MODEL
    response_format: Literal["wav"] = "wav"

    @field_validator("input")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Speech text is empty")
        return value

    @field_validator("voice")
    @classmethod
    def known_voice(cls, value):
        if value not in VOICES:
            raise ValueError("Select a built-in voice")
        return value


class BusyError(RuntimeError):
    pass


class SpeechEngine:
    def __init__(self, backend, cache: Path):
        self.backend = backend
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def synthesize(self, request: SpeechRequest):
        if not self.lock.acquire(blocking=False):
            raise BusyError("GPU worker is busy; request has not started")
        try:
            payload = request.model_dump()
            key = digest(canonical({"request": payload, "engine": self.backend.manifest}))
            audio, receipt = self.cache / f"{key}.wav", self.cache / f"{key}.json"
            if audio.exists() and receipt.exists():
                data = audio.read_bytes()
                record = json.loads(receipt.read_text(encoding="utf-8"))
                if record["wav_sha256"] != digest(data) or record["request"] != payload:
                    raise ValueError("Cached audio receipt changed")
                wav_info(data)
                return data, {**record, "cache_hit": True}
            started = time.monotonic()
            data = self.backend.generate(payload)
            measured = wav_info(data)
            record = {"schema_version": 1, "request_id": key, "request": payload,
                      "engine": self.backend.manifest, "wav_sha256": digest(data), **measured,
                      "elapsed_seconds": time.monotonic() - started, "cache_hit": False,
                      "created_at": datetime.now(timezone.utc).isoformat(),
                      "scope": "Generated audio; not listening or media acceptance",
                      "writer": "GPU speech worker", "consumers": ["client", "auditor"],
                      "lifecycle": "Cached for identical request and engine fingerprint",
                      "invalidation": "Request, weights, worker or cached bytes change"}
            temporary = audio.with_suffix(".wav.tmp")
            temporary.write_bytes(data)
            temporary.replace(audio)
            temporary = receipt.with_suffix(".json.tmp")
            temporary.write_bytes(canonical(record))
            temporary.replace(receipt)
            return data, record
        finally:
            self.lock.release()


class QwenBackend:
    def __init__(self, model_path: Path):
        validate_model_path(model_path)
        import importlib.metadata
        import torch
        import soundfile
        from qwen_tts import Qwen3TTSModel

        if not torch.cuda.is_available():
            raise ValueError("CUDA GPU is required; no implicit CPU fallback")
        files = sorted(p for p in model_path.rglob("*") if p.is_file() and p.suffix in {".json", ".safetensors", ".txt"})
        fingerprints = {}
        for path in files:
            sha = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    sha.update(block)
            fingerprints[str(path.relative_to(model_path)).replace("\\", "/")] = sha.hexdigest()
        self.manifest = {"model": MODEL, "model_files_sha256": digest(canonical(fingerprints)),
                         "worker_sha256": digest(Path(__file__).read_bytes()),
                         "qwen_tts_version": importlib.metadata.version("qwen-tts"),
                         "torch_version": torch.__version__, "cuda_runtime": torch.version.cuda,
                         "gpu": torch.cuda.get_device_name(0), "attention": "sdpa", "dtype": "bfloat16"}
        self.model = Qwen3TTSModel.from_pretrained(str(model_path), device_map="cuda:0",
            dtype=torch.bfloat16, attn_implementation="sdpa", local_files_only=True)
        self.soundfile, self.torch = soundfile, torch

    def generate(self, payload):
        self.torch.manual_seed(1729)
        with self.torch.inference_mode():
            wavs, rate = self.model.generate_custom_voice(text=payload["input"], language=payload["language"],
                speaker=payload["voice"], instruct=payload["instructions"] or None,
                max_new_tokens=2048)
        stream = io.BytesIO()
        self.soundfile.write(stream, wavs[0], rate, format="WAV", subtype="PCM_16")
        return stream.getvalue()


def create_app(engine: SpeechEngine, token: str):
    if len(token) < 32 or any(c.isspace() for c in token):
        raise ValueError("A private token of at least 32 characters is required")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
            return Response(status_code=401)
        if request.method == "POST":
            length = request.headers.get("content-length", "")
            if not length.isdecimal() or len(length) > 10 or int(length) > 32768:
                return Response(status_code=413)
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"status": "ready", "engine": engine.backend.manifest, "busy": engine.lock.locked(),
                "scope": "Model loaded; generation and listening are separate checks"}

    @app.post("/v1/audio/speech")
    def speak(request: SpeechRequest):
        try:
            data, record = engine.synthesize(request)
        except BusyError as exc:
            raise HTTPException(status_code=503, detail=str(exc), headers={"Retry-After": "5"}) from exc
        except Exception as exc:
            print(json.dumps({"event": "speech_failed", "error_type": type(exc).__name__, "error": str(exc)}), flush=True)
            raise HTTPException(status_code=500, detail="Speech generation failed; inspect private worker log") from exc
        return Response(data, media_type="audio/wav", headers={
            "X-Request-ID": record["request_id"], "X-Audio-SHA256": record["wav_sha256"],
            "X-Audio-Duration": str(record["duration_seconds"]),
            "X-Synthesis-Seconds": str(record["elapsed_seconds"]),
            "X-Cache-Hit": "1" if record["cache_hit"] else "0"})

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--log-file", type=Path)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged port")
    token = args.token_file.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        parser.error("A strong private token is required")
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        stream = args.log_file.open("a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = stream
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("HF_HOME", str(args.cache.resolve().parent / "hf-cache"))
    engine = SpeechEngine(QwenBackend(args.model_path.resolve()), args.cache.resolve())
    print(json.dumps({"event": "model_loaded", "engine": engine.backend.manifest}), flush=True)
    import uvicorn
    uvicorn.run(create_app(engine, token), host="127.0.0.1", port=args.port, workers=1, access_log=False)


if __name__ == "__main__":
    main()
