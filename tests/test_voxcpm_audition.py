import array
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import wave

import pytest

from manimind.postproduce import preset_audition as common
from manimind.postproduce import voxcpm_audition as vox


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def setup(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text(json.dumps({"architecture": "voxcpm2", "audio_vae_config": {"out_sample_rate": 48000}}))
    (model / "weights.bin").write_bytes(b"fixture, not model weights")
    (model / ".gitattributes").write_text("fixture")
    (model / "tokenization.py").write_text("raise RuntimeError('must not execute fixture code')")
    value = {"schema_version": 1, "model_id": vox.MODEL, "revision": vox.REVISION,
             "model_path": str(model), "declared_license": "Apache-2.0",
             "files": [{"file": file.name, "sha256": vox.sha(file)} for file in sorted(model.iterdir())]}
    receipt = tmp_path / "setup.json"
    vox.write_json(receipt, value)
    return model, receipt, value


@pytest.fixture
def engine(monkeypatch):
    calls = {"load": [], "generate": [], "resets": 0, "syncs": 0, "seeds": []}

    def reset():
        calls["resets"] += 1

    def synchronize():
        calls["syncs"] += 1

    def generate(*, text, cfg_value, inference_timesteps, normalize, denoise, retry_badcase):
        calls["generate"].append({"text": text, "cfg_value": cfg_value,
                                  "inference_timesteps": inference_timesteps, "normalize": normalize,
                                  "denoise": denoise, "retry_badcase": retry_badcase})
        return calls.get("samples", [0.0, 0.25, -0.5, 0.125] * 120)

    def load(*args, **kwargs):
        calls["load"].append((args, kwargs))
        if "load_error" in calls:
            raise calls["load_error"]
        return SimpleNamespace(tts_model=SimpleNamespace(sample_rate=calls.get("rate", 48000)), generate=generate)

    def seed_for(name):
        return lambda seed: calls["seeds"].append((name, seed))

    cuda = SimpleNamespace(is_available=lambda: calls.get("cuda", True), synchronize=synchronize,
                           reset_peak_memory_stats=reset, get_device_name=lambda: "fixture GPU",
                           manual_seed_all=seed_for("cuda"),
                           max_memory_allocated=lambda: 2 * 1024**2, max_memory_reserved=lambda: 3 * 1024**2)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda, manual_seed=seed_for("torch"), version=SimpleNamespace(cuda="fixture CUDA"), inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(random=SimpleNamespace(seed=seed_for("numpy"))))
    monkeypatch.setattr(vox.random, "seed", seed_for("random"))
    monkeypatch.setitem(sys.modules, "voxcpm", SimpleNamespace(VoxCPM=SimpleNamespace(from_pretrained=load)))
    monkeypatch.setattr(vox.importlib.metadata, "version", lambda name: "2.0.3" if name == "voxcpm" else "fixture-version")
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_IMPLICIT_TOKEN", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.setenv(name, "0")
    return calls


def test_fixed_shared_text_and_exact_unconditioned_requests():
    assert vox.TEXT == common.TEXT
    assert vox.SEEDS == (42, 43, 44)
    for seed in vox.SEEDS:
        assert vox.request(seed) == {"text": common.TEXT, "cfg_value": 2.0, "inference_timesteps": 10,
                                     "normalize": False, "denoise": False, "retry_badcase": False, "seed": seed}
    assert vox.LOAD_OPTIONS == {"load_denoiser": False, "optimize": False, "device": "cuda", "local_files_only": True}


def test_other_sdk_version_is_rejected_before_loading_weights(setup, engine, monkeypatch, tmp_path):
    model, receipt, _ = setup
    monkeypatch.setattr(vox.importlib.metadata, "version", lambda name: "2.0.4")
    with pytest.raises(ValueError, match="2.0.3 API"):
        vox.generate(model, tmp_path / "wrong-sdk", receipt)
    assert not engine["load"] and not engine["generate"]


@pytest.mark.parametrize("seed", [True, 42.0, 41, 45, None, "42"])
def test_other_seeds_are_not_a_selection_or_retry_option(seed):
    with pytest.raises(ValueError):
        vox.request(seed)


