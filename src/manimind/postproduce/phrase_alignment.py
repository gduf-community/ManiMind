"""Create-only, local forced alignment of references within complete meaning WAVs.

Run in runtime/tools/meaning-alignment-env with PYTHONPATH=src:
  python -m manimind.postproduce.phrase_alignment --plan PLAN --speech DIR --output NEW_JSON

Uses the official stable-ts API (https://github.com/jianfch/stable-ts, MIT), not
copied engine code. Each unit has one original, unedited WAV and generation
receipt. References are newline-separated for original_split=True. No TTS,
transcription, text repair, proportional timing, clipping or publishing occurs.

The output and sibling NEW_JSON.attempts/<UTC-UUID>/ evidence are create-only.
The worker writes; schedulers, operators and independent reviewers consume.
Evidence lasts for this attempt; interruption leaves an incomplete started.json,
never permission to retry automatically. Changes to any bound plan, WAV, receipt,
source, software, FFmpeg or model invalidate reuse. Downstream must rehash sources
and must reject smoke_only artifacts. This is model estimation, not listening,
pronunciation verification, phrase-ending improvement or publication approval.
Returned word estimates may have zero duration and are explicitly marked as
uncertain points; whole clauses must still have positive, ordered intervals.

Production consumers must call verify_production_timings(path, plan_path=...,
speech=...) and retain/compare its complete files/evidence_sha256 on every later
release. backend_factory output is explicitly test_only=True and rejected by
that read-only gate. Missing source/runtime/attempt evidence never defaults true.

For legacy-WAV smoke tests only, a plan may declare alignment_smoke_source with
generation_plan and generation_plan_sha256. The original receipt must match that
unaltered plan and its unit text/identity, not a fabricated new receipt. This
explicit exception propagates smoke_only=True and cannot be a production input.
"""

from __future__ import annotations

import argparse
import base64
import configparser
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import traceback
import uuid
import wave

from . import flexible_voxcpm as transport


ROOT = Path(__file__).resolve().parents[3]
ENV_ROOT = ROOT / "runtime/tools/meaning-alignment-env"
METHOD = "stable_whisper_forced_alignment"
TIMING_SCOPE = "model_estimated_forced_alignment_not_listening"
UPSTREAM_URL = "https://github.com/jianfch/stable-ts"
MODEL_SHA256 = {
    "base": "ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e",
    "small": "9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794",
}
PINNED_PACKAGES = {"stable-ts": "2.19.1", "openai-whisper": "20250625", "torch": "2.7.1",
                   "torchaudio": "2.7.1", "numpy": "2.2.6", "numba": "0.61.2",
                   "llvmlite": "0.44.0", "openai": "3.22.1", "pyyaml": "6.0.3"}
PROVENANCE = {
    "writer": "manimind.postproduce.phrase_alignment",
    "consumers": ["meaning-unit visual scheduler", "operator", "independent reviewer"],
    "lifecycle": "One create-only alignment attempt; retain raw results, inputs and failures",
    "invalidation": "Any plan, WAV, receipt, source, software, FFmpeg or model change invalidates reuse",
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_object)


def validate_plan(value):
    transport.validate_plan(value)
    for unit in value["segments"]:
        seen = set()
        if unit.get("focus_scope") != "meaning_unit_not_visual_focus":
            raise ValueError("Require focus_scope=meaning_unit_not_visual_focus")
        references = unit.get("references")
        if not isinstance(references, list) or not references:
            raise ValueError("Every meaning unit requires nonempty references")
        for reference in references:
            if (not isinstance(reference, dict)
                    or any(not isinstance(reference.get(k), str) or not reference[k].strip()
                           for k in ("id", "focus", "text"))):
                raise ValueError("Every reference requires nonempty id, focus and text")
            identity, text = reference["id"], reference["text"]
            if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", identity)
                    or identity in seen):
                raise ValueError("Require unique safe reference IDs within each unit")
            seen.add(identity)
            if text != text.strip() or any(c in text for c in "\r\n\t"):
                raise ValueError("Reference whitespace would change original_split boundaries")
        if "".join(row["text"] for row in references) != unit["text"]:
            raise ValueError("References must concatenate exactly to the original unit text")
    return value


