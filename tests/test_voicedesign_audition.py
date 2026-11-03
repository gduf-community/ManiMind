import hashlib
import json
from pathlib import Path
import shutil

import pytest

from manimind.postproduce import voicedesign_audition as design
from manimind.postproduce import preset_audition as common
from test_preset_audition import candidates as preset_fixture, wav


def setup_manifest():
    records = [{"file": name, "sha256": value, "official_blob": "fixture", "origin": "fixture-not-model"}
               for name, value in design.WEIGHTS.items()]
    records += [{"file": name, "sha256": hashlib.sha256(name.encode()).hexdigest(), "official_blob": value, "origin": "fixture-not-model"}
                for name, value in design.BLOBS.items()]
    return {"model_id": design.MODEL, "revision": design.REVISION, "files": records}


def design_fixture(root, profile_set="original"):
    root.mkdir()
    value = design.plan(profile_set)
    common.write_json(root / "plan.json", value)
    setup = setup_manifest()
    common.write_json(root / "setup-receipt.json", setup)
    (root / "source").mkdir()
    sources = {}
    for module in (design, common):
        source = Path(module.__file__)
        target = root / "source" / source.name
        shutil.copyfile(source, target)
        sources[source.name] = common.sha(target)
    engine = {"model": design.MODEL, "revision": design.REVISION, "model_files": setup["files"], "sources": sources,
              "packages": {"fixture": "not-actual-inference"}, "gpu": "fixture", "device": "cuda:0", "dtype": "bfloat16",
              "attention": "sdpa", "python": "fixture", "model_load_seconds": .1}
    request = {k: v for k, v in value.items() if k not in {"profiles", "context"}}
    for profile in value["profiles"]:
        target = root / f"{profile['id']}.wav"
        wav(target)
        common.write_json(target.with_suffix(".receipt.json"), {"request": request, "profile": profile, "engine": engine,
                          "wav_sha256": common.sha(target), "generation_seconds": .1})


def test_plan_uses_same_text_and_original_designs_without_teacher_persona():
    plan = design.validate_plan(design.plan())
    assert plan["input"] == common.TEXT
    assert len(plan["profiles"]) == 10
    assert len({p["id"] for p in plan["profiles"]}) == 10
    assert sum(p["gender"] == "女声" for p in plan["profiles"]) == 6
    assert sum(p["gender"] == "男声" for p in plan["profiles"]) == 4
    assert all("不要老师腔" in p["instructions"] and "不模仿具体人物" in p["instructions"] for p in plan["profiles"])
    assert "reference" not in json.dumps(plan)


@pytest.mark.parametrize("change", [{"input": "different"}, {"seed": True}, {"non_streaming_mode": False},
    {"reference_audio": "private.wav"}, {"model": "different"}])
def test_plan_rejects_changed_inputs_and_reference_audio(change):
    with pytest.raises(ValueError):
        design.validate_plan({**design.plan(), **change})


@pytest.mark.parametrize("path", ["../outside.wav", "/tmp/outside.wav", "https://example.org/audio.wav", "C:\\private.wav", None])
def test_local_paths_stay_inside_audition(tmp_path, path):
    with pytest.raises(ValueError):
        design.local_file(tmp_path, path)


def test_closed_model_manifest_rejects_private_or_missing_files():
    setup = setup_manifest()
    design.validate_records(setup)
    with pytest.raises(ValueError):
        design.validate_records({**setup, "files": setup["files"] + [{"file": "private.wav"}]})
    with pytest.raises(ValueError):
        design.validate_records({**setup, "files": setup["files"][:-1]})
    with pytest.raises(ValueError):
        design.validate_records({**setup, "model_id": "different-model"})