def test_standalone_copy_import_and_help_need_no_project_or_heavy_packages(tmp_path):
    worker = tmp_path / "worker.py"
    shutil.copyfile(vox.__file__, worker)
    check = """
import builtins, importlib.util, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'voxcpm', 'qwen_tts', 'numpy', 'soundfile', 'manimind'}:
        raise AssertionError('Unexpected import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
spec = importlib.util.spec_from_file_location('standalone', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main(['generate', '--help'])
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", check, str(worker)], capture_output=True, text=True, check=True)
    assert all(option in result.stdout for option in ("--model", "--output", "--setup-receipt"))


def test_setup_checks_every_declared_file_and_native_config(setup):
    model, _, value = setup
    assert vox.validate_setup(value, model) == model
    (model / "weights.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        vox.validate_setup(value, model)


@pytest.mark.parametrize("changes", [
    {"schema_version": True}, {"schema_version": 2}, {"model_id": "other"}, {"revision": "main"},
    {"declared_license": ""}, {"declared_license": None}, {"files": []}, {"model_path": "missing"}
])
def test_wrong_or_unpinned_setup_is_refused(setup, changes):
    model, _, value = setup
    with pytest.raises(ValueError):
        vox.validate_setup({**value, **changes}, model)


@pytest.mark.parametrize("name", ["../outside.bin", "/outside.bin", "C:/outside.bin", "C:\\outside.bin",
    "\\\\server\\weights", "weights.bin:stream", "./weights.bin", "sub//weights.bin", "sub/../weights.bin",
    "sub/", "NUL", "CON.txt", "file.", "file ", "*.bin", "", None])
def test_model_paths_are_windows_safe_and_cannot_escape(setup, name):
    model, _, _ = setup
    with pytest.raises(ValueError):
        vox.local_file(model, name)


@pytest.mark.parametrize("kind", ["duplicate", "case", "hash", "missing", "unlisted"])
def test_closed_manifest_rejects_ambiguous_or_undeclared_sources(setup, kind):
    model, _, value = setup
    if kind == "duplicate":
        value["files"].append(value["files"][0].copy())
    elif kind == "case":
        (model / "OTHER.bin").write_bytes(b"case")
        (model / "other.bin").write_bytes(b"case")
        value["files"].extend({"file": name, "sha256": vox.sha(model / name)} for name in ("OTHER.bin", "other.bin"))
    elif kind == "hash":
        value["files"][0]["sha256"] = "not-a-hash"
    elif kind == "missing":
        (model / "weights.bin").unlink()
    else:
        (model / "extra.json").write_text("{}")
    with pytest.raises(ValueError):
        vox.validate_setup(value, model)


def test_links_even_with_matching_hashes_are_not_model_sources(setup, tmp_path):
    model, _, value = setup
    outside = tmp_path / "outside.bin"
    outside.write_bytes((model / "weights.bin").read_bytes())
    (model / "weights.bin").unlink()
    (model / "weights.bin").symlink_to(outside)
    with pytest.raises(ValueError):
        vox.validate_setup(value, model)


@pytest.mark.parametrize("change", [{"architecture": "voxcpm"}, {"audio_vae_config": {"out_sample_rate": 24000}}])
def test_even_self_consistent_wrong_model_configs_are_refused(setup, change):
    model, _, value = setup
    config = model / "config.json"
    config.write_text(json.dumps({**read(config), **change}))
    next(item for item in value["files"] if item["file"] == "config.json")["sha256"] = vox.sha(config)
    with pytest.raises(ValueError, match="native 48000"):
        vox.validate_setup(value, model)


def test_three_first_takes_are_kept_with_exact_parameters_and_bound_receipts(setup, engine, tmp_path):
    model, receipt, value = setup
    output = tmp_path / "audition"
    state = vox.generate(model, output, receipt)
    assert state["status"] == "generated_not_listening_approved"
    assert state["attempted"] == state["done"] == [42, 43, 44]
    assert read(output / "state.json") == state
    assert engine["load"] == [((str(model),), vox.LOAD_OPTIONS)]
    assert engine["generate"] == [vox.generate_kwargs(seed) for seed in vox.SEEDS]
    assert engine["seeds"] == [(name, seed) for seed in vox.SEEDS for name in ("random", "numpy", "torch", "cuda")]
    assert engine["resets"] == 4
    assert read(output / "requests.json") == [vox.request(seed) for seed in vox.SEEDS]
    assert (output / "setup-receipt.json").read_bytes() == receipt.read_bytes()
    assert (output / "source" / "voxcpm_audition.py").read_bytes() == Path(vox.__file__).read_bytes()
    assert not (output / "state.json.tmp").exists()
    for index, seed in enumerate(vox.SEEDS, 1):
        identity = f"V{index:02d}"
        record = read(output / f"{identity}.receipt.json")
        assert record["seed"] == seed and record["request"] == vox.request(seed)
        assert record["generate_kwargs"] == vox.generate_kwargs(seed) and "seed" not in record["generate_kwargs"]
        assert record["seed_method"] == vox.SEED_METHOD
        assert record["sample_rate"] == 48000 and record["frames"] == 480
        assert record["duration_seconds"] == .01
        assert record["finite"] and record["clipped_samples"] == 0
        assert record["wav_sha256"] == vox.sha(output / f"{identity}.wav")
        assert record["float32_sha256"] == vox.sha(output / record["float32_file"])
        assert record["peak_torch_allocated_mib"] == 2 and record["peak_torch_reserved_mib"] == 3
        assert record["generation_seconds"] >= 0
        source = record["engine"]
        assert source["revision"] == vox.REVISION and source["model_files"] == value["files"]
        assert source["worker_sha256"] == vox.sha(vox.__file__)
        assert source["setup_sha256"] == vox.sha(receipt)
        assert source["model_files_sha256"] == hashlib.sha256(vox.canonical(value["files"])).hexdigest()
        assert source["packages"]["voxcpm"] == "2.0.3"
        assert source["load_options"] == vox.LOAD_OPTIONS
        assert record["acceptance"] == "generated_not_listening_approved"
        assert "gender" not in record and "description" not in record
        with wave.open(str(output / f"{identity}.wav"), "rb") as audio:
            assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) == (1, 2, 48000, 480)
            pcm = array.array("h", audio.readframes(480))
            if sys.byteorder != "little":
                pcm.byteswap()
            assert list(pcm[:4]) == [0, 8192, -16384, 4096]


def test_output_is_create_only_before_any_engine_call(setup, engine, tmp_path):
    model, receipt, _ = setup
    output = tmp_path / "audition"
    output.mkdir()
    sentinel = output / "keep.bin"
    sentinel.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        vox.generate(model, output, receipt)
    assert sentinel.read_bytes() == b"original" and list(output.iterdir()) == [sentinel]
    assert not engine["load"] and not engine["generate"]


def test_output_cannot_pollute_model_or_setup_inputs(setup, engine):
    model, receipt, _ = setup
    output = model / "new-parent" / "audition"
    with pytest.raises(ValueError, match="non-nested"):
        vox.generate(model, output, receipt)
    assert not output.parent.exists()
    assert not engine["load"]


def test_bad_setup_retains_failure_without_importing_the_engine(setup, engine, tmp_path):
    model, receipt, _ = setup
    (model / "weights.bin").write_bytes(b"tampered")
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        vox.generate(model, output, receipt)
    state = read(output / "state.json")
    assert state["status"] == "failed" and state["attempted"] == state["done"] == []
    assert read(output / "failure.json")["error_type"] == "ValueError"
    assert (output / "setup-receipt.json").read_bytes() == receipt.read_bytes()
    assert not engine["load"] and not engine["generate"]


@pytest.mark.parametrize("kind", ["cpu", "load", "rate"])
def test_loading_failures_never_trigger_a_take_or_cpu_fallback(setup, engine, tmp_path, kind):
    model, receipt, _ = setup
    if kind == "cpu":
        engine["cuda"] = False
    elif kind == "load":
        engine["load_error"] = RuntimeError("fixture load failed")
    else:
        engine["rate"] = 24000
    output = tmp_path / "failed"
    with pytest.raises((ValueError, RuntimeError)):
        vox.generate(model, output, receipt)
    state = read(output / "state.json")
    assert state["status"] == "failed" and state["attempted"] == state["done"] == []
    assert not engine["generate"]
    assert "Traceback" in read(output / "failure.json")["traceback"]


@pytest.mark.parametrize("samples", [[], [float("nan")], [float("inf")], [-float("inf")],
    [1.0], [-1.0], [1.01], [0.0, 0.0], [0.999999]])
def test_invalid_audio_is_not_repaired_retried_or_silently_discarded(setup, engine, tmp_path, samples):
    model, receipt, _ = setup
    engine["samples"] = samples
    output = tmp_path / "failed"
    with pytest.raises(ValueError):
        vox.generate(model, output, receipt)
    state = read(output / "state.json")
    assert state["status"] == "failed" and state["attempted"] == [42] and state["done"] == []
    assert len(engine["generate"]) == 1
    assert (output / "V01.float32").exists()
    assert not list(output.glob("*.wav")) and not list(output.glob("*.receipt.json"))
    assert read(output / "failure.json")["attempted"] == [42]


def test_failed_second_take_keeps_first_take_and_does_not_repeat_or_skip_seed(setup, engine, monkeypatch, tmp_path):
    model, receipt, _ = setup
    original = sys.modules["voxcpm"].VoxCPM.from_pretrained

    def load(*args, **kwargs):
        model_instance = original(*args, **kwargs)
        generate = model_instance.generate

        def fail_second(**request):
            if len(engine["generate"]) == 1:
                engine["generate"].append(request)
                raise RuntimeError("fixture interrupted take")
            return generate(**request)

        model_instance.generate = fail_second
        return model_instance

    monkeypatch.setattr(sys.modules["voxcpm"].VoxCPM, "from_pretrained", load)
    output = tmp_path / "partial"
    with pytest.raises(RuntimeError, match="interrupted"):
        vox.generate(model, output, receipt)
    state = read(output / "state.json")
    assert state["attempted"] == [42, 43] and state["done"] == [42]
    first = output / "V01.wav"
    assert first.exists() and read(output / "V01.receipt.json")["wav_sha256"] == vox.sha(first)
    assert not (output / "V03.wav").exists()
    assert len(engine["generate"]) == 2
    assert all("seed" not in item for item in engine["generate"])
    with pytest.raises(FileExistsError):
        vox.generate(model, output, receipt)


def test_cli_accepts_existing_runner_arguments(setup, monkeypatch, tmp_path, capsys):
    model, receipt, _ = setup
    output = tmp_path / "audition"
    captured = []

    def generate(*args):
        captured.append(args)
        return {"status": "generated_not_listening_approved", "done": [42, 43, 44]}

    monkeypatch.setattr(vox, "generate", generate)
    vox.main(["generate", "--model", str(model), "--output", str(output), "--setup-receipt", str(receipt)])
    assert captured == [(model, output, receipt)]
    assert json.loads(capsys.readouterr().out)["done"] == [42, 43, 44]
