"""Offline fixtures only: no SDK, CUDA, remote host or speech synthesis is used."""

from contextlib import contextmanager, nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import wave
import xml.etree.ElementTree as ET

import pytest

from manimind.postproduce import flexible_voxcpm as worker
from manimind.postproduce import voxcpm_audition as audition


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def segments(count):
    return [{"id": "N01" if i == 0 else f"focus-{i}_take", "cue": "shared-cue", "focus": f"event-{i}",
             "text": f"  Unchanged fixture sentence {i}.\nKeep spaces.  ", "extra": {"preserve": i}}
            for i in range(count)]


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text(json.dumps({"architecture": "voxcpm2", "audio_vae_config": {"out_sample_rate": 48000}}))
    (model / "weights.bin").write_bytes(b"test fixture, not real weights")
    setup = {"schema_version": 1, "model_id": audition.MODEL, "revision": audition.REVISION,
             "model_path": str(model), "declared_license": "apache-2.0",
             "files": [{"file": p.name, "sha256": audition.sha(p)} for p in sorted(model.iterdir())]}
    setup_path = tmp_path / "setup.json"
    audition.write_json(setup_path, setup)
    monkeypatch.setattr(worker, "MODEL_FILES_SHA256", worker.model_files_sha256(setup))
    reference = tmp_path / "V01.wav"
    with wave.open(str(reference), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(b"\x00\x10\x00\xf0" * 240)
    monkeypatch.setattr(worker, "REFERENCE_SHA256", audition.sha(reference))
    plan = {"schema_version": 2, "reference_sha256": worker.REFERENCE_SHA256,
            "reference_text": audition.TEXT, "reference_source": "outputs/synthetic-fixture/V01.wav",
            "synthetic_reference": True, "generation": dict(worker.GENERATION), "segments": segments(3),
            "source": {"visual": "pending-focus-scheduler", "extra": {"keep": True}},
            "writer": "Main", "consumers": ["audio worker"], "lifecycle": "This plan version",
            "invalidation": "Text/source changes", "extra": {"keep": [1, 2, 3]}}
    plan_path = tmp_path / "plan.json"
    audition.write_json(plan_path, plan)
    return SimpleNamespace(model=model, setup=setup, setup_path=setup_path, plan=plan, plan_path=plan_path,
                           reference=reference, output=tmp_path / "first-attempt")


def save_plan(inputs):
    inputs.plan_path.unlink()
    audition.write_json(inputs.plan_path, inputs.plan)


def run(inputs):
    return worker.generate(inputs.model, inputs.output, inputs.setup_path, inputs.plan_path, inputs.reference)


@pytest.fixture
def engine(monkeypatch):
    calls = {"load": [], "generate": [], "rng": [], "lock": [], "held": False, "resets": 0}

    @contextmanager
    def slot():
        calls["lock"].append("acquire")
        if "slot_error" in calls:
            raise calls["slot_error"]
        if calls.get("busy"):
            raise RuntimeError("fixture GPU slot busy")
        calls["held"] = True
        try:
            yield {"mutex": worker.GPU_MUTEX, "evidence": "simulation_only_not_GPU_validation"}
        finally:
            calls["held"] = False
            calls["lock"].append("release")

    def generate(*, text, reference_wav_path, prompt_wav_path, prompt_text, cfg_value,
                 inference_timesteps, normalize, denoise, retry_badcase):
        assert calls["held"]
        assert calls["rng"][-4:] == [(name, 42) for name in ("random", "numpy", "torch", "cuda")]
        kwargs = dict(text=text, reference_wav_path=reference_wav_path, prompt_wav_path=prompt_wav_path,
                      prompt_text=prompt_text, cfg_value=cfg_value, inference_timesteps=inference_timesteps,
                      normalize=normalize, denoise=denoise, retry_badcase=retry_badcase)
        calls["generate"].append(kwargs)
        if calls.get("fail_on") == len(calls["generate"]):
            raise RuntimeError("fixture interrupted inference")
        print("private simulated SDK diagnostic")
        return calls.get("samples", [0, .25, -.5, .125] * 120)

    def load(path, **kwargs):
        assert calls["held"]
        assert all(worker.os.environ[key] == "1" for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"))
        calls["load"].append((path, kwargs))
        if calls.get("load_error"):
            raise RuntimeError("fixture load failed")
        return SimpleNamespace(tts_model=SimpleNamespace(sample_rate=calls.get("rate", 48000)), generate=generate)

    def reset():
        calls["resets"] += 1

    def seed_for(name):
        return lambda seed: calls["rng"].append((name, seed))

    cuda = SimpleNamespace(is_available=lambda: calls.get("cuda", True), synchronize=lambda: None,
                           reset_peak_memory_stats=reset, get_device_name=lambda: "SIMULATED GPU",
                           max_memory_allocated=lambda: 2 * 1024**2, max_memory_reserved=lambda: 3 * 1024**2,
                           manual_seed_all=seed_for("cuda"))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda, version=SimpleNamespace(cuda="fixture"),
                        inference_mode=nullcontext, manual_seed=seed_for("torch")))
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(random=SimpleNamespace(seed=seed_for("numpy"))))
    monkeypatch.setitem(sys.modules, "voxcpm", SimpleNamespace(VoxCPM=SimpleNamespace(from_pretrained=load)))
    monkeypatch.setattr(worker.random, "seed", seed_for("random"))
    monkeypatch.setattr(worker, "gpu_slot", slot)
    monkeypatch.setattr(worker.importlib.metadata, "version", lambda name: calls.get("sdk", "2.0.3") if name == "voxcpm" else "fixture")
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_IMPLICIT_TOKEN", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.setenv(name, "0")
    return calls


