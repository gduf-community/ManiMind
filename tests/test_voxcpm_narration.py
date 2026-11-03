from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import wave

import pytest

from manimind.postproduce import voxcpm_audition as audition
from manimind.postproduce import voxcpm_narration as narration


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text(json.dumps({"architecture": "voxcpm2", "audio_vae_config": {"out_sample_rate": 48000}}))
    (model / "weights.bin").write_bytes(b"fixture, not actual model weights")
    setup = {"schema_version": 1, "model_id": audition.MODEL, "revision": audition.REVISION,
             "model_path": str(model), "declared_license": "Apache-2.0",
             "files": [{"file": file.name, "sha256": audition.sha(file)} for file in sorted(model.iterdir())]}
    setup_path = tmp_path / "setup.json"
    audition.write_json(setup_path, setup)
    reference = tmp_path / "V01.wav"
    with wave.open(str(reference), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(b"\x00\x10\x00\xf0" * 240)
    monkeypatch.setattr(narration, "REFERENCE_SHA256", audition.sha(reference))
    plan = {"schema_version": 1, "reference_sha256": narration.REFERENCE_SHA256,
            "reference_text": audition.TEXT, "generation": dict(narration.GENERATION),
            "segments": [{"id": f"N{index:02d}", "cue": f"cue-{index:02d}", "anchor": f"anchor-{index:02d}",
                          "relation": "at", "text": f"  第{index}段批准文本。\n原字原句保留。  ", "anchor_time": index * 6}
                         for index in range(1, 18)],
            "source": {"config": "fixture.json", "delivery_sha256": "a" * 64, "video_sha256": "b" * 64,
                       "narration_sha256": "c" * 64}, "writer": "Main", "consumers": ["narration adapter"],
            "lifecycle": "approved text plan", "invalidation": "text or source changes", "extra_metadata": {"keep": True}}
    plan_path = tmp_path / "plan.json"
    audition.write_json(plan_path, plan)
    return SimpleNamespace(model=model, setup=setup_path, reference=reference, plan_path=plan_path,
                           plan=plan, output=tmp_path / "narration")


@pytest.fixture
def engine(monkeypatch):
    calls = {"load": [], "generate": [], "rng": [], "resets": 0}

    def reset():
        calls["resets"] += 1

    def generate(text, prompt_wav_path=None, prompt_text=None, reference_wav_path=None,
                 cfg_value=2.0, inference_timesteps=10, min_len=2, max_len=4096,
                 normalize=False, denoise=False, retry_badcase=True, retry_badcase_max_times=3,
                 retry_badcase_ratio_threshold=6.0, streaming=False):
        # Exact 2.0.3 _generate signature: an accidental seed kwarg raises TypeError.
        assert (min_len, max_len, retry_badcase_max_times, retry_badcase_ratio_threshold, streaming) == (2, 4096, 3, 6.0, False)
        calls["generate"].append({"text": text, "prompt_wav_path": prompt_wav_path, "prompt_text": prompt_text,
                                  "reference_wav_path": reference_wav_path, "cfg_value": cfg_value,
                                  "inference_timesteps": inference_timesteps, "normalize": normalize,
                                  "denoise": denoise, "retry_badcase": retry_badcase})
        assert calls["rng"][-4:] == [(name, 42) for name in ("random", "numpy", "torch", "cuda")]
        assert Path(reference_wav_path).is_file() and prompt_wav_path == reference_wav_path
        print("internal engine diagnostic, not a public progress event")
        if len(calls["generate"]) == calls.get("fail_on"):
            raise RuntimeError("fixture interrupted inference")
        return calls.get("samples", [0, .25, -.5, .125] * 120)

    def load(path, *, load_denoiser=True, optimize=True, device=None, local_files_only=False):
        calls["load"].append((path, {"load_denoiser": load_denoiser, "optimize": optimize,
                                    "device": device, "local_files_only": local_files_only}))
        assert (load_denoiser, optimize, device, local_files_only) == (False, False, "cuda", True)
        print("internal model loading diagnostic")
        return SimpleNamespace(tts_model=SimpleNamespace(sample_rate=calls.get("rate", 48000)), generate=generate)

    cuda = SimpleNamespace(is_available=lambda: calls.get("cuda", True), synchronize=lambda: None,
                           reset_peak_memory_stats=reset, get_device_name=lambda: "fixture GPU",
                           max_memory_allocated=lambda: 2 * 1024**2, max_memory_reserved=lambda: 3 * 1024**2,
                           manual_seed_all=lambda seed: calls["rng"].append(("cuda", seed)))
    torch = SimpleNamespace(cuda=cuda, version=SimpleNamespace(cuda="12.8"), inference_mode=nullcontext,
                            manual_seed=lambda seed: calls["rng"].append(("torch", seed)))
    numpy = SimpleNamespace(random=SimpleNamespace(seed=lambda seed: calls["rng"].append(("numpy", seed))))
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "numpy", numpy)
    monkeypatch.setitem(sys.modules, "voxcpm", SimpleNamespace(VoxCPM=SimpleNamespace(from_pretrained=load)))
    monkeypatch.setattr(narration.random, "seed", lambda seed: calls["rng"].append(("random", seed)))
    monkeypatch.setattr(narration.importlib.metadata, "version", lambda name: calls.get("sdk", "2.0.3") if name == "voxcpm" else "fixture-version")
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_IMPLICIT_TOKEN", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.setenv(key, "0")
    return calls


