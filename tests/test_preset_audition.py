import array
import hashlib
import json
import math
import wave

import pytest

from manimind.postproduce import preset_audition as audition


def wav(path, amplitude=6000):
    samples = array.array("h", (round(amplitude * math.sin(n / 12)) for n in range(2400)))
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes(samples.tobytes())


def candidates(output):
    audition.prepare(output)
    engine = {"model": "qwen3-tts-1.7b-customvoice", "model_files_sha256": audition.QWEN_MODEL_HASH,
              "worker_sha256": audition.QWEN_WORKER_HASH, "qwen_tts_version": "fixture",
              "torch_version": "fixture", "cuda_runtime": "fixture", "gpu": "fixture",
              "attention": "fixture", "dtype": "fixture"}
    audition.write_json(output / "qwen-engine.json", {"engine": engine})
    files = [{"file": name, "sha256": value} for name, value in audition.MODEL_HASHES.items()]
    audition.write_json(output / "kokoro-setup-receipt.json", {"model_id": audition.MODEL, "revision": audition.REVISION, "files": files})
    (output / "generation-adapter.py").write_text("test fixture, not an actual model adapter")
    for engine in ("qwen", "kokoro"):
        (output / engine).mkdir()
    specs = [(n, "qwen", v) for n, (v, _, _) in enumerate(audition.QWEN, 1)]
    specs += [(n, "kokoro", v) for n, v in enumerate(audition.KOKORO, 6)]
    for number, engine, voice in specs:
        target = output / engine / f"{number:02d}-{voice}.wav"
        wav(target)
        if engine == "qwen":
            source = audition.read_json(output / "qwen-engine.json")["engine"]
            record = {"request": audition.qwen_request(voice), "wav_sha256": audition.sha(target),
                      "server": {"X-Request-ID": hashlib.sha256(audition.canonical({"request": audition.qwen_request(voice), "engine": source})).hexdigest()}}
        else:
            source = {"model": audition.MODEL, "revision": audition.REVISION, "model_files": files,
                      "adapter_sha256": audition.sha(output / "generation-adapter.py"), "gpu": "fixture",
                      "model_load_seconds": .1, "packages": {}, "python": "fixture", "device": "fixture", "dtype": "fixture"}
            record = {"request": {**audition.request(), "voice": voice}, "wav_sha256": audition.sha(target), "engine": source}
        audition.write_json(target.with_suffix(".receipt.json"), record)


@pytest.mark.parametrize("change", [{"instructions": "teacher role"}, {"input": "different text"},
    {"seed": True}, {"seed": 1729.0}, {"speed": True}, {"speed": .8}, {"reference": "private.wav"}])
def test_neutral_request_has_no_role_prompt_or_reference(change):
    with pytest.raises(ValueError):
        audition.validate_request({**audition.request(), **change})


def test_prepare_is_exclusive_and_uses_one_text(tmp_path):
    output = tmp_path / "audition"
    audition.prepare(output)
    assert audition.read_json(output / "request.json") == audition.request()
    with pytest.raises(FileExistsError):
        audition.prepare(output)


def test_levels_change_gain_only_and_preserve_original(tmp_path):
    source, target = tmp_path / "raw.wav", tmp_path / "level.wav"
    wav(source, 1000)
    original = source.read_bytes()
    info, before = audition.pcm_info(source)
    record = audition.level_copy(source, target)
    after_info, after = audition.pcm_info(target)
    gain = 10 ** (record["gain_db"] / 20)
    assert source.read_bytes() == original
    assert len(before) == len(after) and info["duration_seconds"] == after_info["duration_seconds"]
    assert all(abs(b - a * gain) <= .51 for a, b in zip(before, after))
    assert after_info["rms_dbfs"] == pytest.approx(-23, abs=.01)
    assert after_info["clipped_samples"] == 0
    with pytest.raises(FileExistsError):
        audition.level_copy(source, target)