def _interval(value, duration, previous, label, *, allow_instant=False):
    start, end = value.get("start"), value.get("end")
    if (type(start) not in (int, float) or type(end) not in (int, float)
            or not math.isfinite(start) or not math.isfinite(end)
            or not 0 <= start <= end <= duration or start < previous
            or start == end and not allow_instant):
        raise ValueError("Nonfinite, reversed, overlapping or out-of-bounds timing: " + label)
    return start, end


def _exact_text(actual, expected):
    # stable-ts prefixes lines with an ASCII token-boundary space, not speech text.
    return actual == expected or actual == " " + expected


def validate_result(result, references, duration):
    """Validate the actual returned clauses, never reconstruct missing segments."""
    segments = result.get("segments") if isinstance(result, dict) else None
    if not isinstance(segments, list) or len(segments) != len(references):
        raise ValueError("Alignment omitted or added reference clauses")
    phrases, previous = [], 0.0
    for segment, reference in zip(segments, references, strict=True):
        if not isinstance(segment, dict) or not _exact_text(segment.get("text"), reference["text"]):
            raise ValueError("Returned clause text changed: " + reference["id"])
        start, end = _interval(segment, duration, previous, reference["id"])
        previous = end
        phrase = {"id": reference["id"], "text": reference["text"], "start": start, "end": end}
        if "words" in segment:
            words = segment["words"]
            if not isinstance(words, list) or not words or any(not isinstance(w, dict) for w in words):
                raise ValueError("Malformed returned words: " + reference["id"])
            if any(not isinstance(w.get("word"), str) or not w["word"] for w in words):
                raise ValueError("Malformed returned word text: " + reference["id"])
            text = "".join(w["word"] for w in words)
            if not _exact_text(text, reference["text"]):
                raise ValueError("Returned word text changed: " + reference["id"])
            word_previous = start
            for word in words:
                _, word_previous = _interval(word, end, word_previous, reference["id"] + " word", allow_instant=True)
            if words[0]["start"] != start or words[-1]["end"] != end:
                raise ValueError("Word and clause boundaries differ: " + reference["id"])
            phrase["words"] = [{key: word[key] for key in ("word", "start", "end")} for word in words]
            instant = [index for index, word in enumerate(words) if word["start"] == word["end"]]
            if instant:
                phrase["instantaneous_word_indices"] = instant
                phrase["word_timing_warning"] = "Zero-duration tokens are uncertain point estimates, not measured speech intervals"
        phrases.append(phrase)
    return phrases


def _bind(path, bindings, archive=None):
    path = Path(path).absolute()
    path.resolve(strict=True)
    digest = sha256(path)
    bindings.append({"path": str(path), "sha256": digest})
    if archive is not None:
        with Path(archive).open("xb") as target:
            target.write(path.read_bytes())
        if sha256(archive) != digest:
            raise ValueError("Source changed while archiving: " + str(path))
        bindings.append({"path": str(Path(archive).absolute()), "sha256": digest})
    return digest


def _check_bindings(bindings):
    for item in bindings:
        if sha256(item["path"]) != item["sha256"]:
            raise ValueError("Bound source drift: " + item["path"])


def _wav_info(path):
    with wave.open(str(path), "rb") as audio:
        frames, rate = audio.getnframes(), audio.getframerate()
        channels, width = audio.getnchannels(), audio.getsampwidth()
        if frames <= 0 or rate <= 0 or audio.getcomptype() != "NONE":
            raise ValueError("Require a nonempty original PCM WAV")
        if len(audio.readframes(frames)) != frames * channels * width:
            raise ValueError("Truncated original WAV")
    return {"frames": frames, "sample_rate": rate, "channels": channels,
            "sample_width_bytes": width, "duration_seconds": frames / rate}


