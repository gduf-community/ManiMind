r"""Offline, variable-length V01 first takes, without alignment or publishing.

Copy this file beside the frozen voxcpm_audition.py (no project install needed):
  python flexible_voxcpm.py generate --plan PLAN --model MODEL \
    --setup-receipt SETUP --reference V01.wav --output NEW_DIRECTORY

Schema 2 requires the fixed reference_sha256, reference_text and generation below,
a nonempty reference_source string, synthetic_reference: true, and a nonempty
segments list of {id, cue, focus, text}. Other metadata is preserved, not executed.
IDs are unique case-insensitively and Windows-safe ASCII alphanumerics/_/-.
No anchor, relation, timestamp, segment count or visual approval is inferred.

Windows deployment is pending GPU validation. An operator must pause Qwen and
coordinate a maintenance window first; the separate flexible runner restores it.
The worker acquires the existing cross-engine mutex itself; do not wrap it in an
old runner holding that mutex. Without --gpu-baseline, GPU processes fail closed.
With it, nvidia-smi -q -x must report one GPU and only exactly covered occupants.
Nothing is stopped, resumed or retried by this worker.

Optional operator-written baseline JSON (never generated/approved by the worker):
  {"schema_version": 1, "purpose": "approved_shared_desktop_occupants",
   "approved": true, "operator": "operator identity", "exclusive_gpu": false,
   "approved_at": "2026-10-27T10:00:00+00:00",
   "expires_at": "2026-10-27T10:20:00+00:00",
   "gpu_uuid": "GPU-<actual uuid>", "driver_version": "610.47",
   "processes": [{"pid": 123, "type": "C+G",
     "process_name": "C:\\Windows\\System32\\dwm.exe",
     "approved_shared_desktop_occupant": true,
     "reason": "Operator inspected this PID and full path: Windows desktop compositor"}]}
The operator inspects EVERY PID/path after pausing Qwen, then explicitly approves
each desktop occupant with a nonempty reason. There is no app-name allowlist;
interpreters/model executors are denied even with approval. An unfamiliar process
whose desktop purpose cannot be established must not be approved. This is a
single-operator supervised declaration, not executable authentication or a way to
automatically discover arbitrary disguised model workers. Lifetime is at most 20 minutes,
consumed once at pre-load inspection by this worker; expiry, GPU/driver/identity
change or a new process invalidates permission. Archived baseline and GPU evidence
are historical, consumed by operators/auditors, not reusable live authorization.
This permits shared desktop occupants, NOT an empty/exclusive GPU claim. NVIDIA
identity tuples do not attest executable bytes, prevent PID reuse or future work.

All new files are attempt-scoped derived output, not project/session context.
The worker writes; operators, audio reviewers and future focus schedulers consume.
state.json is live only during this process; snapshots/receipts/failures persist.
Any input, code, setup, software or media change invalidates their applicability.
An interrupted/unknown process requires inspection, never an implicit rerun. Only
a brand-new directory is accepted. Receipts grant no listening/alignment approval,
real-person voice permission, final mixing permission or publication approval.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PureWindowsPath
import random
import re
import subprocess
import sys
import tempfile
import time
import traceback
import wave
import xml.etree.ElementTree as ET

if __package__:
    from . import voxcpm_audition as audition
else:
    import voxcpm_audition as audition


REFERENCE_SHA256 = "b36f1c933b6d452df52e85571bd8de995f8513c2033e8c3d1d923a7cb79c0be9"
HELPER_SHA256 = "10766c863d5f6f1f7c4dd337e9f0ca267ce9198bac1f8bbe6d2e80b4a0d567fc"
# Canonical file->sha256 map from the frozen 2026-10-25 official setup receipt.
MODEL_FILES_SHA256 = "5c755cf99025acbc653d245c017782f4b0484ca53a9fba71037d74378030d9f5"
GENERATION = {"seed": 42, "cfg_value": 2.0, "inference_timesteps": 10,
              "normalize": False, "denoise": False, "retry_badcase": False}
SEED_METHOD = audition.SEED_METHOD
GPU_MUTEX = "Global\\ManiMind-VoiceDesign-Audition"
ACCEPTANCE = "generated_not_listening_or_alignment_approved"
PROVENANCE = {
    "writer": "Flexible VoxCPM2 audio worker",
    "consumers": ["operator", "audio reviewer", "focus scheduler"],
    "lifecycle": "One create-only process attempt; preserve first takes and failures",
    "invalidation": "Process exit invalidates live state; input/code/setup/software/media changes invalidate reuse",
}
GPU_BASELINE_TTL_SECONDS = 20 * 60
# Explicit desktop approval cannot authorize interpreters or known model runners.
EXECUTOR_BASENAMES = frozenset({
    "py.exe", "pyw.exe", "ipy.exe", "ipy64.exe", "jupyter.exe",
    "node.exe", "nodejs.exe", "deno.exe", "bun.exe", "java.exe", "javaw.exe", "dotnet.exe",
    "powershell.exe", "powershell_ise.exe", "pwsh.exe", "cmd.exe", "cscript.exe", "wscript.exe",
    "wsl.exe", "wslhost.exe", "bash.exe", "sh.exe", "zsh.exe", "ruby.exe", "perl.exe",
    "r.exe", "rscript.exe", "julia.exe", "lua.exe", "luajit.exe", "uv.exe", "uvx.exe",
    "conda.exe", "mamba.exe", "micromamba.exe", "inference.exe", "tritonserver.exe", "worker.exe", "model.exe",
})
MODEL_EXECUTION_PATH = re.compile(
    r"python|pypy|conda|(?:^|[\\/])(?:\.?venv|models?|checkpoints|huggingface)(?:[\\/]|$)|"
    r"qwen|voxcpm|cosyvoice|kokoro|index[-_ ]?tts|whisper|ollama|llama|vllm|torch|comfyui|stable[-_ ]?diffusion|automatic1111|"
    r"lm[-_ ]?studio|koboldcpp|gpt4all|oobabooga|text[-_ ]generation|"
    r"model[-_ ]?(?:worker|server|runner)|inference[-_ ]?(?:worker|server|runner)", re.I)
GPU_LIMITATIONS = [
    "Approved shared desktop occupants only; generation does not prove exclusive GPU access",
    "used_memory=N/A is not zero memory or evidence of inactivity",
    "NVIDIA PID/type/process_name is not executable attestation and cannot rule out PID reuse or renamed workers",
    "Point-in-time pre-load inspection, not a GPU scheduler or a guarantee against later processes",
]


def validate_plan(value):
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 2 or value.get("reference_sha256") != REFERENCE_SHA256
            or value.get("reference_text") != audition.TEXT
            or audition.canonical(value.get("generation")) != audition.canonical(GENERATION)):
        raise ValueError("Require schema 2, exact V01 hash/text and fixed generation settings")
    if (value.get("synthetic_reference") is not True
            or not isinstance(value.get("reference_source"), str) or not value["reference_source"].strip()):
        raise ValueError("Declare synthetic_reference: true and a nonempty reference_source")
    segments = value.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("Require a nonempty segments list")
    seen = set()
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)}
    for segment in segments:
        identity = segment.get("id") if isinstance(segment, dict) else None
        if (not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", identity)
                or identity.upper() in reserved or identity.casefold() in seen):
            raise ValueError("Require unique Windows-safe segment IDs (including case)")
        seen.add(identity.casefold())
        if any(not isinstance(segment.get(key), str) or not segment[key].strip()
               for key in ("cue", "focus", "text")):
            raise ValueError("Every segment requires nonempty cue, focus and text")
    return value


def model_files_sha256(setup):
    return hashlib.sha256(audition.canonical({item["file"]: item["sha256"] for item in setup["files"]})).hexdigest()


def generate_kwargs(segment, reference, reference_text):
    return {"text": segment["text"], "reference_wav_path": str(reference),
            "prompt_wav_path": str(reference), "prompt_text": reference_text,
            **{key: value for key, value in GENERATION.items() if key != "seed"}}


def _kernel32():
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    kernel.ReleaseMutex.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


def _process_identity(value):
    if (not isinstance(value, dict) or type(value.get("pid")) is not int or value["pid"] <= 0
            or value.get("type") not in ("C", "G", "C+G")
            or not isinstance(value.get("process_name"), str)):
        raise ValueError("GPU process requires positive integer pid, supported type and process_name")
    name = value["process_name"]
    path = PureWindowsPath(name)
    if (not name or name != name.strip() or any(ord(c) < 32 for c in name)
            or not re.match(r"^[A-Za-z]:\\", name) or not path.is_absolute()
            or str(path) != name
            or any(part in (".", "..") or part.endswith((".", " ")) for part in name.split("\\"))
            or path.suffix.casefold() != ".exe" or any(c in name[2:] for c in ':"<>|?*')):
        raise ValueError("GPU process_name must be an inspectable absolute Windows executable path")
    return value["pid"], value["type"], name


def parse_gpu_xml(payload):
    """Read NVIDIA's single-GPU process inventory; unsupported/ambiguous data blocks."""
    def field(element, tag):
        children = element.findall(tag)
        if len(children) != 1 or len(children[0]) or not children[0].text or not children[0].text.strip():
            raise ValueError("Missing or ambiguous GPU XML field: " + tag)
        if tag == "process_name" and children[0].text != children[0].text.strip():
            raise ValueError("Ambiguous GPU XML process_name whitespace")
        return children[0].text.strip()

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("Cannot parse nvidia-smi GPU XML") from exc
    gpus = root.findall("gpu")
    if root.tag != "nvidia_smi_log" or len(gpus) != 1 or field(root, "attached_gpus") != "1":
        raise ValueError("Require a supported single-GPU NVIDIA XML inventory")
    gpu = gpus[0]
    uuid, driver = field(gpu, "uuid"), field(root, "driver_version")
    if (not re.fullmatch(r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", uuid)
            or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", driver)):
        raise ValueError("Unsupported GPU UUID or driver_version")
    inventories = gpu.findall("processes")
    if (len(inventories) != 1 or (inventories[0].text or "").strip()
            or any(item.tag != "process_info" for item in inventories[0])):
        raise ValueError("Unsupported or missing GPU process inventory")
    processes, seen = [], set()
    for item in inventories[0]:
        pid = field(item, "pid")
        if not re.fullmatch(r"[1-9][0-9]*", pid):
            raise ValueError("Unsupported GPU process pid")
        process = {"pid": int(pid), "type": field(item, "type"), "process_name": field(item, "process_name")}
        identity = _process_identity(process)
        if identity[0] in seen:
            raise ValueError("Duplicate GPU process pid")
        seen.add(identity[0])
        processes.append(process)
    return {"gpu_uuid": uuid, "driver_version": driver, "processes": processes}


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate GPU baseline JSON field: " + key)
        result[key] = value
    return result


def validate_gpu_baseline(baseline, current, now=None):
    """Validate explicit operator permission, not an assertion of an idle GPU."""
    if (not isinstance(baseline, dict) or type(baseline.get("schema_version")) is not int
            or baseline["schema_version"] != 1 or baseline.get("approved") is not True
            or baseline.get("purpose") != "approved_shared_desktop_occupants"
            or baseline.get("exclusive_gpu") is not False
            or not isinstance(baseline.get("operator"), str) or not baseline["operator"].strip()):
        raise ValueError("Require explicitly operator-approved shared desktop GPU baseline, not exclusive GPU permission")
    try:
        approved = datetime.fromisoformat(baseline["approved_at"])
        expires = datetime.fromisoformat(baseline["expires_at"])
        if approved.utcoffset() is None or expires.utcoffset() is None:
            raise ValueError("Timezone required")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("GPU baseline requires timezone-aware approved_at and expires_at") from exc
    now = now if now is not None else datetime.now(timezone.utc)
    if not (0 < (expires - approved).total_seconds() <= GPU_BASELINE_TTL_SECONDS and approved <= now < expires):
        raise ValueError("GPU baseline expired, future-dated or exceeds the 20 minute lifetime")
    if any(baseline.get(key) != current[key] for key in ("gpu_uuid", "driver_version")):
        raise ValueError("GPU baseline GPU/driver identity changed")
    processes = baseline.get("processes")
    if not isinstance(processes, list):
        raise ValueError("GPU baseline requires an explicit processes list")
    allowed, pids = set(), set()
    for process in processes:
        identity = _process_identity(process)
        name = PureWindowsPath(identity[2]).name.casefold()
        if (process.get("approved_shared_desktop_occupant") is not True
                or not isinstance(process.get("reason"), str) or not process["reason"].strip()):
            raise ValueError("GPU baseline requires explicit desktop approval and a nonempty operator reason for every PID")
        if (name in EXECUTOR_BASENAMES or MODEL_EXECUTION_PATH.search(identity[2])
                or re.fullmatch(r"pip[0-9.]*\.exe", name)):
            raise ValueError("GPU baseline refuses unapproved desktop occupant, interpreter or unknown model worker: " + identity[2])
        if identity[0] in pids:
            raise ValueError("Duplicate GPU baseline pid")
        pids.add(identity[0])
        allowed.add(identity)
    uncovered = [item for item in current["processes"] if _process_identity(item) not in allowed]
    if uncovered:
        raise ValueError("GPU baseline does not exactly cover current process identities: " + json.dumps(uncovered))
    return baseline


def _gpu_preflight(gpu_baseline=None):
    # Match the existing maintenance-window gate; no service control or network.
    command = ("$ErrorActionPreference='Stop'; "
               "$t=Get-ScheduledTask -TaskName 'ManiMind-QwenVoice-5080'; "
               "if ([string]$t.State -ne 'Ready' -or "
               "(Get-NetTCPConnection -ErrorAction Stop | Where-Object "
               "{ $_.LocalPort -eq 8766 -and $_.State -eq 'Listen' })) "
               "{throw 'Pause Qwen in an operator-coordinated maintenance window first'}")
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                   check=True, capture_output=True, text=True, timeout=30)
    if gpu_baseline is not None:
        payload = Path(gpu_baseline).read_bytes()
        baseline = json.loads(payload.decode("utf-8-sig"), object_pairs_hook=_unique_json_object)
        audition.canonical(baseline)  # Reject non-JSON NaN/Infinity, including in metadata.
        result = subprocess.run(["nvidia-smi", "-q", "-x"],
                                check=True, capture_output=True, text=True, timeout=30)
        current = parse_gpu_xml(result.stdout)
        validate_gpu_baseline(baseline, current)
        return {"qwen_task_and_port": "inactive", "mutex": GPU_MUTEX, **current,
                "checked_at": datetime.now(timezone.utc).isoformat(), "exclusive_gpu": False,
                "mode": "operator_approved_shared_desktop", "limitations": GPU_LIMITATIONS,
                "baseline": baseline, "baseline_sha256": hashlib.sha256(payload).hexdigest(),
                "baseline_writer": baseline["operator"], "consumers": ["worker", "operator", "auditor"],
                "lifecycle": "One pre-load check within the operator's at-most-20-minute approval window",
                "invalidation": "Expiry, GPU/driver/process identity change or new process; archive is historical only",
                "nvidia_smi_xml": result.stdout, "xml_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()}
    result = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"],
                            check=True, capture_output=True, text=True, timeout=30)
    if result.stdout.strip():
        raise RuntimeError("GPU processes present or unknown; inspect before any new attempt: " + result.stdout.strip())
    return {"qwen_task_and_port": "inactive", "gpu_compute_processes": [], "mutex": GPU_MUTEX}


@contextmanager
def gpu_slot(gpu_baseline=None):
    if sys.platform != "win32":
        raise RuntimeError("Windows CUDA maintenance worker only; no implicit platform/CPU fallback")
    kernel = _kernel32()
    handle = kernel.CreateMutexW(None, False, GPU_MUTEX)
    if not handle:
        raise OSError("Cannot open the shared GPU mutex")
    owned = False
    try:
        result = kernel.WaitForSingleObject(handle, 0)
        owned = result in (0, 0x80)
        if result == 0x80:
            raise RuntimeError("Abandoned GPU mutex; unknown previous process outcome requires inspection")
        if result != 0:
            raise RuntimeError("GPU mutex busy or uninspectable; no wait or implicit retry")
        yield _gpu_preflight() if gpu_baseline is None else _gpu_preflight(gpu_baseline)
    finally:
        try:
            if owned and not kernel.ReleaseMutex(handle):
                raise OSError("Failed to release shared GPU mutex; inspect process state")
        finally:
            kernel.CloseHandle(handle)


def _write_state(output, state):
    """Retry only a Windows reader's temporary rename lock, never inference.

    Each update owns a unique staging file. Failed files remain diagnostic
    evidence and cannot prevent the exception handler writing a new snapshot.
    """
    payload = audition.canonical(state)
    descriptor, name = tempfile.mkstemp(prefix="state-", suffix=".json.tmp", dir=output)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    for attempt in range(8):
        try:
            os.replace(name, output / "state.json")
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (5, 32) or attempt == 7:
                raise
            time.sleep(.025 * (attempt + 1))


def generate(model_path, output, setup_path, plan_path, reference_path, gpu_baseline=None):
    model_path, output, setup_path, plan_path, reference_path = (
        Path(path).resolve() for path in (model_path, output, setup_path, plan_path, reference_path))
    sources = (setup_path, plan_path, reference_path, Path(__file__).resolve(), Path(audition.__file__).resolve())
    if gpu_baseline is not None:
        gpu_baseline = Path(gpu_baseline).resolve()
        sources += (gpu_baseline,)
    if (output.is_relative_to(model_path) or model_path.is_relative_to(output)
            or any(path.is_relative_to(output) for path in sources)):
        raise ValueError("Use a new output directory separate from all source inputs")
    output.mkdir(parents=True, exist_ok=False)
    started_run, progress = time.monotonic(), sys.stdout
    state = {"schema_version": 2, **PROVENANCE, "pid": os.getpid(), "status": "validating",
             "started_at": datetime.now(timezone.utc).isoformat(), "attempted": [], "done": [],
             "call_count": 0, "model_load_count": 0, "seed_method": SEED_METHOD}

    def update(**changes):
        state.update(changes)
        _write_state(output, state)

    def emit(event, **details):
        print(json.dumps({"event": event, "pid": state["pid"], "call_count": state["call_count"],
                          "done_count": len(state["done"]), **details}), file=progress, flush=True)

    update()
    try:
        source = output / "source"
        source.mkdir()
        for module in (Path(__file__), Path(audition.__file__)):
            with (source / module.name).open("xb") as stream:
                stream.write(module.read_bytes())
        bindings = {"worker_sha256": audition.sha(source / "flexible_voxcpm.py"),
                    "helper_sha256": audition.sha(source / "voxcpm_audition.py")}
        if gpu_baseline is not None:
            payload = gpu_baseline.read_bytes()
            with (output / "gpu-baseline.json").open("xb") as stream:
                stream.write(payload)
            bindings["gpu_baseline_sha256"] = hashlib.sha256(payload).hexdigest()
        update(**bindings)
        if bindings["helper_sha256"] != HELPER_SHA256:
            raise ValueError("Require the frozen audition helper SHA256")
        plan_bytes, setup_bytes = plan_path.read_bytes(), setup_path.read_bytes()
        for name, payload in (("plan.json", plan_bytes), ("setup-receipt.json", setup_bytes)):
            with (output / name).open("xb") as stream:
                stream.write(payload)
        bindings.update(plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
                        setup_sha256=hashlib.sha256(setup_bytes).hexdigest())
        update(**bindings)
        plan = validate_plan(json.loads(plan_bytes.decode("utf-8-sig")))
        setup = json.loads(setup_bytes.decode("utf-8-sig"))
        root = audition.validate_setup(setup, model_path)
        if model_files_sha256(setup) != MODEL_FILES_SHA256:
            raise ValueError("Model file manifest differs from the frozen official setup")
        if audition.sha(reference_path) != plan["reference_sha256"]:
            raise ValueError("Reference SHA256 mismatch; only selected synthetic V01 is allowed")
        reference = output / "reference.wav"
        with reference_path.open("rb") as original, reference.open("xb") as archived:
            for block in iter(lambda: original.read(1024 * 1024), b""):
                archived.write(block)
        if audition.sha(reference) != plan["reference_sha256"]:
            raise ValueError("Reference SHA256 changed during copying")
        with wave.open(str(reference), "rb") as audio:
            if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (48000, 1, 2) or audio.getnframes() <= 0:
                raise ValueError("V01 must remain nonempty native mono 48000 Hz PCM16 WAV")
        bindings["reference_sha256"] = plan["reference_sha256"]
        update(**bindings, reference_source=plan["reference_source"], synthetic_reference=True,
               reference_input_path=str(reference_path), reference_path=str(reference))
        requests = [{"id": segment["id"], "request": generate_kwargs(segment, reference, plan["reference_text"]),
                     "seed": GENERATION["seed"], "seed_method": SEED_METHOD} for segment in plan["segments"]]
        audition.write_json(output / "requests.json", {"schema_version": 2, **PROVENANCE, **bindings, "segments": requests})
        os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                           "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"})
        update(status="acquiring_gpu_slot")
        slot_context = gpu_slot() if gpu_baseline is None else gpu_slot(output / "gpu-baseline.json")
        with slot_context as slot, (output / "generation.log").open("x", encoding="utf-8", buffering=1) as log, \
                redirect_stdout(log), redirect_stderr(log):
            update(status="loading", gpu_slot=slot)
            audition.write_json(output / "gpu-evidence.json", {**PROVENANCE, **slot})
            packages = {}
            for name in ("voxcpm", "torch", "torchaudio", "transformers", "numpy", "safetensors", "huggingface-hub", "tokenizers", "sentencepiece"):
                try:
                    packages[name] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    packages[name] = None
            if packages["voxcpm"] != "2.0.3":
                raise ValueError("Require the pinned official VoxCPM 2.0.3 reference API")
            import torch
            import numpy as np
            from voxcpm import VoxCPM

            if not torch.cuda.is_available():
                raise ValueError("CUDA is required; no CPU fallback")
            emit("loading", total_segments=len(requests))
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            update(model_load_count=1)
            started = time.monotonic()
            model = VoxCPM.from_pretrained(str(root), **audition.LOAD_OPTIONS)
            torch.cuda.synchronize()
            engine = {"schema_version": 2, **PROVENANCE, **bindings, "packages": packages,
                      "model": audition.MODEL, "revision": setup["revision"], "declared_license": setup["declared_license"],
                      "model_files": setup["files"], "model_files_sha256": model_files_sha256(setup),
                      "python": sys.version, "platform": sys.platform, "gpu_slot": slot,
                      "cuda_runtime": torch.version.cuda, "gpu": torch.cuda.get_device_name(),
                      "load_options": audition.LOAD_OPTIONS, "seed_method": SEED_METHOD, "model_load_count": 1,
                      "model_load_seconds": time.monotonic() - started,
                      "load_peak_torch_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
                      "load_peak_torch_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2}
            audition.write_json(output / "engine.json", engine)
            rate = model.tts_model.sample_rate
            if type(rate) is not int or rate != audition.SAMPLE_RATE:
                raise ValueError("Require native 48000 Hz output; no resampling")
            for segment, request in zip(plan["segments"], requests, strict=True):
                identity, kwargs = segment["id"], request["request"]
                if audition.sha(reference) != bindings["reference_sha256"]:
                    raise ValueError("Archived reference SHA256 changed before a take")
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
                allocated = torch.cuda.max_memory_allocated() / 1024**2
                reserved = torch.cuda.max_memory_reserved() / 1024**2
                measured = audition.save_audio(output, identity, samples, rate)
                record = {"schema_version": 2, **PROVENANCE, **bindings, **measured,
                          "id": identity, "segment": segment, "request": kwargs, "generate_kwargs": kwargs,
                          "reference_source": plan["reference_source"], "synthetic_reference": True,
                          "seed": GENERATION["seed"], "seed_method": SEED_METHOD, "engine": engine,
                          "generation_seconds": elapsed, "peak_torch_allocated_mib": allocated,
                          "peak_torch_reserved_mib": reserved, "pid": state["pid"],
                          "call_count": state["call_count"], "segment_call_count": 1, "first_take": True,
                          "model_load_count": state["model_load_count"], "acceptance": ACCEPTANCE}
                audition.write_json(output / f"{identity}.receipt.json", record)
                state["done"].append(identity)
                update()
                emit("segment_done", id=identity, duration_seconds=measured["duration_seconds"], generation_seconds=elapsed)
        update(status=ACCEPTANCE, current_segment=None, current_request=None,
               finished_at=datetime.now(timezone.utc).isoformat(), total_seconds=time.monotonic() - started_run)
        emit("completed", total_segments=len(state["done"]))
        return state
    except BaseException as exc:
        diagnostics = {}
        if isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
            diagnostics = {"command": exc.cmd, "stdout": str(exc.stdout or ""), "stderr": str(exc.stderr or "")}
        audition.write_json(output / "failure.json", {"schema_version": 2, **PROVENANCE,
                            "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(),
                            "state": state, "subprocess_diagnostics": diagnostics, "automatic_retry": False})
        update(status="failed", error_type=type(exc).__name__, error=str(exc),
               finished_at=datetime.now(timezone.utc).isoformat(), total_seconds=time.monotonic() - started_run)
        emit("failed", id=state.get("current_segment"), error_type=type(exc).__name__, error=str(exc))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("generate", help="Generate each schema-2 segment once using selected synthetic V01")
    for name in ("plan", "model", "setup-receipt", "reference", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)
    command.add_argument("--gpu-baseline", type=Path,
                         help="Explicit, at-most-20-minute operator permission for exactly covered shared desktop occupants")
    args = parser.parse_args(argv)
    optional = {} if args.gpu_baseline is None else {"gpu_baseline": args.gpu_baseline}
    state = generate(args.model, args.output, args.setup_receipt, args.plan, args.reference, **optional)
    print(json.dumps({"output": str(args.output), "status": state["status"], "done": state["done"]}), flush=True)


if __name__ == "__main__":
    main()