def test_peak_ceiling_not_dynamic_compression(tmp_path):
    source = tmp_path / "raw.wav"
    samples = array.array("h", [100] * 2399 + [32000])
    with wave.open(str(source), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes(samples.tobytes())
    audition.level_copy(source, tmp_path / "leveled.wav")
    info, _ = audition.pcm_info(tmp_path / "leveled.wav")
    assert info["sample_peak"] <= math.ceil(32767 * 10 ** (-1 / 20))


@pytest.mark.parametrize("amplitude", [0])
def test_silence_rejected(tmp_path, amplitude):
    wav(tmp_path / "silent.wav", amplitude)
    with pytest.raises(ValueError, match="Silent"):
        audition.pcm_info(tmp_path / "silent.wav")


def test_package_contains_thirteen_bound_audio_choices_without_approval(tmp_path):
    output = tmp_path / "audition"
    candidates(output)
    manifest = audition.package(output)
    assert len(manifest["candidates"]) == 13
    assert manifest["accepted_voice"] is None
    assert manifest["acceptance"] == "awaiting_user_voice_selection"
    assert all((output / item["raw"]).is_file() and (output / item["listening"]).is_file() for item in manifest["candidates"])
    page = (output / "index.html").read_text()
    assert "__AUDITION_DATA__" not in page
    assert "<audio" not in page  # Players are built from the embedded manifest.
    assert "document.createElement('audio')" in page
    assert json.loads((output / "manifest.json").read_text()) == manifest
    with pytest.raises(ValueError, match="overwritten"):
        audition.package(output)


@pytest.mark.parametrize("field,value", [("input", "changed"), ("instructions", "teacher"), ("voice", "wrong")])
def test_mismatched_audio_never_packaged(tmp_path, field, value):
    output = tmp_path / "audition"
    candidates(output)
    target = output / "qwen" / "01-Vivian.receipt.json"
    record = audition.read_json(target)
    record["request"][field] = value
    target.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        audition.package(output)
    assert not (output / "index.html").exists()


def test_model_manifest_requires_all_voices_and_safe_paths(tmp_path, monkeypatch):
    model = tmp_path / "model"
    model.mkdir()
    names = ["config.json", "kokoro-v1_0.pth"] + [f"voices/{voice}.pt" for voice in audition.KOKORO]
    records = []
    for name in names:
        path = model / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"test fixture, not actual model")
        records.append({"file": name, "sha256": audition.sha(path)})
    setup = {"model_id": audition.MODEL, "revision": audition.REVISION, "model_path": str(model), "files": records}
    monkeypatch.setattr(audition, "MODEL_HASHES", {item["file"]: item["sha256"] for item in records})
    assert audition.validate_setup(setup) == model
    with pytest.raises(ValueError):
        audition.validate_setup({**setup, "files": records[:-1]})
    outside = tmp_path / "unintended.pt"
    outside.write_bytes(b"outside")
    with pytest.raises(ValueError):
        audition.validate_setup({**setup, "files": records + [{"file": "../unintended.pt", "sha256": audition.sha(outside)}]})


@pytest.mark.parametrize("engine,field,value", [("kokoro", "reference", "private.wav"), ("qwen", "reference", "private.wav"),
    ("qwen", "response_format", "mp3"), ("qwen", "model", "other-model")])
def test_candidate_request_schema_is_closed(tmp_path, engine, field, value):
    output = tmp_path / "audition"
    candidates(output)
    target = output / engine / ("06-zf_xiaobei.receipt.json" if engine == "kokoro" else "01-Vivian.receipt.json")
    record = audition.read_json(target)
    record["request"][field] = value
    target.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        audition.collect(output)


@pytest.mark.parametrize("change", [{"model": "other-model"}, {"reference": "private.wav"}, {"adapter_sha256": "changed"}])
def test_kokoro_engine_identity_cannot_be_relabelled(tmp_path, change):
    output = tmp_path / "audition"
    candidates(output)
    target = output / "kokoro" / "06-zf_xiaobei.receipt.json"
    record = audition.read_json(target)
    record["engine"].update(change)
    target.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        audition.collect(output)


def test_changed_config_manifest_is_rejected():
    records = [{"file": name, "sha256": value} for name, value in audition.MODEL_HASHES.items()]
    records[0]["sha256"] = "different_config"
    with pytest.raises(ValueError):
        audition.validate_model_records(records)