def _validate_receipt(receipt, unit, expected, plan_hash, wav_hash, info, reference_hash):
    if (type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 2
            or expected is None or any(expected[k] != unit[k] for k in ("id", "cue", "focus", "text"))
            or receipt.get("plan_sha256") != plan_hash
            or receipt.get("wav_sha256") != wav_hash or receipt.get("id") != unit["id"]
            or receipt.get("segment") != expected
            or receipt.get("request", {}).get("text") != unit["text"]
            or receipt.get("first_take") is not True or type(receipt.get("segment_call_count")) is not int
            or receipt["segment_call_count"] != 1 or receipt.get("acceptance") != transport.ACCEPTANCE
            or receipt.get("reference_sha256") != reference_hash):
        raise ValueError("Original speech receipt, plan or text mismatch: " + unit["id"])
    if any(receipt.get(key) != info[key] for key in info):
        raise ValueError("Original speech receipt WAV metadata mismatch: " + unit["id"])


def _speech_inputs(plan, plan_hash, speech, attempt, bindings):
    smoke = plan.get("alignment_smoke_source")
    generation_hash, generation_units = plan_hash, plan["segments"]
    if smoke is not None:
        if not isinstance(smoke, dict):
            raise ValueError("Malformed alignment_smoke_source")
        source = Path(smoke["generation_plan"])
        generation_hash = _bind(source, bindings, attempt / "generation-plan.json")
        if generation_hash != smoke.get("generation_plan_sha256"):
            raise ValueError("Smoke generation plan drift")
        generation_units = transport.validate_plan(_read_json(attempt / "generation-plan.json"))["segments"]
    inputs = []
    for unit in plan["segments"]:
        identity = unit["id"]
        wav, receipt_path = speech / f"{identity}.wav", speech / f"{identity}.receipt.json"
        wav_hash = _bind(wav, bindings)
        receipt_hash = _bind(receipt_path, bindings, attempt / f"{identity}.receipt.json")
        receipt, info = _read_json(attempt / f"{identity}.receipt.json"), _wav_info(wav)
        expected = next((row for row in generation_units if row["id"] == identity), None)
        _validate_receipt(receipt, unit, expected, generation_hash, wav_hash, info, plan["reference_sha256"])
        inputs.append({"id": identity, "wav": str(wav.resolve()), "wav_sha256": wav_hash,
                       "receipt": str(receipt_path.resolve()), "receipt_sha256": receipt_hash, **info})
    return inputs