@pytest.mark.parametrize("extra", ["tokenizer.json", "added_tokens.json"])
def test_loader_directory_rejects_unlisted_configs(tmp_path, monkeypatch, extra):
    config = b'{"tts_model_type":"voice_design","tts_model_size":"1b7"}'
    weights = b"test fixture, not model weights"
    (tmp_path / "config.json").write_bytes(config)
    (tmp_path / "model.safetensors").write_bytes(weights)
    blob = hashlib.sha1(b"blob " + str(len(config)).encode() + b"\0" + config).hexdigest()
    monkeypatch.setattr(design, "BLOBS", {"config.json": blob})
    monkeypatch.setattr(design, "WEIGHTS", {"model.safetensors": hashlib.sha256(weights).hexdigest()})
    setup = {"model_id": design.MODEL, "revision": design.REVISION, "model_path": str(tmp_path), "files": [
        {"file": "config.json", "sha256": hashlib.sha256(config).hexdigest(), "official_blob": blob},
        {"file": "model.safetensors", "sha256": hashlib.sha256(weights).hexdigest()}]}
    assert design.validate_setup(setup) == tmp_path
    (tmp_path / extra).write_text("{}")
    with pytest.raises(ValueError, match="undeclared"):
        design.validate_setup(setup)


def test_collector_validates_all_ten_audio_sources(tmp_path):
    design_fixture(tmp_path / "design")
    records = design.collect(tmp_path / "design")
    assert len(records) == 10 and all(item["group"] == "design" for item in records)
    assert records[0]["id"] == "D01" and records[-1]["id"] == "D10"
    (tmp_path / "design" / "source" / "preset_audition.py").write_text("changed")
    with pytest.raises(ValueError):
        design.collect(tmp_path / "design")


@pytest.mark.parametrize("kind", ["request", "profile", "engine", "hash"])
def test_collector_never_accepts_relabelled_or_reference_candidates(tmp_path, kind):
    root = tmp_path / "design"
    design_fixture(root)
    path = root / "D01.receipt.json"
    record = common.read_json(path)
    if kind == "request":
        record["request"]["reference_audio"] = "private.wav"
    elif kind == "profile":
        record["profile"]["instructions"] = "teacher persona"
    elif kind == "engine":
        record["engine"]["reference"] = "private.wav"
    else:
        record["wav_sha256"] = "changed"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        design.collect(root)


def test_combined_package_keeps_original_audio_and_ids(tmp_path):
    baseline, designed, output = (tmp_path / name for name in ("baseline", "design", "combined"))
    preset_fixture(baseline)
    old = common.package(baseline)
    design_fixture(designed)
    manifest = design.package_combined(baseline, designed, output)
    assert len(manifest["candidates"]) == 23
    assert manifest["candidates"][0]["id"] == "D01"
    assert manifest["candidates"][10]["id"] == "01"
    assert manifest["accepted_voice"] is None
    for previous, candidate in zip(old["candidates"], manifest["candidates"][10:]):
        assert (baseline / previous["raw"]).read_bytes() == (output / candidate["raw"]).read_bytes()
        assert (baseline / previous["listening"]).read_bytes() == (output / candidate["listening"]).read_bytes()
    for candidate in manifest["candidates"]:
        assert common.sha(output / candidate["raw"]) == candidate["wav_sha256"]
        assert common.sha(output / candidate["listening"]) == candidate["listening_gain"]["wav_sha256"]
    with pytest.raises(FileExistsError):
        design.package_combined(baseline, designed, output)


def test_combined_package_rejects_changed_old_listening_copy(tmp_path):
    baseline, designed = tmp_path / "baseline", tmp_path / "design"
    preset_fixture(baseline)
    manifest = common.package(baseline)
    design_fixture(designed)
    (baseline / manifest["candidates"][0]["listening"]).write_bytes(b"changed")
    with pytest.raises(ValueError):
        design.package_combined(baseline, designed, tmp_path / "combined")


