import hashlib
import json
from pathlib import Path
import shutil

import pytest

from manimind.postproduce import preset_audition as common
from manimind.postproduce import voxcpm_audition as worker
from manimind.postproduce import voxcpm_package as pack
from test_preset_audition import wav


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def sources(tmp_path):
    previous, generated = tmp_path / "previous", tmp_path / "generated"
    previous.mkdir()
    (previous / "raw").mkdir()
    (previous / "listening").mkdir()
    identities = ["A"] + [f"N{index:02d}" for index in range(1, 4)] + [f"D{index:02d}" for index in range(1, 11)] + [f"{index:02d}" for index in range(1, 14)]
    items = []
    for index, identity in enumerate(identities):
        raw = previous / "raw" / f"{identity}.wav"
        wav(raw, amplitude=1000 + index * 100)
        target = previous / "listening" / raw.name
        gain = common.level_copy(raw, target)
        group = "reference" if identity == "A" else "minimal" if identity.startswith("N") else "design" if identity.startswith("D") else "qwen" if int(identity) <= 5 else "kokoro"
        items.append({"id": identity, "voice": f"fixture {identity}", "group": group,
                      "raw": f"raw/{raw.name}", "listening": f"listening/{raw.name}",
                      "listening_gain": gain, "wav_sha256": common.sha(raw), "keep": {"nested": identity}})
    manifest = {"schema_version": 1, "request": {"input": common.TEXT}, "candidates": items,
                "groups": [{"id": name, "title": name, "detail": "fixture"} for name in ("reference", "minimal", "design", "qwen", "kokoro")],
                "accepted_voice": None, "footer": "Reference A is a benchmark, not approval"}
    common.write_json(previous / "manifest.json", manifest)
    for name in ("index.html", "README.md", "quality-check.json", "browser-check.json"):
        (previous / name).write_text(f"previous bytes: {name}")
    (previous / "other-evidence.txt").write_text("retain every previous file")

    generated.mkdir()
    (generated / "source").mkdir()
    shutil.copyfile(worker.__file__, generated / "source" / "voxcpm_audition.py")
    setup = {"schema_version": 1, "model_id": worker.MODEL, "revision": worker.REVISION,
             "files": [{"file": "weights.bin", "sha256": "a" * 64}], "declared_license": "Apache-2.0"}
    common.write_json(generated / "setup-receipt.json", setup)
    setup_hash = common.sha(generated / "setup-receipt.json")
    engine = {"model": worker.MODEL, "revision": worker.REVISION, "model_files": setup["files"],
              "model_files_sha256": hashlib.sha256(worker.canonical(setup["files"])).hexdigest(),
              "worker_sha256": common.sha(generated / "source" / "voxcpm_audition.py"),
              "setup_sha256": setup_hash, "load_options": worker.LOAD_OPTIONS, "packages": {"voxcpm": "2.0.3"}}
    common.write_json(generated / "engine.json", engine)
    common.write_json(generated / "state.json", {"status": "generated_not_listening_approved",
                      "attempted": list(worker.SEEDS), "done": list(worker.SEEDS), "setup_sha256": setup_hash})
    common.write_json(generated / "requests.json", [worker.request(seed) for seed in worker.SEEDS])
    for index, seed in enumerate(worker.SEEDS, 1):
        identity = f"V{index:02d}"
        measured = worker.save_audio(generated, identity, [0, 0.1 * index, -0.2 * index] * 160, 48000)
        common.write_json(generated / f"{identity}.receipt.json", {
            "id": identity, "seed": seed, "request": worker.request(seed),
            "generate_kwargs": {key: value for key, value in worker.request(seed).items() if key != "seed"},
            "seed_method": worker.SEED_METHOD, "engine": engine,
            "acceptance": "generated_not_listening_approved", "generation_seconds": .1, **measured})
    return previous, generated, tmp_path / "output"