def test_frozen_identity_and_generation_contract():
    assert worker.HELPER_SHA256 == audition.sha(audition.__file__)
    assert worker.REFERENCE_SHA256 == "b36f1c933b6d452df52e85571bd8de995f8513c2033e8c3d1d923a7cb79c0be9"
    assert worker.MODEL_FILES_SHA256 == "5c755cf99025acbc653d245c017782f4b0484ca53a9fba71037d74378030d9f5"
    assert worker.GENERATION == {"seed": 42, "cfg_value": 2.0, "inference_timesteps": 10,
                                 "normalize": False, "denoise": False, "retry_badcase": False}


def test_optional_identity_matches_existing_local_artifacts():
    root = Path(__file__).resolve().parents[1]
    reference = root / "outputs/voxcpm2-no-reference-20261025/V01.wav"
    setup_path = root / "runtime/sessions/voxcpm2-audition-20261025/setup/voxcpm2-setup-receipt.json"
    if not reference.is_file() or not setup_path.is_file():
        pytest.skip("Local audition artifacts are not part of a source checkout")
    assert worker.REFERENCE_SHA256 == audition.sha(reference)
    setup = read(setup_path)
    assert worker.MODEL_FILES_SHA256 == worker.model_files_sha256(setup)
    assert worker.GENERATION == {"seed": 42, "cfg_value": 2.0, "inference_timesteps": 10,
                                 "normalize": False, "denoise": False, "retry_badcase": False}