def _production_software_identity(model):
    """Read the pinned local runtime identity without importing/loading a model."""
    if model not in MODEL_SHA256:
        raise ValueError("Unsupported production multilingual model")
    sites = list(ENV_ROOT.glob("lib/python*/site-packages"))
    if len(sites) != 1:
        raise ValueError("Require one isolated alignment site-packages directory")
    site = sites[0]
    distributions = list(importlib.metadata.distributions(path=[str(site)]))
    packages = {d.metadata["Name"]: d.version for d in distributions}
    normalized = {re.sub(r"[-_.]+", "-", name).lower(): version for name, version in packages.items()}
    if any(normalized.get(name) != version for name, version in PINNED_PACKAGES.items()):
        raise ValueError("Pinned production alignment dependency mismatch")
    checked = 0
    for distribution in distributions:
        engine = distribution.metadata["Name"].lower() in ("stable-ts", "openai-whisper")
        for entry in distribution.files or []:
            if entry.hash is None or (not engine and entry.suffix.lower() not in (".py", ".so", ".dylib")):
                continue
            path = Path(os.path.abspath(distribution.locate_file(entry)))
            if entry.hash.mode != "sha256" or not path.resolve().is_relative_to(ENV_ROOT.resolve()):
                raise ValueError("Unsupported installed wheel source/library record")
            digest = base64.urlsafe_b64encode(bytes.fromhex(sha256(path))).rstrip(b"=").decode("ascii")
            if digest != entry.hash.value:
                raise ValueError("Installed wheel source/library differs from its RECORD: " + str(path))
            checked += 1
    config = configparser.ConfigParser()
    config.read_string("[venv]\n" + (ENV_ROOT / "pyvenv.cfg").read_text(encoding="utf-8"))
    if config.getboolean("venv", "include-system-site-packages"):
        raise ValueError("Alignment runtime must not inherit old/system packages")
    python_version = config.get("venv", "version")
    source_files = []
    for name in ("stable_whisper", "whisper"):
        paths = sorted((site / name).rglob("*.py"))
        if not paths:
            raise ValueError("Missing actual installed alignment engine sources")
        source_files.extend({"path": str(p), "sha256": sha256(p)} for p in paths)
    environment_paths = [ENV_ROOT / "pyvenv.cfg", ENV_ROOT / "bin/python", site / "manimind_local_src.pth"]
    if (site / "manimind_local_src.pth").read_text(encoding="utf-8").strip() != str(ROOT / "src"):
        raise ValueError("Isolated runtime source path mismatch")
    for directory in sorted(site.glob("*.dist-info")):
        for name in ("METADATA", "RECORD", "WHEEL"):
            path = directory / name
            if not path.is_file():
                raise ValueError("Incomplete installed distribution identity: " + str(path))
            environment_paths.append(path)
    ffmpeg = ROOT / "manimgl_env/bin/ffmpeg"
    version = subprocess.run([str(ffmpeg), "-version"], check=True, capture_output=True, text=True, timeout=15)
    checkpoint = ENV_ROOT / "models" / f"{model}.pt"
    if sha256(checkpoint) != MODEL_SHA256[model]:
        raise ValueError("Official production Whisper checkpoint SHA256 mismatch")
    return {
        "backend": "stable_whisper", "source_url": UPSTREAM_URL, "declared_license": "MIT",
        "packages": dict(sorted(packages.items())), "python_version": python_version,
        "wheel_record_files_checked": checked,
        "executable": str(ENV_ROOT / "bin/python"), "platform": platform.platform(), "device": "cpu",
        "source_files": source_files,
        "environment_files": [{"path": str(p), "sha256": sha256(p)} for p in environment_paths],
        "ffmpeg": {"path": str(ffmpeg), "sha256": sha256(ffmpeg), "version": version.stdout.splitlines()[0]},
        "model": {"name": model, "multilingual": True, "path": str(checkpoint),
                  "sha256": MODEL_SHA256[model], "declared_license": "MIT",
                  "source_url": f"https://openaipublic.azureedge.net/main/whisper/models/{MODEL_SHA256[model]}/{model}.pt"},
        "align_options": {"language": "zh", "original_split": True, "verbose": None},
    }


def _evidence_digest(files):
    data = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def verify_alignment_evidence(value, plan_path, speech):
    """Read-only production gate; no engine import, inference, download or writes.

    Require the expected original plan/speech, not paths trusted from the result.
    Reject test injection, smoke/replay, missing evidence and any source drift.
    Return {schema_version, method, plan_sha256, attempt, files, evidence_sha256,
    units}; files includes the complete attempt and runtime/input evidence. The
    publisher must freeze it and call again before audio/caption release. This
    is local provenance consistency, not signed authentication or listening.
    """
    try:
        return _verify_alignment_evidence(value, Path(plan_path).absolute(), Path(speech).absolute())
    except ValueError:
        raise
    except (OSError, KeyError, TypeError, AttributeError, configparser.Error, subprocess.SubprocessError) as exc:
        raise ValueError("Invalid production alignment evidence: " + str(exc)) from exc