def test_minimal_plan_uses_only_short_plain_female_descriptions():
    value = design.validate_plan(design.plan("minimal-female"))
    assert value["input"] == common.TEXT and value["seed"] == design.plan()["seed"]
    assert [p["id"] for p in value["profiles"]] == ["N01", "N02", "N03"]
    assert len(value["profiles"]) == 3
    for profile in value["profiles"]:
        assert profile["gender"] == "女声"
        assert profile["instructions"] == profile["description"]
        assert len(profile["instructions"]) <= 32
        assert not any(word in profile["instructions"] for word in ("老师", "乙游", "温柔", "亲近", "明亮", "播音", "推销"))
    assert len(design.plan()["profiles"]) == 10
    assert "audition_set" not in design.plan()["context"]


def test_minimal_collect_is_separate_from_old_designs(tmp_path):
    root = tmp_path / "minimal"
    design_fixture(root, "minimal-female")
    items = design.collect(root)
    assert len(items) == 3
    assert all(item["group"] == "minimal" and item["kind"] == "design" for item in items)


def previous_fixture(tmp_path):
    baseline, designed, previous = (tmp_path / name for name in ("baseline", "design", "previous"))
    preset_fixture(baseline)
    common.package(baseline)
    design_fixture(designed)
    design.package_combined(baseline, designed, previous)
    return previous


def test_append_preserves_all_twenty_three_previous_audio_candidates(tmp_path):
    previous = previous_fixture(tmp_path)
    before = design.validate_combined(previous)
    minimal, output = tmp_path / "minimal", tmp_path / "appended"
    design_fixture(minimal, "minimal-female")
    result = design.append_minimal(previous, minimal, output)
    assert len(result["candidates"]) == 26
    assert result["candidates"][:3][0]["id"] == "N01"
    assert result["groups"][0]["id"] == "minimal" and result["groups"][0]["priority"] == 0
    assert result["candidates"][3:] == before["candidates"]
    assert result["accepted_voice"] is None
    assert (previous / "index.html").read_bytes() == (output / "index-23.html").read_bytes()
    assert common.sha(output / "manifest-23.json") == common.sha(previous / "manifest.json")
    for item in before["candidates"]:
        for field in ("raw", "listening"):
            assert (previous / item[field]).read_bytes() == (output / item[field]).read_bytes()
    with pytest.raises(FileExistsError):
        design.append_minimal(previous, minimal, output)


@pytest.mark.parametrize("change", ["description", "listening", "request"])
def test_append_rejects_changed_previous_package(tmp_path, change):
    previous = previous_fixture(tmp_path)
    manifest = common.read_json(previous / "manifest.json")
    if change == "description":
        manifest["candidates"][0]["description"] = "different target"
    elif change == "request":
        manifest["request"]["input"] = "different text"
    else:
        (previous / manifest["candidates"][0]["listening"]).write_bytes(b"changed audio")
    (previous / "manifest.json").write_text(json.dumps(manifest))
    minimal = tmp_path / "minimal"
    design_fixture(minimal, "minimal-female")
    with pytest.raises(ValueError):
        design.append_minimal(previous, minimal, tmp_path / "appended")


@pytest.mark.parametrize("change_path", [True, False])
def test_listening_copy_cannot_be_reassigned_with_a_self_reported_hash(tmp_path, change_path):
    previous = previous_fixture(tmp_path)
    manifest = common.read_json(previous / "manifest.json")
    item = manifest["candidates"][0]
    if change_path:
        target = previous / "unrelated.wav"
        item["listening"] = target.name
    else:
        target = previous / item["listening"]
    wav(target, amplitude=500)
    item["listening_gain"]["wav_sha256"] = common.sha(target)
    (previous / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="bound"):
        design.validate_combined(previous)


@pytest.mark.parametrize("parent", ["previous", "minimal"])
def test_append_rejects_nested_output_before_creating_any_directory(tmp_path, parent):
    previous, minimal = tmp_path / "previous", tmp_path / "minimal"
    previous.mkdir()
    minimal.mkdir()
    output = (previous if parent == "previous" else minimal) / "new-child" / "appended"
    with pytest.raises(ValueError, match="non-nested"):
        design.append_minimal(previous, minimal, output)
    assert not output.parent.exists()