def run(inputs):
    return narration.generate(inputs.model, inputs.output, inputs.setup, inputs.plan_path, inputs.reference)


def test_real_reference_and_frozen_helper_constants():
    assert narration.REFERENCE_SHA256 == "b36f1c933b6d452df52e85571bd8de995f8513c2033e8c3d1d923a7cb79c0be9"
    assert narration.HELPER_SHA256 == audition.sha(audition.__file__)
    assert narration.GENERATION == {"seed": 42, "cfg_value": 2.0, "inference_timesteps": 10,
                                     "normalize": False, "denoise": False, "retry_badcase": False}


def test_two_file_deployment_help_and_import_do_not_load_models(tmp_path):
    for module in (narration, audition):
        shutil.copyfile(module.__file__, tmp_path / Path(module.__file__).name)
    check = """
import builtins, sys
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'numpy', 'voxcpm', 'qwen_tts', 'soundfile', 'manimind'}:
        raise AssertionError('unexpected heavy/project import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import voxcpm_narration
voxcpm_narration.main(['generate', '--help'])
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", check, str(tmp_path)], capture_output=True, text=True, check=True)
    assert all(flag in result.stdout for flag in ("--plan", "--reference", "--setup-receipt", "--model", "--output"))


def test_full_plan_keeps_text_metadata_reference_and_emits_progress(inputs, engine, capsys):
    state = run(inputs)
    identities = [f"N{index:02d}" for index in range(1, 18)]
    assert state["attempted"] == state["done"] == identities
    assert state["call_count"] == 17 and state["model_load_count"] == 1
    assert state["status"] == "generated_not_listening_or_alignment_approved"
    assert read(inputs.output / "state.json") == state
    assert engine["load"] == [(str(inputs.model), audition.LOAD_OPTIONS)]
    assert len(engine["generate"]) == 17 and engine["resets"] == 18
    assert engine["rng"] == [(name, 42) for _ in identities for name in ("random", "numpy", "torch", "cuda")]
    assert (inputs.output / "plan.json").read_bytes() == inputs.plan_path.read_bytes()
    assert (inputs.output / "setup-receipt.json").read_bytes() == inputs.setup.read_bytes()
    assert (inputs.output / "reference.wav").read_bytes() == inputs.reference.read_bytes()
    for module in (narration, audition):
        assert (inputs.output / "source" / Path(module.__file__).name).read_bytes() == Path(module.__file__).read_bytes()
    requests = read(inputs.output / "requests.json")
    for index, (segment, kwargs) in enumerate(zip(inputs.plan["segments"], engine["generate"]), 1):
        identity = segment["id"]
        record = read(inputs.output / f"{identity}.receipt.json")
        assert kwargs == narration.generate_kwargs(segment, inputs.output / "reference.wav", audition.TEXT)
        assert "seed" not in kwargs and kwargs["text"] == segment["text"]
        assert kwargs["prompt_text"] == audition.TEXT
        assert record["id"] == identity and record["segment"] == segment
        assert record["request"] == record["generate_kwargs"] == kwargs == requests[index - 1]["request"]
        assert record["seed"] == 42 and record["seed_method"] == audition.SEED_METHOD
        assert record["call_count"] == index and record["segment_call_count"] == 1 and record["pid"] == os.getpid()
        assert record["attempted"] == record["done"] == identities[:index]
        assert record["reference_sha256"] == audition.sha(inputs.reference)
        assert record["plan_sha256"] == audition.sha(inputs.plan_path)
        assert record["setup_sha256"] == audition.sha(inputs.setup)
        assert record["worker_sha256"] == audition.sha(narration.__file__)
        assert record["helper_sha256"] == audition.sha(audition.__file__)
        assert record["wav_sha256"] == audition.sha(inputs.output / f"{identity}.wav")
        assert record["float32_sha256"] == audition.sha(inputs.output / f"{identity}.float32")
        assert record["sample_rate"] == 48000 and record["duration_seconds"] == .01
        assert record["generation_seconds"] >= 0 and record["engine"]["packages"]["voxcpm"] == "2.0.3"
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[0]["event"] == "loading" and events[-1]["event"] == "completed"
    assert [event["id"] for event in events if event["event"] == "segment_started"] == identities
    assert [event["id"] for event in events if event["event"] == "segment_done"] == identities
    assert events[-1]["done_count"] == 17 and events[-1]["call_count"] == 17
    assert "internal engine diagnostic" in (inputs.output / "generation.log").read_text()


@pytest.mark.parametrize("change", ["schema", "ref_hash", "ref_text", "seed", "retry", "bool_seed", "short", "id", "text", "anchor"])
def test_invalid_plan_never_loads_or_rewrites_approved_text(inputs, engine, change):
    value = inputs.plan
    if change == "schema":
        value["schema_version"] = True
    elif change == "ref_hash":
        value["reference_sha256"] = "0" * 64
    elif change == "ref_text":
        value["reference_text"] += " changed"
    elif change == "seed":
        value["generation"]["seed"] = 43
    elif change == "retry":
        value["generation"]["retry_badcase"] = True
    elif change == "bool_seed":
        value["generation"]["seed"] = True
    elif change == "short":
        value["segments"].pop()
    elif change == "id":
        value["segments"][1]["id"] = "N01"
    elif change == "text":
        value["segments"][0]["text"] = "  "
    else:
        value["segments"][0]["anchor_time"] = -1
    inputs.plan_path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        run(inputs)
    assert not engine["load"] and not engine["generate"]
    state = read(inputs.output / "state.json")
    assert state["status"] == "failed" and state["attempted"] == state["done"] == [] and state["call_count"] == 0
    assert (inputs.output / "plan.json").read_bytes() == inputs.plan_path.read_bytes()


@pytest.mark.parametrize("change", ["reference", "helper", "model", "sdk", "cpu", "rate"])
def test_source_and_loading_failures_leave_evidence_without_inference(inputs, engine, monkeypatch, change):
    if change == "reference":
        inputs.reference.write_bytes(b"not the selected V01")
    elif change == "helper":
        monkeypatch.setattr(narration, "HELPER_SHA256", "0" * 64)
    elif change == "model":
        (inputs.model / "weights.bin").write_bytes(b"changed")
    elif change == "sdk":
        engine["sdk"] = "2.0.4"
    elif change == "cpu":
        engine["cuda"] = False
    else:
        engine["rate"] = 24000
    with pytest.raises(ValueError):
        run(inputs)
    assert not engine["generate"]
    state = read(inputs.output / "state.json")
    assert state["status"] == "failed" and state["call_count"] == 0 and state["done"] == state["attempted"] == []
    assert "Traceback" in read(inputs.output / "failure.json")["traceback"]


def test_failed_fourth_call_keeps_first_three_and_never_retries(inputs, engine, capsys):
    engine["fail_on"] = 4
    with pytest.raises(RuntimeError, match="interrupted"):
        run(inputs)
    state = read(inputs.output / "state.json")
    assert state["attempted"] == ["N01", "N02", "N03", "N04"]
    assert state["done"] == ["N01", "N02", "N03"] and state["call_count"] == 4
    assert len(engine["generate"]) == 4
    assert len(list(inputs.output.glob("*.receipt.json"))) == 3
    assert not (inputs.output / "N05.wav").exists()
    before = (inputs.output / "state.json").read_bytes()
    with pytest.raises(FileExistsError):
        run(inputs)
    assert (inputs.output / "state.json").read_bytes() == before
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1]["event"] == "failed" and events[-1]["id"] == "N04"


@pytest.mark.parametrize("samples", [[float("nan")], [1.2], [0, 0]])
def test_invalid_audio_retains_native_float_evidence_and_does_not_reroll(inputs, engine, samples):
    engine["samples"] = samples
    with pytest.raises(ValueError):
        run(inputs)
    assert (inputs.output / "N01.float32").exists()
    state = read(inputs.output / "state.json")
    assert state["attempted"] == ["N01"] and state["done"] == [] and state["call_count"] == 1
    assert len(engine["generate"]) == 1 and not (inputs.output / "N01.wav").exists()


def test_nonempty_existing_output_is_untouched(inputs, engine):
    inputs.output.mkdir()
    sentinel = inputs.output / "keep"
    sentinel.write_bytes(b"previous attempt")
    with pytest.raises(FileExistsError):
        run(inputs)
    assert list(inputs.output.iterdir()) == [sentinel] and sentinel.read_bytes() == b"previous attempt"
    assert not engine["load"]


def test_output_cannot_pollute_model_or_contain_plan_inputs(inputs, engine):
    inputs.output = inputs.model / "new-parent" / "narration"
    with pytest.raises(ValueError, match="separate"):
        run(inputs)
    assert not inputs.output.parent.exists() and not engine["load"]


def test_exact_cli_argument_order(inputs, monkeypatch, capsys):
    calls = []

    def generate(*args):
        calls.append(args)
        return {"status": "fixture", "done": ["N01"]}

    monkeypatch.setattr(narration, "generate", generate)
    narration.main(["generate", "--model", str(inputs.model), "--output", str(inputs.output),
                    "--setup-receipt", str(inputs.setup), "--plan", str(inputs.plan_path), "--reference", str(inputs.reference)])
    assert calls == [(inputs.model, inputs.output, inputs.setup, inputs.plan_path, inputs.reference)]
    assert json.loads(capsys.readouterr().out)["done"] == ["N01"]