def tree_bytes(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_append_keeps_27_candidates_and_all_old_files_including_a(sources):
    previous, generated, output = sources
    before, vox_before = tree_bytes(previous), tree_bytes(generated)
    original = read(previous / "manifest.json")
    result = pack.package(previous, generated, output)
    assert len(result["candidates"]) == 30
    assert [item["id"] for item in result["candidates"][:3]] == ["V01", "V02", "V03"]
    assert result["candidates"][3:] == original["candidates"]
    assert next(item for item in result["candidates"] if item["id"] == "A") == original["candidates"][0]
    assert result["groups"][0]["id"] == "vox" and result["groups"][0]["priority"] == -2
    assert next(group for group in result["groups"] if group["id"] == "reference")["priority"] == -1
    assert result["accepted_voice"] is None and result["acceptance"] == "awaiting_user_voice_selection"
    assert result["previous_manifest_sha256"] == common.sha(previous / "manifest.json")
    assert common.sha(output / result["previous_manifest"]) == result["previous_manifest_sha256"]
    assert result["vox_engine_sha256"] == common.sha(generated / "engine.json")
    assert result["packager_sha256"] == common.sha(pack.__file__)
    renamed = {name: f"{Path(name).stem}-before-vox{Path(name).suffix}" for name in ("manifest.json", "index.html", "README.md", "quality-check.json", "browser-check.json")}
    for name, payload in before.items():
        assert (output / renamed.get(name, name)).read_bytes() == payload
    assert tree_bytes(output / "vox") == vox_before
    assert tree_bytes(previous) == before and tree_bytes(generated) == vox_before
    for item in result["candidates"]:
        assert common.sha(output / item["raw"]) == item["wav_sha256"]
        payload, gain = common.level_payload(output / item["raw"])
        assert item["listening_gain"] == gain and (output / item["listening"]).read_bytes() == payload
    page = (output / "index.html").read_text()
    assert "__AUDITION_DATA__" not in page and '"priority": -2' in page
    assert all(item["gender"] == "未标注" and "description" not in item for item in result["candidates"][:3])


@pytest.mark.parametrize("change", ["raw", "listening", "gain", "self_reported_hash", "reassigned", "duplicate", "escape"])
def test_old_audio_and_derived_gain_must_match_before_creating_output(sources, change):
    previous, generated, output = sources
    manifest = read(previous / "manifest.json")
    item = manifest["candidates"][0]
    if change == "raw":
        (previous / item["raw"]).write_bytes(b"changed")
    elif change in ("listening", "self_reported_hash"):
        wav(previous / item["listening"], amplitude=7000)
        if change == "self_reported_hash":
            item["listening_gain"]["wav_sha256"] = common.sha(previous / item["listening"])
    elif change == "gain":
        item["listening_gain"]["gain_db"] += 1
    elif change == "reassigned":
        other = manifest["candidates"][1]
        item["listening"], item["listening_gain"] = other["listening"], other["listening_gain"]
    elif change == "duplicate":
        manifest["candidates"][-1]["id"] = item["id"]
    else:
        item["raw"] = "../outside.wav"
    (previous / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        pack.package(previous, generated, output)
    assert not output.exists()


@pytest.mark.parametrize("change", ["partial", "kwargs", "seed", "method", "wrong_method", "version", "wave", "float", "worker", "setup", "requests"])
def test_new_samples_are_bound_to_fixed_first_takes_and_sources(sources, change):
    previous, generated, output = sources
    receipt_path = generated / "V01.receipt.json"
    receipt = read(receipt_path)
    if change == "partial":
        path = generated / "state.json"
        value = read(path)
        value["done"] = [42, 43]
        path.write_text(json.dumps(value))
    elif change == "kwargs":
        receipt["generate_kwargs"]["seed"] = 42
    elif change == "seed":
        receipt["request"]["seed"] = 99
    elif change == "method":
        receipt.pop("seed_method")
    elif change == "wrong_method":
        receipt["seed_method"] = "not the frozen seeding protocol"
    elif change == "version":
        path = generated / "engine.json"
        value = read(path)
        value["packages"]["voxcpm"] = "2.0.4"
        path.write_text(json.dumps(value))
    elif change == "wave":
        (generated / "V01.wav").write_bytes(b"changed")
    elif change == "float":
        (generated / "V01.float32").write_bytes(b"changed")
    elif change == "worker":
        (generated / "source" / "voxcpm_audition.py").write_text("changed")
    elif change == "setup":
        (generated / "setup-receipt.json").write_text("{}")
    else:
        (generated / "requests.json").write_text("[]")
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises((ValueError, EOFError)):
        pack.package(previous, generated, output)
    assert not output.exists()


@pytest.mark.parametrize("source", ["previous", "vox"])
def test_no_nested_output_or_parent_creation(sources, source):
    previous, generated, _ = sources
    target = (previous if source == "previous" else generated) / "new-parent" / "output"
    with pytest.raises(ValueError, match="non-overlapping"):
        pack.package(previous, generated, target)
    assert not target.parent.exists()


def test_source_trees_also_cannot_overlap(sources):
    previous, _, output = sources
    with pytest.raises(ValueError, match="non-overlapping"):
        pack.package(previous, previous / "nested", output)
    assert not output.exists()


def test_existing_output_is_never_reused(sources):
    previous, generated, output = sources
    output.mkdir()
    (output / "keep").write_bytes(b"keep")
    before = tree_bytes(output)
    with pytest.raises(FileExistsError):
        pack.package(previous, generated, output)
    assert tree_bytes(output) == before


@pytest.mark.parametrize("name", ["vox", "manifest-before-vox.json", "listening/V01.wav"])
def test_reserved_new_paths_cannot_overwrite_previous_files(sources, name):
    previous, generated, output = sources
    (previous / name).write_text("keep")
    with pytest.raises(ValueError, match="already exist"):
        pack.package(previous, generated, output)
    assert not output.exists()


def test_unused_external_links_cannot_be_copied(sources, tmp_path):
    previous, generated, output = sources
    outside = tmp_path / "private"
    outside.write_bytes(b"not part of this package")
    (previous / "linked").symlink_to(outside)
    with pytest.raises(ValueError, match="symlinks"):
        pack.package(previous, generated, output)
    assert not output.exists()


def test_cli_is_the_requested_package_interface(sources, monkeypatch, capsys):
    previous, generated, output = sources
    called = []

    def package(*args):
        called.append(args)
        return {"candidates": [None] * 30, "accepted_voice": None}

    monkeypatch.setattr(pack, "package", package)
    pack.main(["package", "--previous", str(previous), "--vox", str(generated), "--output", str(output)])
    assert called == [(previous, generated, output)]
    assert json.loads(capsys.readouterr().out) == {"candidates": 30, "accepted_voice": None}