def _verify_alignment_evidence(value, plan_path, speech):
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or value.get("method") != METHOD
            or value.get("timing_scope") != TIMING_SCOPE
            or any(value.get(k) != v for k, v in PROVENANCE.items())
            or value.get("test_only") is not False or value.get("smoke_only") is not False
            or value.get("listening_reviewed") is not False
            or value.get("acceptance") != "estimated_not_listening_or_publication_approved"):
        raise ValueError("Require explicit production alignment provenance; reject test/fake/smoke/replay")
    plan = validate_plan(_read_json(plan_path))
    if "alignment_smoke_source" in plan:
        raise ValueError("Smoke generation plans cannot be production inputs")
    if (not isinstance(value.get("plan"), str) or Path(value["plan"]).resolve() != plan_path.resolve()
            or value.get("plan_sha256") != sha256(plan_path)):
        raise ValueError("Production alignment plan drift")
    sources = value.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Require nonempty production alignment sources")
    files, source_map = {}, {}

    def add(path, digest=None, *, local=False):
        path = Path(path)
        if not path.is_absolute():
            raise ValueError("Evidence paths must be absolute")
        if local and (path.is_symlink() or path.resolve() != path or not path.is_relative_to(attempt)):
            raise ValueError("Attempt evidence must remain inside its nonsymlink directory")
        if not path.is_file():
            raise ValueError("Missing production evidence file: " + str(path))
        actual = sha256(path)
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                                   or actual != digest):
            raise ValueError("Production evidence hash drift: " + str(path))
        if str(path) in files and files[str(path)] != actual:
            raise ValueError("Production evidence changed while verifying")
        files[str(path)] = actual
        return actual

    for item in sources:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"} or item["path"] in source_map:
            raise ValueError("Require unique exact path/SHA256 production source bindings")
        add(item["path"], item["sha256"])
        source_map[item["path"]] = item["sha256"]

    def require_source(path):
        path = Path(path).absolute()
        if str(path) not in source_map:
            raise ValueError("Required production source is unbound: " + str(path))
        return add(path, source_map[str(path)])

    if not isinstance(value.get("attempt"), str):
        raise ValueError("Require a production attempt directory")
    attempt = Path(value["attempt"])
    if (not attempt.is_absolute() or attempt.resolve() != attempt or not attempt.is_dir()
            or not re.fullmatch(r"\d{8}T\d{12}Z-[0-9a-f]{32}", attempt.name)):
        raise ValueError("Invalid production attempt path")
    if os.path.lexists(attempt / "failure.json"):
        raise ValueError("Failed/unknown attempts cannot enter production")

    def record(name):
        path = attempt / name
        add(path, local=True)
        return _read_json(path)

    started, completed = record("started.json"), record("completed.json")
    for item, status in ((started, "started"), (completed, "validated_candidate")):
        if (not isinstance(item, dict) or type(item.get("schema_version")) is not int or item["schema_version"] != 1
                or any(item.get(k) != v for k, v in PROVENANCE.items())
                or item.get("status") != status or item.get("test_only") is not False
                or item.get("automatic_retry") is not False or item.get("device") != "cpu"
                or item.get("model") not in MODEL_SHA256):
            raise ValueError("Invalid production started/completed receipt")
    if not isinstance(completed.get("result_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", completed["result_sha256"]):
        raise ValueError("Require a completion SHA256 for the exact result")
    if {k: v for k, v in completed.items() if k not in ("status", "result_sha256")} != {
            k: v for k, v in started.items() if k != "status"}:
        raise ValueError("Completion does not bind the exact started attempt")
    output = Path(started["output"])
    if (not output.is_absolute() or attempt.parent != output.parent / (output.name + ".attempts")
            or Path(started["plan"]).resolve() != plan_path.resolve()
            or Path(started["speech"]).resolve() != speech.resolve()):
        raise ValueError("Production attempt/output/plan/speech binding mismatch")
    add(output, completed.get("result_sha256"))
    add(attempt / "result.json", completed.get("result_sha256"), local=True)
    if _read_json(output) != value or record("result.json") != value:
        raise ValueError("Production result must match its immutable output and completed receipt")
    if record("plan.json") != plan or sha256(attempt / "plan.json") != value["plan_sha256"]:
        raise ValueError("Archived production plan differs from source")
    for path in (Path(__file__), Path(transport.__file__), Path(transport.audition.__file__),
                 ROOT / "scripts/requirements-phrase-alignment.txt"):
        digest = require_source(path)
        add(attempt / "source" / path.name, digest, local=True)

    software = record("software.json")
    if (not isinstance(software, dict) or software != value.get("software")
            or "validation_replay" in software or software.get("test_only", False) is not False):
        raise ValueError("Missing/changed production software identity or replay backend")
    identity = _production_software_identity(started["model"])
    python_version = identity.pop("python_version")
    if (any(software.get(k) != v for k, v in identity.items())
            or not isinstance(software.get("python"), str) or not software["python"].startswith(python_version + " ")
            or type(software.get("cpu_threads")) is not int or not 1 <= software["cpu_threads"] <= 4):
        raise ValueError("Require actual pinned stable_whisper software/model/runtime identity, not fake")
    for item in identity["source_files"] + identity["environment_files"] + [identity["ffmpeg"], identity["model"]]:
        if require_source(item["path"]) != item["sha256"]:
            raise ValueError("Unbound real engine/model/software evidence")
    require_source(plan_path)
    inputs = record("inputs.json")
    prefix = inputs.get("sources")
    if (any(inputs.get(k) != v for k, v in PROVENANCE.items()) or not isinstance(prefix, list) or not prefix
            or sources[:len(prefix)] != prefix):
        raise ValueError("Original input evidence source prefix/provenance differs")
    units, original_inputs = value.get("units"), inputs.get("units")
    if (not isinstance(units, list) or not isinstance(original_inputs, list)
            or len(units) != len(plan["segments"]) or len(original_inputs) != len(units)):
        raise ValueError("Every production unit requires its actual input and raw result")
    for unit, emitted, original in zip(plan["segments"], units, original_inputs, strict=True):
        identity = unit["id"]
        wav, receipt_path = speech / f"{identity}.wav", speech / f"{identity}.receipt.json"
        wav_hash, receipt_hash = require_source(wav), require_source(receipt_path)
        info, receipt = _wav_info(wav), _read_json(receipt_path)
        _validate_receipt(receipt, unit, unit, value["plan_sha256"], wav_hash, info, plan["reference_sha256"])
        expected = {"id": identity, "wav": str(wav.resolve()), "wav_sha256": wav_hash,
                    "receipt": str(receipt_path.resolve()), "receipt_sha256": receipt_hash, **info}
        if original != expected:
            raise ValueError("Original input metadata/path/hash changed: " + identity)
        add(attempt / f"{identity}.receipt.json", receipt_hash, local=True)
        request = record(f"{identity}.request.json")
        if request != {"audio": str(wav.resolve()), "text": "\n".join(r["text"] for r in unit["references"]),
                       "language": "zh", "original_split": True}:
            raise ValueError("Actual alignment request differs from original WAV/reference clauses")
        raw = record(f"{identity}.raw.json")
        if (not isinstance(raw, dict) or raw.get("language") != "zh"
                or not isinstance(raw.get("segments"), list)
                or raw.get("text") != "".join(segment["text"] for segment in raw["segments"])):
            raise ValueError("Actual production raw result language/text metadata differs")
        phrases = validate_result(raw, unit["references"], info["duration_seconds"])
        if emitted != {**expected, "phrases": phrases}:
            raise ValueError("Emitted phrase times/text/words differ from actual raw alignment")
    add(attempt / "backend.log", local=True)
    # Every file currently produced before result/completed must be source-bound.
    for path in attempt.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlinks are not production attempt evidence")
        if path.is_file():
            add(path, local=True)
            if path.name not in ("result.json", "completed.json"):
                require_source(path)
    result_files = [{"path": path, "sha256": digest} for path, digest in sorted(files.items())]
    _check_bindings(result_files)
    if os.path.lexists(attempt / "failure.json"):
        raise ValueError("Attempt failed during verification")
    return {"schema_version": 1, "method": METHOD, "plan_sha256": value["plan_sha256"],
            "attempt": str(attempt), "files": result_files,
            "evidence_sha256": _evidence_digest(result_files), "units": units}


def verify_production_timings(path, *, plan_path, speech):
    """File-oriented production wrapper, with the timing file itself hash-bound."""
    try:
        path = Path(path).absolute()
        value = _read_json(path)
        result = verify_alignment_evidence(value, plan_path, speech)
        started = _read_json(Path(result["attempt"]) / "started.json")
        if Path(started["output"]).absolute() != path:
            raise ValueError("Production timings must be the exact create-only attempt output")
        _check_bindings(result["files"])
        return result
    except ValueError:
        raise
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid production timings: " + str(exc)) from exc


class StableWhisperBackend:
    """Thin adapter around the unchanged, pinned upstream public API; CPU only."""

    def __init__(self, model="base", device="cpu"):
        if Path(sys.prefix).resolve() != ENV_ROOT.resolve() or sys.prefix == sys.base_prefix:
            raise ValueError("Run only in runtime/tools/meaning-alignment-env; do not alter old environments")
        if model not in ("base", "small") or device != "cpu":
            raise ValueError("Require multilingual base/small and CPU (no shared render GPU)")
        for name, version in PINNED_PACKAGES.items():
            if importlib.metadata.version(name) != version:
                raise ValueError("Pinned alignment package mismatch: " + name)
        ffmpeg = ROOT / "manimgl_env/bin/ffmpeg"
        os.environ["PATH"] = str(ffmpeg.parent) + os.pathsep + os.environ.get("PATH", "")
        # Keep downloaded models, tokenizer caches and numba artifacts in the new env.
        os.environ["XDG_CACHE_HOME"] = str(ENV_ROOT / "cache")
        os.environ["NUMBA_CACHE_DIR"] = str(ENV_ROOT / "cache/numba")
        os.environ["TIKTOKEN_CACHE_DIR"] = str(ENV_ROOT / "cache/tiktoken")
        import torch
        import stable_whisper

        torch.set_num_threads(min(4, os.cpu_count() or 1))
        self.model = stable_whisper.load_model(model, device=device, download_root=str(ENV_ROOT / "models"))
        self.identity = _production_software_identity(model)
        self.identity.pop("python_version")
        self.identity.update(python=sys.version, cpu_threads=torch.get_num_threads())

    def align(self, audio, text, *, language, original_split):
        result = self.model.align(str(audio), text, language=language, original_split=original_split, verbose=None)
        return None if result is None else result.to_dict()


def align_plan(plan_path, speech, output, *, model="base", device="cpu", backend_factory=None):
    """Align once per complete WAV. Inject backend_factory for download-free tests."""
    plan_path, speech = Path(plan_path).absolute(), Path(speech).absolute()
    output = Path(os.path.abspath(output))
    attempts = output.parent / (output.name + ".attempts")
    attempt = attempts / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex)
    attempt.mkdir(parents=True, exist_ok=False)
    bindings = []
    started = {"schema_version": 1, **PROVENANCE, "status": "started", "output": str(output),
               "plan": str(plan_path), "speech": str(speech), "model": model, "device": device,
               "test_only": backend_factory is not None,
               "pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat(), "automatic_retry": False}
    _write_json(attempt / "started.json", started)
    try:
        if os.path.lexists(output):
            raise FileExistsError("Create-only alignment output already exists: " + str(output))
        if model not in ("base", "small") or device != "cpu":
            raise ValueError("Require multilingual base/small and CPU")
        _bind(attempt / "started.json", bindings)
        source_dir = attempt / "source"
        source_dir.mkdir()
        for path in (Path(__file__), Path(transport.__file__), Path(transport.audition.__file__),
                     ROOT / "scripts/requirements-phrase-alignment.txt"):
            _bind(path, bindings, source_dir / path.name)
        plan_hash = _bind(plan_path, bindings, attempt / "plan.json")
        plan = validate_plan(_read_json(attempt / "plan.json"))
        inputs = _speech_inputs(plan, plan_hash, speech, attempt, bindings)
        _write_json(attempt / "inputs.json", {**PROVENANCE, "sources": bindings, "units": inputs})
        _bind(attempt / "inputs.json", bindings)
        factory = backend_factory or StableWhisperBackend
        units = []
        with (attempt / "backend.log").open("x", encoding="utf-8", buffering=1) as log, \
                redirect_stdout(log), redirect_stderr(log):
            backend = factory(model=model, device=device)
            software = backend.identity
            _write_json(attempt / "software.json", software)
            _bind(attempt / "software.json", bindings)
            # Bind actual engine sources, FFmpeg and checkpoint before any alignment.
            for item in software.get("source_files", []) + software.get("environment_files", []) + [
                    software.get("ffmpeg", {}), software.get("model", {})]:
                if "path" in item:
                    bindings.append({"path": item["path"], "sha256": item["sha256"]})
            _check_bindings(bindings)
            for unit, item in zip(plan["segments"], inputs, strict=True):
                _check_bindings(bindings)
                request = {"audio": item["wav"], "text": "\n".join(r["text"] for r in unit["references"]),
                           "language": "zh", "original_split": True}
                _write_json(attempt / f"{unit['id']}.request.json", request)
                _bind(attempt / f"{unit['id']}.request.json", bindings)
                result = backend.align(**request)
                # Preserve invalid raw timestamps too; never repair, clamp or reorder.
                raw_path = attempt / f"{unit['id']}.raw.json"
                with raw_path.open("x", encoding="utf-8") as raw:
                    json.dump(result, raw, ensure_ascii=False, indent=2)
                _bind(raw_path, bindings)
                # Upstream may emit numpy.float64; validate its unchanged JSON contract.
                phrases = validate_result(_read_json(raw_path), unit["references"], item["duration_seconds"])
                units.append({**item, "phrases": phrases})
        _bind(attempt / "backend.log", bindings)
        _check_bindings(bindings)
        value = {"schema_version": 1, "method": METHOD, "timing_scope": TIMING_SCOPE, **PROVENANCE,
                 "plan": str(plan_path), "plan_sha256": plan_hash, "units": units,
                 "test_only": backend_factory is not None,
                 "smoke_only": "alignment_smoke_source" in plan, "listening_reviewed": False, "software": software,
                 "sources": bindings, "attempt": str(attempt),
                 "acceptance": "estimated_not_listening_or_publication_approved"}
        candidate = attempt / "result.json"
        _write_json(candidate, value)
        _write_json(attempt / "completed.json", {**started, "status": "validated_candidate",
                                                "result_sha256": sha256(candidate)})
        # Hard-link publication is atomic and refuses even a racing or dangling target.
        os.link(candidate, output)
        return value
    except BaseException as exc:
        _write_json(attempt / "failure.json", {**started, "status": "failed", "sources": bindings,
                                               "error_type": type(exc).__name__, "error": str(exc),
                                               "traceback": traceback.format_exc()})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "speech", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model", choices=("base", "small"), default="base")
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    args = parser.parse_args(argv)
    try:
        result = align_plan(args.plan, args.speech, args.output, model=args.model, device=args.device)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                          "attempts": str(args.output.absolute()) + ".attempts"}), file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "units": len(result["units"]),
                      "timing_scope": result["timing_scope"], "smoke_only": result["smoke_only"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