def test_two_file_standalone_import_and_help_do_not_import_sdk_or_project(tmp_path):
    for module in (worker, audition):
        shutil.copyfile(module.__file__, tmp_path / Path(module.__file__).name)
    check = """
import builtins, sys
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'numpy', 'voxcpm', 'manimind', 'soundfile'}:
        raise AssertionError('unexpected heavy/project import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import flexible_voxcpm
flexible_voxcpm.main(['generate', '--help'])
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", check, str(tmp_path)],
                            capture_output=True, text=True, check=True)
    assert all(flag in result.stdout for flag in ("--plan", "--model", "--setup-receipt", "--reference", "--output", "--gpu-baseline"))


@pytest.mark.parametrize("count", [1, 3, 29])
def test_variable_counts_first_takes_are_bound_without_timing_or_text_edits(inputs, engine, capsys, count):
    inputs.plan["segments"] = segments(count)
    save_plan(inputs)
    state = run(inputs)
    ids = [row["id"] for row in inputs.plan["segments"]]
    assert state["attempted"] == state["done"] == ids
    assert state["call_count"] == count and state["model_load_count"] == 1
    assert state["status"] == worker.ACCEPTANCE and read(inputs.output / "state.json") == state
    assert engine["load"] == [(str(inputs.model), audition.LOAD_OPTIONS)]
    assert engine["resets"] == count + 1
    assert engine["rng"] == [(name, 42) for _ in ids for name in ("random", "numpy", "torch", "cuda")]
    assert engine["lock"] == ["acquire", "release"] and not engine["held"]
    assert read(inputs.output / "plan.json") == inputs.plan
    for name, original in (("plan.json", inputs.plan_path), ("setup-receipt.json", inputs.setup_path), ("reference.wav", inputs.reference)):
        assert (inputs.output / name).read_bytes() == original.read_bytes()
    for module in (worker, audition):
        assert (inputs.output / "source" / Path(module.__file__).name).read_bytes() == Path(module.__file__).read_bytes()
    requests = read(inputs.output / "requests.json")["segments"]
    for i, segment in enumerate(inputs.plan["segments"]):
        identity = segment["id"]
        kwargs = worker.generate_kwargs(segment, inputs.output / "reference.wav", audition.TEXT)
        assert requests[i]["request"] == engine["generate"][i] == kwargs
        record = read(inputs.output / f"{identity}.receipt.json")
        assert record["segment"] == segment and record["generate_kwargs"] == kwargs and "seed" not in kwargs
        assert record["seed"] == 42 and record["seed_method"] == audition.SEED_METHOD
        assert record["first_take"] is True and record["segment_call_count"] == record["model_load_count"] == 1
        assert record["call_count"] == i + 1 and record["acceptance"] == worker.ACCEPTANCE
        assert record["wav_sha256"] == audition.sha(inputs.output / f"{identity}.wav")
        assert record["float32_sha256"] == audition.sha(inputs.output / record["float32_file"])
        assert record["plan_sha256"] == audition.sha(inputs.plan_path)
        assert record["reference_sha256"] == audition.sha(inputs.reference)
        assert record["helper_sha256"] == worker.HELPER_SHA256
        assert record["worker_sha256"] == audition.sha(worker.__file__)
        assert record["setup_sha256"] == audition.sha(inputs.setup_path)
        assert record["generation_seconds"] >= 0
        assert record["peak_torch_allocated_mib"] == 2 and record["peak_torch_reserved_mib"] == 3
        assert record["frames"] == 480 and record["duration_seconds"] == .01
        assert record["reference_source"] == inputs.plan["reference_source"] and record["synthetic_reference"] is True
        assert record["engine"]["model_files_sha256"] == worker.MODEL_FILES_SHA256
        assert record["engine"]["model_load_seconds"] >= 0
        assert all(record[key] for key in ("writer", "consumers", "lifecycle", "invalidation"))
        with wave.open(str(inputs.output / f"{identity}.wav"), "rb") as audio:
            assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth(), audio.getnframes()) == (48000, 1, 2, 480)
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [event["event"] for event in events] == ["loading"] + [e for _ in ids for e in ("segment_started", "segment_done")] + ["completed"]
    assert "private simulated SDK diagnostic" in (inputs.output / "generation.log").read_text()
    assert not (inputs.output / "state.json.tmp").exists()


@pytest.mark.parametrize("bad_id", ["N01", "n01", "../escape", "foo/bar", "foo\\bar", "CON", "nul", "COM1", "a:b", "a.", "a ", "", "-a", "a" * 102, None])
def test_duplicate_or_unsafe_ids_are_rejected(inputs, bad_id):
    inputs.plan["segments"][1]["id"] = bad_id
    with pytest.raises(ValueError, match="IDs"):
        worker.validate_plan(inputs.plan)


@pytest.mark.parametrize("field", ["text", "cue", "focus"])
@pytest.mark.parametrize("value", ["", " \n\t", None, 12])
def test_empty_segment_fields_are_rejected(inputs, field, value):
    inputs.plan["segments"][0][field] = value
    with pytest.raises(ValueError, match="nonempty"):
        worker.validate_plan(inputs.plan)


@pytest.mark.parametrize("change", [{"schema_version": 1}, {"schema_version": True}, {"segments": []},
    {"segments": None}, {"segments": [None]}, {"reference_sha256": "a" * 64}, {"reference_text": "changed"},
    {"synthetic_reference": False}, {"synthetic_reference": "true"}, {"reference_source": ""}, {"reference_source": {}}])
def test_invalid_plans_fail_before_any_gpu_work_and_retain_evidence(inputs, engine, change):
    inputs.plan.update(change)
    save_plan(inputs)
    with pytest.raises(ValueError):
        run(inputs)
    assert not engine["load"] and not engine["generate"] and not engine["lock"]
    assert read(inputs.output / "state.json")["status"] == "failed"
    failure = read(inputs.output / "failure.json")
    assert failure["automatic_retry"] is False and failure["state"]["model_load_count"] == 0
    assert all(failure[key] for key in ("writer", "consumers", "lifecycle", "invalidation"))
    assert (inputs.output / "plan.json").read_bytes() == inputs.plan_path.read_bytes()


@pytest.mark.parametrize("key,value", [("seed", 43), ("seed", 42.0), ("cfg_value", 2.1),
    ("inference_timesteps", 11), ("normalize", True), ("denoise", True), ("retry_badcase", True),
    ("normalize", 0), ("speed", 1.0)])
def test_generation_changes_cannot_reach_sdk(inputs, engine, key, value):
    inputs.plan["generation"][key] = value
    save_plan(inputs)
    with pytest.raises(ValueError, match="fixed generation"):
        run(inputs)
    assert not engine["load"] and not engine["generate"]


@pytest.mark.parametrize("change", ["reference", "reference_and_plan_hash", "weights", "self_consistent_weights", "helper", "sdk"])
def test_changed_inputs_or_software_refused_before_load(inputs, engine, monkeypatch, change):
    if change.startswith("reference"):
        with inputs.reference.open("ab") as stream:
            stream.write(b"changed")
        if change == "reference_and_plan_hash":
            inputs.plan["reference_sha256"] = audition.sha(inputs.reference)
            save_plan(inputs)
    elif change in ("weights", "self_consistent_weights"):
        (inputs.model / "weights.bin").write_bytes(b"changed weights")
        if change == "self_consistent_weights":
            next(item for item in inputs.setup["files"] if item["file"] == "weights.bin")["sha256"] = audition.sha(inputs.model / "weights.bin")
            inputs.setup_path.unlink()
            audition.write_json(inputs.setup_path, inputs.setup)
    elif change == "helper":
        monkeypatch.setattr(worker, "HELPER_SHA256", "0" * 64)
    else:
        engine["sdk"] = "2.0.4"
    with pytest.raises(ValueError):
        run(inputs)
    assert not engine["load"] and not engine["generate"]
    assert read(inputs.output / "state.json")["model_load_count"] == 0


@pytest.mark.parametrize("kind", ["cuda", "load_error", "rate", "busy"])
def test_no_fallback_or_retry_on_preflight_or_loading_failure(inputs, engine, kind):
    engine[kind] = {"cuda": False, "load_error": True, "rate": 24000, "busy": True}[kind]
    with pytest.raises((ValueError, RuntimeError)):
        run(inputs)
    assert not engine["generate"] and len(engine["load"]) <= 1 and not engine["held"]
    assert read(inputs.output / "failure.json")["state"]["attempted"] == []


def test_failed_second_take_keeps_first_and_never_replays_unknown_attempt(inputs, engine):
    engine["fail_on"] = 2
    with pytest.raises(RuntimeError, match="interrupted"):
        run(inputs)
    ids = [row["id"] for row in inputs.plan["segments"]]
    state = read(inputs.output / "state.json")
    assert state["attempted"] == ids[:2] and state["done"] == ids[:1]
    assert state["call_count"] == 2 and state["model_load_count"] == 1
    assert read(inputs.output / f"{ids[0]}.receipt.json")["wav_sha256"] == audition.sha(inputs.output / f"{ids[0]}.wav")
    assert not (inputs.output / f"{ids[2]}.wav").exists()
    with pytest.raises(FileExistsError):
        run(inputs)
    assert len(engine["load"]) == 1 and len(engine["generate"]) == 2 and not engine["held"]


def test_reader_rename_lock_after_inference_does_not_repeat_the_take(inputs, engine, monkeypatch):
    replace = worker.os.replace
    blocked = []
    sleeps = []

    def locked_once(source, target):
        value = read(Path(source))
        if value.get("done") and not blocked:
            blocked.append(str(source))
            error = PermissionError("simulated Windows reader sharing lock")
            error.winerror = 5
            raise error
        return replace(source, target)

    monkeypatch.setattr(worker.os, "replace", locked_once)
    monkeypatch.setattr(worker.time, "sleep", sleeps.append)
    result = run(inputs)
    assert result["status"] == worker.ACCEPTANCE
    assert len(engine["generate"]) == result["call_count"] == len(inputs.plan["segments"])
    assert sleeps == [.025] and len(blocked) == 1
    assert not list(inputs.output.glob("state-*.json.tmp"))


@pytest.mark.parametrize("winerror,expected_calls", [(5, 8), (32, 8), (None, 1)])
def test_state_replace_failure_is_bounded_and_keeps_unique_staging_files(tmp_path, monkeypatch, winerror, expected_calls):
    calls = []

    def locked(source, target):
        calls.append(str(source))
        error = PermissionError("fixture persistent lock or real permissions failure")
        if winerror is not None:
            error.winerror = winerror
        raise error

    monkeypatch.setattr(worker.os, "replace", locked)
    monkeypatch.setattr(worker.time, "sleep", lambda _: None)
    for phase in ("generating", "failed"):
        with pytest.raises(PermissionError):
            worker._write_state(tmp_path, {"status": phase})
    assert len(calls) == 2 * expected_calls
    retained = list(tmp_path.glob("state-*.json.tmp"))
    assert len(retained) == 2
    assert {read(path)["status"] for path in retained} == {"generating", "failed"}
    assert not (tmp_path / "state.json").exists()


@pytest.mark.parametrize("timeout", [False, True])
def test_failed_preflight_keeps_subprocess_diagnostics(inputs, engine, timeout):
    error = (subprocess.TimeoutExpired(["fixture-inspector"], 30, output=b"partial output", stderr=b"fixture timeout")
             if timeout else subprocess.CalledProcessError(1, ["fixture-inspector"], output="diagnostic", stderr="fixture service busy"))
    engine["slot_error"] = error
    with pytest.raises(subprocess.SubprocessError):
        run(inputs)
    failure = read(inputs.output / "failure.json")
    assert failure["subprocess_diagnostics"]["command"] == ["fixture-inspector"]
    assert "fixture" in failure["subprocess_diagnostics"]["stderr"]
    assert failure["state"]["call_count"] == failure["state"]["model_load_count"] == 0
    assert not engine["load"] and not engine["generate"]


@pytest.mark.parametrize("samples", [[], [float("nan")], [1.1], [0.0, 0.0], [0.999999]])
def test_bad_pcm_is_not_edited_retried_or_discarded(inputs, engine, samples):
    engine["samples"] = samples
    with pytest.raises(ValueError):
        run(inputs)
    assert len(engine["generate"]) == 1 and len(engine["load"]) == 1
    assert (inputs.output / "N01.float32").exists() and not (inputs.output / "N01.wav").exists()
    assert read(inputs.output / "state.json")["done"] == [] and not engine["held"]


@pytest.mark.parametrize("populated", [False, True])
def test_even_empty_existing_directories_are_untouched(inputs, engine, populated):
    inputs.output.mkdir()
    if populated:
        (inputs.output / "state.json").write_bytes(b"unknown still-running process")
    before = {p.name: p.read_bytes() for p in inputs.output.iterdir()}
    with pytest.raises(FileExistsError):
        run(inputs)
    assert {p.name: p.read_bytes() for p in inputs.output.iterdir()} == before
    assert not engine["load"] and not engine["lock"]


def test_output_cannot_pollute_model_or_enclose_inputs(inputs, engine):
    for output in (inputs.model / "new-parent" / "attempt", inputs.model.parent):
        inputs.output = output
        with pytest.raises(ValueError, match="separate"):
            run(inputs)
    assert not (inputs.model / "new-parent").exists() and not engine["load"]


@pytest.fixture
def mutex_api(monkeypatch):
    calls = []
    api = SimpleNamespace(result=0, handle=123)
    api.CreateMutexW = lambda *args: calls.append(("create", args)) or api.handle
    api.WaitForSingleObject = lambda *args: calls.append(("wait", args)) or api.result
    api.ReleaseMutex = lambda handle: calls.append(("release", handle)) or True
    api.CloseHandle = lambda handle: calls.append(("close", handle)) or True
    monkeypatch.setattr(worker.sys, "platform", "win32")
    monkeypatch.setattr(worker, "_kernel32", lambda: api)
    monkeypatch.setattr(worker, "_gpu_preflight", lambda: calls.append(("preflight",)) or {"fixture": True})
    return api, calls


def test_native_mutex_binding_declares_pointer_sized_win32_signatures(monkeypatch):
    import ctypes
    from ctypes import wintypes

    api = SimpleNamespace(**{name: SimpleNamespace() for name in ("CreateMutexW", "WaitForSingleObject", "ReleaseMutex", "CloseHandle")})
    opened = []
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: opened.append((args, kwargs)) or api, raising=False)
    assert worker._kernel32() is api
    assert opened == [(("kernel32",), {"use_last_error": True})]
    assert api.CreateMutexW.argtypes == (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    assert api.CreateMutexW.restype is wintypes.HANDLE
    assert api.WaitForSingleObject.argtypes == (wintypes.HANDLE, wintypes.DWORD)
    assert api.ReleaseMutex.argtypes == api.CloseHandle.argtypes == (wintypes.HANDLE,)


def test_shared_mutex_is_nonblocking_and_released_on_error(mutex_api):
    _, calls = mutex_api
    with pytest.raises(RuntimeError, match="test body"):
        with worker.gpu_slot() as evidence:
            assert evidence == {"fixture": True}
            raise RuntimeError("test body")
    assert calls == [("create", (None, False, worker.GPU_MUTEX)), ("wait", (123, 0)),
                     ("preflight",), ("release", 123), ("close", 123)]


def test_preflight_error_releases_acquired_mutex(mutex_api, monkeypatch):
    _, calls = mutex_api

    def fail():
        raise RuntimeError("fixture unknown process")

    monkeypatch.setattr(worker, "_gpu_preflight", fail)
    with pytest.raises(RuntimeError, match="unknown process"):
        with worker.gpu_slot():
            pytest.fail("must not reach model loading")
    assert calls[-2:] == [("release", 123), ("close", 123)]


@pytest.mark.parametrize("result", [0x80, 0x102, 0xFFFFFFFF])
def test_busy_abandoned_or_uninspectable_mutex_never_reaches_preflight(mutex_api, result):
    api, calls = mutex_api
    api.result = result
    with pytest.raises(RuntimeError):
        with worker.gpu_slot():
            pytest.fail("must not acquire GPU")
    assert ("preflight",) not in calls and ("close", 123) in calls
    assert (("release", 123) in calls) == (result == 0x80)


def test_mutex_creation_failure_is_not_silently_ignored(mutex_api):
    api, calls = mutex_api
    api.handle = 0
    with pytest.raises(OSError):
        with worker.gpu_slot():
            pytest.fail("must not acquire GPU")
    assert len(calls) == 1


def test_nonwindows_has_no_implicit_cpu_or_lock_fallback(monkeypatch):
    monkeypatch.setattr(worker.sys, "platform", "darwin")
    with pytest.raises(RuntimeError, match="Windows CUDA"):
        with worker.gpu_slot():
            pytest.fail("must not acquire GPU")


@pytest.mark.parametrize("kind", ["clear", "gpu_pid", "unknown_gpu", "service_failure", "inspection_timeout"])
def test_readonly_gpu_preflight_fails_closed_without_service_changes(monkeypatch, kind):
    commands = []

    def invoke(args, **kwargs):
        commands.append(args)
        assert kwargs == {"check": True, "capture_output": True, "text": True, "timeout": 30}
        if kind == "service_failure":
            raise subprocess.CalledProcessError(1, args, stderr="service running or inspection denied")
        if kind == "inspection_timeout":
            raise subprocess.TimeoutExpired(args, 30)
        return SimpleNamespace(stdout={"gpu_pid": "1234\n", "unknown_gpu": "[Not Supported]\n"}.get(kind, ""))

    monkeypatch.setattr(worker.subprocess, "run", invoke)
    if kind == "clear":
        assert worker._gpu_preflight()["mutex"] == worker.GPU_MUTEX
    else:
        with pytest.raises((RuntimeError, subprocess.SubprocessError)):
            worker._gpu_preflight()
    command = commands[0][-1]
    assert "Get-ScheduledTask" in command and "Get-NetTCPConnection -ErrorAction Stop" in command
    assert "Start-ScheduledTask" not in command and "Stop-" not in command
    assert len(commands) == (1 if kind in ("service_failure", "inspection_timeout") else 2)


def test_cli_arguments(inputs, monkeypatch, capsys):
    calls = []

    def generate(*args):
        calls.append(args)
        return {"status": "fixture", "done": ["N01"]}

    monkeypatch.setattr(worker, "generate", generate)
    worker.main(["generate", "--plan", str(inputs.plan_path), "--model", str(inputs.model),
                 "--setup-receipt", str(inputs.setup_path), "--reference", str(inputs.reference), "--output", str(inputs.output)])
    assert calls == [(inputs.model, inputs.output, inputs.setup_path, inputs.plan_path, inputs.reference)]
    assert json.loads(capsys.readouterr().out)["done"] == ["N01"]


@pytest.fixture
def gpu_inventory():
    return {"gpu_uuid": "GPU-01234567-89ab-cdef-0123-456789abcdef", "driver_version": "610.47",
            "processes": [
                {"pid": 100, "type": "C+G", "process_name": r"C:\Windows\System32\dwm.exe"},
                {"pid": 101, "type": "C+G", "process_name": r"C:\Windows\explorer.exe"},
                {"pid": 102, "type": "C+G", "process_name": r"F:\Steam\steam.exe"},
                {"pid": 103, "type": "C", "process_name": r"C:\Program Files\Lian-Li\LConnect-Service.exe"},
            ]}


@pytest.fixture
def gpu_baseline(gpu_inventory):
    now = datetime.now(timezone.utc)
    return {"schema_version": 1, "purpose": "approved_shared_desktop_occupants", "approved": True,
            "exclusive_gpu": False, "operator": "offline fixture operator, not a real host approval",
            "approved_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(minutes=19)).isoformat(),
            **deepcopy(gpu_inventory),
            "processes": [{**item, "approved_shared_desktop_occupant": True,
                           "reason": "Fixture operator inspected PID/path and confirmed a shared desktop application"}
                          for item in gpu_inventory["processes"]]}


def inventory_xml(inventory):
    root = ET.Element("nvidia_smi_log")
    ET.SubElement(root, "driver_version").text = inventory["driver_version"]
    ET.SubElement(root, "attached_gpus").text = "1"
    gpu = ET.SubElement(root, "gpu", id="00000000:01:00.0")
    ET.SubElement(gpu, "uuid").text = inventory["gpu_uuid"]
    processes = ET.SubElement(gpu, "processes")
    for row in inventory["processes"]:
        item = ET.SubElement(processes, "process_info")
        for key, value in row.items():
            ET.SubElement(item, key).text = str(value)
        ET.SubElement(item, "used_memory").text = "N/A"
    return ET.tostring(root, encoding="unicode")


def mock_gpu_commands(monkeypatch, xml, error=None):
    commands = []

    def invoke(args, **kwargs):
        commands.append(args)
        assert kwargs == {"check": True, "capture_output": True, "text": True, "timeout": 30}
        if error is not None:
            raise error(args)
        return SimpleNamespace(stdout=xml if args[0] == "nvidia-smi" else "")

    monkeypatch.setattr(worker.subprocess, "run", invoke)
    return commands


def test_xml_na_memory_is_supported_without_being_treated_as_idle(gpu_inventory, gpu_baseline):
    current = worker.parse_gpu_xml(inventory_xml(gpu_inventory))
    assert current == gpu_inventory
    assert worker.validate_gpu_baseline(gpu_baseline, current) is gpu_baseline
    # Previously approved occupants may exit; their replacements/new PIDs may not enter.
    current["processes"].pop()
    worker.validate_gpu_baseline(gpu_baseline, current)


@pytest.mark.parametrize("name", ["ShellHost.exe", "CrossDeviceResume.exe", "TextInputHost.exe", "StartMenuExperienceHost.exe",
    "SearchHost.exe", "NVIDIA Overlay.exe", "GCC.exe", "ArmouryCrate.exe", "msedgewebview2.exe", "ChatGPT.exe",
    "RadeonSoftware.exe", "AMDRSSrcExt.exe", "CefSharp.BrowserSubprocess.exe", "localsend_app.exe", "douyin.exe"])
def test_operator_approved_desktop_apps_need_no_source_allowlist(gpu_inventory, gpu_baseline, name):
    path = "C:\\Program Files\\Fixture desktop application\\" + name
    gpu_inventory["processes"][0]["process_name"] = path
    gpu_baseline["processes"][0]["process_name"] = path
    assert worker.validate_gpu_baseline(gpu_baseline, worker.parse_gpu_xml(inventory_xml(gpu_inventory))) is gpu_baseline


@pytest.mark.parametrize("reason", [None, "", " \r\n\t", 42, {}, False])
def test_operator_reason_is_mandatory_for_every_occupant(gpu_inventory, gpu_baseline, reason):
    gpu_baseline["processes"][0]["reason"] = reason
    with pytest.raises(ValueError, match="nonempty operator reason"):
        worker.validate_gpu_baseline(gpu_baseline, gpu_inventory)


def test_explicit_baseline_keeps_content_hash_inventory_and_nonexclusive_limits(tmp_path, monkeypatch, gpu_inventory, gpu_baseline):
    path = tmp_path / "baseline.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(gpu_baseline, indent=2).encode())
    xml = '<?xml version="1.0"?>\n<!DOCTYPE nvidia_smi_log SYSTEM "nvsmi_device_v12.dtd">\n' + inventory_xml(gpu_inventory)
    commands = mock_gpu_commands(monkeypatch, xml)
    evidence = worker._gpu_preflight(path)
    assert commands[1] == ["nvidia-smi", "-q", "-x"]
    assert "Stop-" not in commands[0][-1] and "Start-" not in commands[0][-1]
    assert evidence["qwen_task_and_port"] == "inactive" and evidence["mutex"] == worker.GPU_MUTEX
    assert evidence["baseline"] == gpu_baseline and evidence["baseline_sha256"] == audition.sha(path)
    assert evidence["nvidia_smi_xml"] == xml
    assert evidence["xml_sha256"] == hashlib.sha256(xml.encode()).hexdigest()
    assert evidence["exclusive_gpu"] is False and "does not prove exclusive GPU" in evidence["limitations"][0]
    assert all(evidence[key] for key in ("baseline_writer", "consumers", "lifecycle", "invalidation", "checked_at"))


@pytest.mark.parametrize("change", ["new_desktop", "qwen_9920", "pid", "type", "path", "path_case", "gpu_uuid", "driver_version"])
def test_baseline_rejects_new_processes_and_exact_identity_changes(gpu_inventory, gpu_baseline, change):
    if change == "new_desktop":
        gpu_inventory["processes"].append({"pid": 999, "type": "C+G", "process_name": r"F:\Steam\steam.exe"})
    elif change == "qwen_9920":
        gpu_inventory["processes"].append({"pid": 9920, "type": "C", "process_name": r"F:\Qwen\.venv\Scripts\python.exe"})
    elif change in ("pid", "type", "path", "path_case"):
        key, value = {"pid": ("pid", 999), "type": ("type", "C"),
                      "path": ("process_name", r"D:\Windows\System32\dwm.exe"),
                      "path_case": ("process_name", r"C:\Windows\System32\DWM.EXE")}[change]
        gpu_inventory["processes"][0][key] = value
    else:
        gpu_inventory[change] = "GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" if change == "gpu_uuid" else "611.00"
    with pytest.raises(ValueError, match="cover|identity changed"):
        worker.validate_gpu_baseline(gpu_baseline, gpu_inventory)


@pytest.mark.parametrize("change", ["expired", "expiry_boundary", "future", "long_ttl", "reversed", "naive", "bad_time"])
def test_baseline_time_window_is_strict_and_at_most_twenty_minutes(gpu_inventory, gpu_baseline, change):
    now = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
    start, end = now - timedelta(minutes=1), now + timedelta(minutes=19)
    if change == "expired":
        start, end = now - timedelta(minutes=21), now - timedelta(minutes=1)
    elif change == "expiry_boundary":
        start, end = now - timedelta(minutes=20), now
    elif change == "future":
        start, end = now + timedelta(seconds=1), now + timedelta(minutes=20)
    elif change == "long_ttl":
        end += timedelta(microseconds=1)
    elif change == "reversed":
        end = start
    elif change == "naive":
        start = start.replace(tzinfo=None)
    gpu_baseline.update(approved_at=start.isoformat(), expires_at=end.isoformat())
    if change == "bad_time":
        gpu_baseline["approved_at"] = 42
    with pytest.raises(ValueError, match="baseline"):
        worker.validate_gpu_baseline(gpu_baseline, gpu_inventory, now=now)


@pytest.mark.parametrize("change", [{"approved": False}, {"approved": "true"}, {"schema_version": True},
    {"exclusive_gpu": True}, {"purpose": "empty_gpu"}, {"operator": " "}, {"processes": None}])
def test_missing_explicit_operator_approval_cannot_authorize_gpu(gpu_inventory, gpu_baseline, change):
    gpu_baseline.update(change)
    with pytest.raises(ValueError, match="baseline"):
        worker.validate_gpu_baseline(gpu_baseline, gpu_inventory)


@pytest.mark.parametrize("name", [r"F:\env\python.exe", r"F:\env\PYTHONW.EXE", r"F:\env\python3.12.exe",
    r"F:\env\pypy.exe", r"F:\env\node.exe", r"F:\env\java.exe", r"F:\env\dotnet.exe", r"F:\env\pwsh.exe",
    r"F:\env\unknown-model-worker.exe", r"F:\env\ollama.exe", r"F:\Python311\steam.exe",
    r"F:\env\.venv\dwm.exe", r"F:\models\renamed.exe", r"F:\LM Studio\lms.exe",
    r"F:\env\py.exe", r"F:\env\worker.exe", r"F:\CosyVoice\desktop-name.exe"])
def test_interpreters_unknown_workers_and_interpreter_path_masquerades_cannot_be_approved(gpu_inventory, gpu_baseline, name):
    gpu_baseline["processes"][0]["process_name"] = name
    gpu_inventory["processes"][0]["process_name"] = name
    with pytest.raises(ValueError, match="interpreter or unknown model worker"):
        worker.validate_gpu_baseline(gpu_baseline, gpu_inventory)


@pytest.mark.parametrize("change", [{"pid": None}, {"pid": True}, {"pid": "100"}, {"type": "N/A"},
    {"process_name": "python.exe"}, {"process_name": r"C:\Windows\System32\..\dwm.exe"},
    {"process_name": "C:\\Windows\\dwm.exe "}, {"process_name": "N/A"},
    {"process_name": r"C:\...\steam.exe"}, {"process_name": r"\\?\C:\Windows\dwm.exe"},
    {"process_name": r"C:\Windows\\System32\dwm.exe"}, {"approved_shared_desktop_occupant": False}])
def test_bad_baseline_process_fields_and_unapproved_entries_fail(gpu_inventory, gpu_baseline, change):
    gpu_baseline["processes"][0].update(change)
    with pytest.raises(ValueError):
        worker.validate_gpu_baseline(gpu_baseline, gpu_inventory)


@pytest.mark.parametrize("field", ["pid", "type", "process_name", "approved_shared_desktop_occupant", "reason"])
def test_baseline_missing_identity_or_approval_is_not_inferred(gpu_inventory, gpu_baseline, field):
    del gpu_baseline["processes"][0][field]
    with pytest.raises(ValueError):
        worker.validate_gpu_baseline(gpu_baseline, gpu_inventory)


@pytest.mark.parametrize("kind", ["parse", "unsupported", "no_processes", "missing_pid", "missing_name", "missing_type",
    "na_name", "unsupported_type", "duplicate_pid", "duplicate_field", "multi_gpu", "missing_uuid", "bad_driver", "whitespace_name"])
def test_gpu_xml_malformed_or_uninspectable_inventory_is_never_empty(gpu_inventory, kind):
    root = ET.fromstring(inventory_xml(gpu_inventory))
    gpu = root.find("gpu")
    processes = gpu.find("processes")
    item = processes[0]
    if kind == "parse":
        payload = "<nvidia_smi_log>broken"
    else:
        if kind == "unsupported":
            processes.clear()
            processes.text = "[Not Supported]"
        elif kind == "no_processes":
            gpu.remove(processes)
        elif kind.startswith("missing_"):
            field = kind.removeprefix("missing_")
            field = {"name": "process_name", "uuid": "uuid"}.get(field, field)
            parent = gpu if field == "uuid" else item
            parent.remove(parent.find(field))
        elif kind == "na_name":
            item.find("process_name").text = "N/A"
        elif kind == "unsupported_type":
            item.find("type").text = "Unknown"
        elif kind == "duplicate_pid":
            processes.append(deepcopy(item))
        elif kind == "duplicate_field":
            item.append(deepcopy(item.find("pid")))
        elif kind == "multi_gpu":
            root.append(deepcopy(gpu))
        elif kind == "bad_driver":
            root.find("driver_version").text = "N/A"
        elif kind == "whitespace_name":
            item.find("process_name").text += " "
        payload = ET.tostring(root, encoding="unicode")
    with pytest.raises(ValueError):
        worker.parse_gpu_xml(payload)


@pytest.mark.parametrize("payload", [b"not json", b'{"approved": true, "approved": false}', b'[]', b'\xff', b'{"extra":NaN}'])
def test_invalid_baseline_json_is_not_ignored(tmp_path, monkeypatch, gpu_inventory, payload):
    path = tmp_path / "baseline.json"
    path.write_bytes(payload)
    mock_gpu_commands(monkeypatch, inventory_xml(gpu_inventory))
    with pytest.raises((ValueError, UnicodeError)):
        worker._gpu_preflight(path)


@pytest.mark.parametrize("error", [subprocess.CalledProcessError, subprocess.TimeoutExpired])
def test_baseline_does_not_bypass_required_qwen_inspection(tmp_path, monkeypatch, gpu_inventory, gpu_baseline, error):
    path = tmp_path / "baseline.json"
    audition.write_json(path, gpu_baseline)
    factory = ((lambda args: error(1, args)) if error is subprocess.CalledProcessError else (lambda args: error(args, 30)))
    commands = mock_gpu_commands(monkeypatch, inventory_xml(gpu_inventory), error=factory)
    with pytest.raises(error):
        worker._gpu_preflight(path)
    assert len(commands) == 1 and commands[0][0] == "powershell.exe"


def test_baseline_mutex_path_still_acquires_and_releases(mutex_api, monkeypatch, tmp_path):
    _, calls = mutex_api
    path = tmp_path / "operator-baseline.json"
    monkeypatch.setattr(worker, "_gpu_preflight", lambda value: calls.append(("baseline", value)) or {"exclusive_gpu": False})
    with worker.gpu_slot(path) as evidence:
        assert evidence["exclusive_gpu"] is False
    assert calls[2:] == [("baseline", path), ("release", 123), ("close", 123)]


def test_baseline_is_snapshotted_before_slot_and_bound_to_every_receipt(inputs, engine, gpu_baseline, monkeypatch):
    path = inputs.plan_path.parent / "operator-baseline.json"
    payload = json.dumps(gpu_baseline, indent=2).encode()
    path.write_bytes(payload)
    original_slot = worker.gpu_slot

    @contextmanager
    def slot(snapshot):
        assert snapshot == inputs.output / "gpu-baseline.json" and snapshot.read_bytes() == payload
        # The original input can change without changing the permission consumed.
        path.write_text("changed externally")
        with original_slot():
            yield {"baseline": read(snapshot), "baseline_sha256": audition.sha(snapshot), "exclusive_gpu": False,
                   "limitations": worker.GPU_LIMITATIONS}

    monkeypatch.setattr(worker, "gpu_slot", slot)
    state = worker.generate(inputs.model, inputs.output, inputs.setup_path, inputs.plan_path, inputs.reference, gpu_baseline=path)
    digest = hashlib.sha256(payload).hexdigest()
    assert state["gpu_baseline_sha256"] == state["gpu_slot"]["baseline_sha256"] == digest
    assert read(inputs.output / "gpu-evidence.json")["baseline"] == gpu_baseline
    assert (inputs.output / "gpu-baseline.json").read_bytes() == payload
    for segment in inputs.plan["segments"]:
        record = read(inputs.output / (segment["id"] + ".receipt.json"))
        assert record["gpu_baseline_sha256"] == digest and record["engine"]["gpu_slot"]["exclusive_gpu"] is False


def test_baseline_cannot_be_enclosed_by_output(inputs, engine):
    with pytest.raises(ValueError, match="separate"):
        worker.generate(inputs.model, inputs.output, inputs.setup_path, inputs.plan_path, inputs.reference,
                        gpu_baseline=inputs.output / "baseline.json")
    assert not inputs.output.exists() and not engine["lock"]


def test_cli_forwards_optional_baseline_without_changing_default_call(inputs, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(worker, "generate", lambda *args, **kwargs: calls.append((args, kwargs)) or {"status": "fixture", "done": []})
    path = inputs.plan_path.parent / "operator-baseline.json"
    worker.main(["generate", "--plan", str(inputs.plan_path), "--model", str(inputs.model), "--reference", str(inputs.reference),
                 "--setup-receipt", str(inputs.setup_path), "--output", str(inputs.output), "--gpu-baseline", str(path)])
    assert calls == [((inputs.model, inputs.output, inputs.setup_path, inputs.plan_path, inputs.reference), {"gpu_baseline": path})]
    assert json.loads(capsys.readouterr().out)["status"] == "fixture"


def test_flexible_runner_static_maintenance_and_create_only_contract():
    root = Path(__file__).resolve().parents[1]
    runner = (root / "scripts/run-windows-flexible-voxcpm.ps1").read_text()
    assert "'flexible_voxcpm.py'" in runner and "'voxcpm_narration.py'" not in runner
    for flag, variable in (("--plan", "$Plan"), ("--reference", "$Reference"), ("--gpu-baseline", "$GpuBaseline")):
        assert flag in runner and variable in runner
    assert runner.index("Threading.Mutex") > runner.index("if ($started) { $process.WaitForExit() }")
    assert "if (-not $restoreOwned)" in runner and "catch [Threading.AbandonedMutexException]" in runner
    assert "if ($restoreOwned) { $restoreMutex.ReleaseMutex() }" in runner
    assert runner.index("$restoreMutex.WaitOne(0)") < runner.index("Start-ScheduledTask")
    assert not any(command in runner for command in ("Stop-ScheduledTask", "Stop-Process", "taskkill", "Register-ScheduledTask"))
    assert "Get-NetTCPConnection -ErrorAction Stop" in runner and "$task.State -ne 'Ready'" in runner
    assert runner.index("Qwen is online") < runner.index("$started = $process.Start()")
    assert runner.count("$process.Start()") == 1 and runner.count("Start-ScheduledTask") == 1
    for path in ("$claimPath", "$stdout", "$stderr", "$restorePath"):
        assert f"[IO.File]::Open({path}, [IO.FileMode]::CreateNew" in runner
    assert "Set-Content" not in runner and "[IO.FileMode]::Create," not in runner
    assert runner.index("$processHandle = $process.Handle") < runner.index("$process.WaitForExit()") < runner.index("$workerExitCode = $process.ExitCode")
    assert "$null -eq $workerExitCode" in runner and "$workerExitCode -ne 0" in runner
    assert "if ($started) { $process.WaitForExit() }" in runner
    assert runner.index("finally {\n    try {") < runner.index("Start-ScheduledTask")
    assert "90 - $clock.Elapsed.TotalSeconds" in runner and "-MaximumRedirection 0" in runner
    assert "$health.status -eq 'ready'" in runner and "Authorization=('Bearer ' + $token)" in runner
    assert "555ee3544a45e2ab090d974e1f3c0f3cfb04db7eb0450b89f7f570d3e576ec93" in runner
    assert "c1d77e1fbb1a24e2474cea448e9d2e34f3b52a207d1fa7d8040bf033f7701766" in runner
    assert "[IO.File]::ReadAllText((Join-Path $Root 'private\\speech.token'))" in runner
    assert "inference_rerun=$false" in runner and "automatic_retry=$false" in runner
    for line in runner.splitlines():
        if any(command in line for command in ("Write-Output", "Write-Host", "Write-Warning", "Write-Error")):
            assert "$token" not in line
    args = runner[runner.index("$argsList ="):runner.index("$quotedArgs =")]
    assert "$token" not in args
