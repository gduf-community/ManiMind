"""Download-free contract tests; the real-model smoke is separately archived."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import wave

import pytest

from manimind.postproduce import phrase_alignment as align


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def inputs(tmp_path):
    references = [
        {"id": "R01", "focus": "first", "text": "\u5148\u770b\u8fd9\u4e2a\u70b9\u3002"},
        {"id": "R02", "focus": "second", "text": "\u518d\u8ba9\u5b83\u6162\u6162\u9760\u8fd1\u3002"},
    ]
    unit = {"id": "U01", "cue": "continuous", "focus": "whole_unit",
            "text": "".join(row["text"] for row in references),
            "focus_scope": "meaning_unit_not_visual_focus", "references": references}
    plan = {"schema_version": 2, "reference_sha256": align.transport.REFERENCE_SHA256,
            "reference_text": align.transport.audition.TEXT, "synthetic_reference": True,
            "reference_source": "synthetic V01", "generation": align.transport.GENERATION,
            "segments": [unit]}
    plan_path = tmp_path / "plan.json"
    speech = tmp_path / "speech"
    speech.mkdir()
    wav = speech / "U01.wav"
    with wave.open(str(wav), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\x01\x00" * (16000 * 6))
    write_json(plan_path, plan)
    receipt = {"schema_version": 2, "id": unit["id"], "segment": unit,
               "plan_sha256": align.sha256(plan_path), "wav_sha256": align.sha256(wav),
               "request": {"text": unit["text"]}, "first_take": True, "segment_call_count": 1,
               "acceptance": align.transport.ACCEPTANCE, "reference_sha256": plan["reference_sha256"],
               **align._wav_info(wav)}
    receipt_path = speech / "U01.receipt.json"
    write_json(receipt_path, receipt)
    result = {"segments": [
        {"text": " " + references[0]["text"], "start": 0.12, "end": 1.45,
         "words": [{"word": " " + references[0]["text"], "start": 0.12, "end": 1.45}]},
        {"text": " " + references[1]["text"], "start": 1.62, "end": 5.84,
         "words": [{"word": " " + references[1]["text"], "start": 1.62, "end": 5.84}]},
    ]}
    return {"plan": plan, "plan_path": plan_path, "speech": speech, "wav": wav,
            "receipt": receipt_path, "output": tmp_path / "timings.json", "result": result}


def factory(inputs, *, change=None, action=None, error=None):
    calls = []

    class FakeBackend:
        def __init__(self, **options):
            self.identity = {"backend": "fake_download_free", "model": options}

        def align(self, **request):
            calls.append(request)
            with wave.open(request["audio"], "rb") as stream:
                assert stream.getnframes() == 6 * 16000  # Entire WAV, never a cut.
            if error:
                raise error
            result = deepcopy(inputs["result"])
            if change:
                change(result)
            if action:
                action()
            return result

    return FakeBackend, calls


def run(inputs, backend=None, **kwargs):
    backend = backend or factory(inputs)[0]
    return align.align_plan(inputs["plan_path"], inputs["speech"], inputs["output"],
                            backend_factory=backend, **kwargs)


def attempts(inputs):
    return sorted(inputs["output"].parent.glob(inputs["output"].name + ".attempts/*"))


def test_normal_multiple_clauses_in_one_continuous_wav(inputs):
    backend, calls = factory(inputs)
    value = run(inputs, backend)
    assert len(calls) == 1
    assert calls[0] == {"audio": str(inputs["wav"]), "language": "zh", "original_split": True,
                        "text": "\n".join(r["text"] for r in inputs["plan"]["segments"][0]["references"])}
    assert value == read(inputs["output"])
    assert value["schema_version"] == 1 and value["method"] == align.METHOD
    assert value["timing_scope"] == align.TIMING_SCOPE
    assert value["smoke_only"] is False
    assert value["test_only"] is True
    assert value["plan_sha256"] == align.sha256(inputs["plan_path"])
    unit = value["units"][0]
    assert unit["wav_sha256"] == align.sha256(inputs["wav"])
    assert unit["duration_seconds"] == 6
    assert [(p["id"], p["start"], p["end"]) for p in unit["phrases"]] == [
        ("R01", 0.12, 1.45), ("R02", 1.62, 5.84)]
    assert all(value[key] for key in ("writer", "consumers", "lifecycle", "invalidation", "software", "sources"))
    assert (attempts(inputs)[0] / "U01.raw.json").exists()
    assert len(value["sources"]) >= 7


def test_multiple_units_each_use_one_full_wav_and_relative_clock(inputs):
    first = inputs["plan"]["segments"][0]
    second = deepcopy(first)
    second["id"] = "U02"
    inputs["plan"]["segments"].append(second)
    write_json(inputs["plan_path"], inputs["plan"])
    receipt = read(inputs["receipt"])
    receipt["plan_sha256"] = align.sha256(inputs["plan_path"])
    write_json(inputs["receipt"], receipt)
    second_wav = inputs["speech"] / "U02.wav"
    second_wav.write_bytes(inputs["wav"].read_bytes())
    write_json(inputs["speech"] / "U02.receipt.json", {**receipt, "id": "U02", "segment": second})
    backend, calls = factory(inputs)
    value = run(inputs, backend)
    assert len(calls) == 2
    assert [Path(call["audio"]).name for call in calls] == ["U01.wav", "U02.wav"]
    assert [u["phrases"][0]["start"] for u in value["units"]] == [0.12, 0.12]
    assert [u["phrases"][0]["id"] for u in value["units"]] == ["R01", "R01"]


def test_json_serializable_upstream_float_subclasses_keep_exact_times(inputs):
    class UpstreamFloat(float):
        pass

    def upstream_scalars(result):
        for segment in result["segments"]:
            for row in [segment, *segment["words"]]:
                for key in ("start", "end"):
                    row[key] = UpstreamFloat(row[key])

    value = run(inputs, factory(inputs, change=upstream_scalars)[0])
    assert [(p["start"], p["end"]) for p in value["units"][0]["phrases"]] == [
        (0.12, 1.45), (1.62, 5.84)]


@pytest.mark.parametrize("where", ["first", "middle", "last"])
def test_instant_word_estimates_are_preserved_and_explicitly_uncertain(inputs, where):
    def instant_word(result):
        segment = result["segments"][0]
        text = segment["text"]
        if where == "first":
            segment["words"] = [{"word": text[:2], "start": .12, "end": .12},
                                {"word": text[2:], "start": .12, "end": 1.45}]
        elif where == "last":
            segment["words"] = [{"word": text[:-1], "start": .12, "end": 1.45},
                                {"word": text[-1:], "start": 1.45, "end": 1.45}]
        else:
            segment["words"] = [{"word": text[:2], "start": .12, "end": .5},
                                {"word": text[2:3], "start": .5, "end": .5},
                                {"word": text[3:], "start": .5, "end": 1.45}]

    value = run(inputs, factory(inputs, change=instant_word)[0])
    phrase = value["units"][0]["phrases"][0]
    raw = read(attempts(inputs)[0] / "U01.raw.json")["segments"][0]
    assert phrase["words"] == raw["words"]
    assert phrase["instantaneous_word_indices"] == [0 if where == "first" else 1]
    assert "uncertain" in phrase["word_timing_warning"]
    assert (phrase["start"], phrase["end"]) == (.12, 1.45)
    assert value["test_only"] is True


@pytest.mark.parametrize("bad", [
    {"start": .5, "end": .4}, {"start": -.1, "end": .12},
    {"start": .12, "end": 1.5}, {"start": float("nan"), "end": 1.45},
    {"start": .12, "end": True},
])
def test_allowing_instant_words_never_repairs_invalid_word_intervals(inputs, bad):
    def invalid_word(result):
        result["segments"][0]["words"][0].update(bad)

    with pytest.raises(ValueError):
        run(inputs, factory(inputs, change=invalid_word)[0])
    assert (attempts(inputs)[0] / "failure.json").exists()
    assert not inputs["output"].exists()


@pytest.mark.parametrize("mutation", [
    lambda r: r["segments"].pop(),
    lambda r: r["segments"].append(deepcopy(r["segments"][0])),
    lambda r: r["segments"].reverse(),
    lambda r: r["segments"][0].update(text="changed"),
    lambda r: r["segments"][0].update(text="  " + r["segments"][0]["text"]),
    lambda r: r["segments"][0].update(start=1.5, end=1.4),
    lambda r: r["segments"][1].update(start=1.0),
    lambda r: r["segments"][0].update(start=-0.01),
    lambda r: r["segments"][1].update(end=6.01),
    lambda r: r["segments"][0].update(start=float("nan")),
    lambda r: r["segments"][0].update(end=float("inf")),
    lambda r: r["segments"][0].update(start=True),
    lambda r: r["segments"][0].update(start=0.12, end=0.12),
    lambda r: r["segments"][0]["words"][0].update(word="different"),
    lambda r: r["segments"][0]["words"][0].update(word=None),
    lambda r: r["segments"][0]["words"][0].update(start=0.0),
    lambda r: r["segments"][0].update(words=[]),
], ids=["missing", "extra", "reordered", "text", "whitespace", "reverse", "overlap",
        "negative", "outside", "nan", "inf", "boolean", "instant", "word-text", "malformed-word", "word-bound", "no-words"])
def test_reject_bad_actual_results_and_preserve_raw(inputs, mutation):
    with pytest.raises(ValueError):
        run(inputs, factory(inputs, change=mutation)[0])
    assert not inputs["output"].exists()
    attempt = attempts(inputs)[0]
    assert (attempt / "U01.raw.json").exists()
    assert read(attempt / "failure.json")["automatic_retry"] is False
    assert (attempt / "plan.json").read_bytes() == inputs["plan_path"].read_bytes()


@pytest.mark.parametrize("change", [
    lambda p: p["segments"][0].pop("focus_scope"),
    lambda p: p["segments"][0].update(focus_scope="visual_focus"),
    lambda p: p["segments"][0].update(references=[]),
    lambda p: p["segments"][0].update(text="changed"),
    lambda p: p["segments"][0]["references"][1].update(id="R01"),
    lambda p: p["segments"][0]["references"][0].update(text="first\nline"),
    lambda p: p["segments"][0]["references"][0].update(focus=""),
])
def test_plan_contract_fails_before_backend(inputs, change):
    change(inputs["plan"])
    write_json(inputs["plan_path"], inputs["plan"])
    backend, calls = factory(inputs)
    with pytest.raises(ValueError):
        run(inputs, backend)
    assert not calls and not inputs["output"].exists()


@pytest.mark.parametrize("target", ["wav", "plan_path", "receipt"])
def test_input_drift_during_alignment_fails_closed(inputs, target):
    def mutate():
        with inputs[target].open("ab") as stream:
            stream.write(b" ")

    with pytest.raises(ValueError, match="drift"):
        run(inputs, factory(inputs, action=mutate)[0])
    assert not inputs["output"].exists()
    assert (attempts(inputs)[0] / "failure.json").exists()


def test_symlink_retarget_during_alignment_fails_closed(inputs):
    original = inputs["wav"].with_name("original.wav")
    original.write_bytes(inputs["wav"].read_bytes())
    replacement = original.with_name("replacement.wav")
    replacement.write_bytes(original.read_bytes() + b"changed")
    inputs["wav"].unlink()
    inputs["wav"].symlink_to(original)

    def retarget():
        inputs["wav"].unlink()
        inputs["wav"].symlink_to(replacement)

    with pytest.raises(ValueError, match="drift"):
        run(inputs, factory(inputs, action=retarget)[0])
    assert not inputs["output"].exists()


@pytest.mark.parametrize("field,value", [
    ("wav_sha256", "0" * 64), ("plan_sha256", "0" * 64), ("id", "other"),
    ("first_take", False), ("segment_call_count", 2), ("duration_seconds", 8),
    ("segment", {}), ("request", {"text": "rewritten"}),
])
def test_reject_stale_or_edited_receipt(inputs, field, value):
    receipt = read(inputs["receipt"])
    receipt[field] = value
    write_json(inputs["receipt"], receipt)
    backend, calls = factory(inputs)
    with pytest.raises(ValueError):
        run(inputs, backend)
    assert not calls


def test_plan_drift_from_generation_receipt(inputs):
    inputs["plan"]["additional_metadata"] = "different plan bytes"
    write_json(inputs["plan_path"], inputs["plan"])
    with pytest.raises(ValueError, match="mismatch"):
        run(inputs)


def test_create_only_with_recorded_second_attempt(inputs):
    run(inputs)
    original = inputs["output"].read_bytes()
    with pytest.raises(FileExistsError):
        run(inputs)
    assert inputs["output"].read_bytes() == original
    assert len(attempts(inputs)) == 2
    assert sum((p / "failure.json").exists() for p in attempts(inputs)) == 1


def test_dangling_symlink_is_not_overwritten(inputs):
    target = inputs["output"].with_name("not-created.json")
    inputs["output"].symlink_to(target)
    with pytest.raises(FileExistsError):
        run(inputs)
    assert inputs["output"].is_symlink() and not target.exists()


def test_racing_output_is_not_overwritten(inputs):
    def competitor():
        inputs["output"].write_bytes(b"competitor timestamps")

    with pytest.raises(FileExistsError):
        run(inputs, factory(inputs, action=competitor)[0])
    assert inputs["output"].read_bytes() == b"competitor timestamps"
    assert (attempts(inputs)[0] / "failure.json").exists()


def test_backend_exception_and_repeated_failure_preserved(inputs):
    backend, calls = factory(inputs, error=RuntimeError("model failed"))
    for _ in range(2):
        with pytest.raises(RuntimeError, match="model failed"):
            run(inputs, backend)
    assert len(calls) == 2 and len(attempts(inputs)) == 2
    for attempt in attempts(inputs):
        assert read(attempt / "failure.json")["error_type"] == "RuntimeError"


def test_none_result_does_not_invent_timing(inputs):
    backend, _ = factory(inputs)
    backend.align = lambda self, **kwargs: None
    with pytest.raises(ValueError, match="omitted"):
        run(inputs, backend)
    assert read(attempts(inputs)[0] / "U01.raw.json") is None


def test_smoke_requires_unchanged_original_generation_plan_and_receipt(inputs):
    generation = inputs["plan_path"].with_name("generation-plan.json")
    generation.write_bytes(inputs["plan_path"].read_bytes())
    original_receipt, original_wav = inputs["receipt"].read_bytes(), inputs["wav"].read_bytes()
    inputs["plan"]["alignment_smoke_source"] = {
        "generation_plan": str(generation), "generation_plan_sha256": align.sha256(generation)}
    write_json(inputs["plan_path"], inputs["plan"])
    value = run(inputs)
    assert value["smoke_only"] is True
    assert value["plan_sha256"] != align.sha256(generation)
    assert inputs["receipt"].read_bytes() == original_receipt
    assert inputs["wav"].read_bytes() == original_wav
    assert (attempts(inputs)[0] / "generation-plan.json").read_bytes() == generation.read_bytes()


def test_smoke_source_hash_drift_rejected(inputs):
    inputs["plan"]["alignment_smoke_source"] = {
        "generation_plan": str(inputs["plan_path"]), "generation_plan_sha256": "0" * 64}
    write_json(inputs["plan_path"], inputs["plan"])
    with pytest.raises(ValueError, match="Smoke generation plan drift"):
        run(inputs)


def test_words_are_optional_not_a_replacement_for_missing_clauses(inputs):
    for segment in inputs["result"]["segments"]:
        segment.pop("words")
    assert len(run(inputs)["units"][0]["phrases"]) == 2


def test_cli_success(inputs, monkeypatch, capsys):
    monkeypatch.setattr(align, "StableWhisperBackend", factory(inputs)[0])
    assert align.main(["--plan", str(inputs["plan_path"]), "--speech", str(inputs["speech"]),
                       "--output", str(inputs["output"])]) == 0
    assert json.loads(capsys.readouterr().out)["timing_scope"] == align.TIMING_SCOPE


def test_cli_failure_retains_attempt(inputs, monkeypatch, capsys):
    monkeypatch.setattr(align, "StableWhisperBackend", factory(inputs, error=RuntimeError("offline"))[0])
    assert align.main(["--plan", str(inputs["plan_path"]), "--speech", str(inputs["speech"]),
                       "--output", str(inputs["output"])]) == 1
    assert json.loads(capsys.readouterr().err)["status"] == "failed"
    assert len(attempts(inputs)) == 1


@pytest.mark.parametrize("options", [{"model": "base.en"}, {"device": "mps"}])
def test_no_english_model_or_shared_gpu(inputs, options):
    with pytest.raises(ValueError, match="CPU"):
        run(inputs, **options)


@pytest.fixture
def synthetic_production_evidence(inputs, monkeypatch):
    """Temporary synthetic evidence, explicitly mocking the trusted runtime boundary.

    No files in the real ASR setup, installed runtime, or real smoke are edited.
    This is a verifier contract fixture, never evidence of model execution.
    """
    runtime = inputs["output"].parent / "SYNTHETIC-TEST-RUNTIME-NOT-A-REAL-MODEL"
    runtime.mkdir()

    def bound(name):
        path = runtime / name
        path.write_text("synthetic verifier fixture, not real model software: " + name, encoding="ascii")
        return {"path": str(path), "sha256": align.sha256(path)}

    trusted = {
        "backend": "stable_whisper", "source_url": align.UPSTREAM_URL, "declared_license": "MIT",
        "packages": {"synthetic-runtime-boundary": "not-real"}, "python_version": sys.version.split()[0],
        "executable": str(runtime / "python"), "platform": "synthetic-test-only", "device": "cpu",
        "source_files": [bound("stable_whisper.py"), bound("whisper.py")],
        "environment_files": [bound("runtime-metadata.txt")],
        "ffmpeg": {**bound("ffmpeg"), "version": "synthetic"},
        "model": {**bound("base.pt"), "name": "base", "multilingual": True,
                  "source_url": "https://example.invalid/SYNTHETIC-NOT-REAL", "declared_license": "MIT"},
        "align_options": {"language": "zh", "original_split": True, "verbose": None},
    }
    monkeypatch.setattr(align, "_production_software_identity", lambda model: deepcopy(trusted))
    identity = {k: v for k, v in trusted.items() if k != "python_version"}
    identity.update(python=sys.version, cpu_threads=2)

    class SyntheticBoundaryBackend:
        def __init__(self, **kwargs):
            self.identity = deepcopy(identity)

        def align(self, **kwargs):
            result = deepcopy(inputs["result"])
            result.update(language="zh", text="".join(s["text"] for s in result["segments"]))
            return result

    # Production-path fixture only: both the default constructor and its trusted
    # identity resolver are replaced locally, never a real inference or receipt.
    monkeypatch.setattr(align, "StableWhisperBackend", SyntheticBoundaryBackend)
    value = align.align_plan(inputs["plan_path"], inputs["speech"], inputs["output"])
    return {**inputs, "value": value, "attempt": Path(value["attempt"]), "trusted": trusted}


def verify(production):
    return align.verify_production_timings(production["output"], plan_path=production["plan_path"],
                                           speech=production["speech"])


def reseal_synthetic_evidence(production):
    """Test-only resealing checks semantics beyond a simple stale-hash failure."""
    value, attempt = production["value"], production["attempt"]
    for item in value["sources"]:
        if Path(item["path"]).is_file():
            item["sha256"] = align.sha256(item["path"])
    inputs = read(attempt / "inputs.json")
    for item in inputs["sources"]:
        if Path(item["path"]).is_file():
            item["sha256"] = align.sha256(item["path"])
    write_json(attempt / "inputs.json", inputs)
    for item in value["sources"]:
        if Path(item["path"]).is_file():
            item["sha256"] = align.sha256(item["path"])
    write_json(production["output"], value)
    completed = read(attempt / "completed.json")
    completed["result_sha256"] = align.sha256(production["output"])
    write_json(attempt / "completed.json", completed)


def test_production_verifier_checks_complete_synthetic_contract_without_writes(synthetic_production_evidence):
    p = synthetic_production_evidence
    assert p["value"]["test_only"] is False
    before = {str(path): align.sha256(path) for path in p["output"].parent.rglob("*") if path.is_file()}
    first, second = verify(p), verify(p)
    after = {str(path): align.sha256(path) for path in p["output"].parent.rglob("*") if path.is_file()}
    assert before == after and first == second
    assert first["units"] == p["value"]["units"]
    assert first["evidence_sha256"] == align._evidence_digest(first["files"])
    paths = {row["path"] for row in first["files"]}
    assert str(p["output"]) in paths
    for name in ("started.json", "completed.json", "inputs.json", "software.json", "plan.json",
                 "result.json", "backend.log", "U01.request.json", "U01.raw.json", "U01.receipt.json"):
        assert str(p["attempt"] / name) in paths
    assert len(paths) > len(p["value"]["sources"])


@pytest.mark.parametrize("field,bad", [
    ("sources", None), ("sources", []), ("software", None), ("software", {}), ("attempt", None),
    ("test_only", None), ("test_only", True), ("smoke_only", None), ("smoke_only", True),
    ("listening_reviewed", None), ("listening_reviewed", True),
])
def test_production_rejects_missing_or_nonproduction_state(synthetic_production_evidence, field, bad):
    p = synthetic_production_evidence
    p["value"][field] = bad
    with pytest.raises(ValueError):
        align.verify_alignment_evidence(p["value"], p["plan_path"], p["speech"])


@pytest.mark.parametrize("name", ["started.json", "completed.json", "inputs.json", "software.json",
    "U01.request.json", "U01.raw.json", "U01.receipt.json", "source/phrase_alignment.py", "result.json"])
def test_production_rejects_any_missing_attempt_evidence(synthetic_production_evidence, name):
    p = synthetic_production_evidence
    (p["attempt"] / name).unlink()
    with pytest.raises(ValueError):
        verify(p)


@pytest.mark.parametrize("name", ["inputs.json", "software.json", "U01.request.json", "U01.raw.json",
    "source/requirements-phrase-alignment.txt", "source/phrase_alignment.py"])
def test_production_rejects_evidence_drift(synthetic_production_evidence, name):
    p = synthetic_production_evidence
    with (p["attempt"] / name).open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError):
        verify(p)


def test_completion_byte_drift_changes_downstream_evidence_digest(synthetic_production_evidence):
    p = synthetic_production_evidence
    frozen = verify(p)
    with (p["attempt"] / "completed.json").open("ab") as stream:
        stream.write(b" ")
    current = verify(p)
    assert frozen["evidence_sha256"] != current["evidence_sha256"]
    assert frozen["files"] != current["files"]


@pytest.mark.parametrize("field,bad", [("result_sha256", None), ("result_sha256", "0" * 64),
    ("status", "failed"), ("test_only", True), ("model", "base.en")])
def test_completion_semantic_drift_rejected(synthetic_production_evidence, field, bad):
    p = synthetic_production_evidence
    path = p["attempt"] / "completed.json"
    record = read(path)
    record[field] = bad
    write_json(path, record)
    with pytest.raises(ValueError):
        verify(p)


def test_production_rejects_raw_text_drift_even_after_test_hashes_are_resealed(synthetic_production_evidence):
    p = synthetic_production_evidence
    raw_path = p["attempt"] / "U01.raw.json"
    raw = read(raw_path)
    raw["segments"][0]["text"] = "Changed actual raw clause"
    write_json(raw_path, raw)
    reseal_synthetic_evidence(p)
    with pytest.raises(ValueError):
        verify(p)


def test_production_rejects_raw_time_change_even_after_test_hashes_are_resealed(synthetic_production_evidence):
    p = synthetic_production_evidence
    raw_path = p["attempt"] / "U01.raw.json"
    raw = read(raw_path)
    raw["segments"][0]["end"] = raw["segments"][0]["words"][0]["end"] = 1.4
    write_json(raw_path, raw)
    reseal_synthetic_evidence(p)
    with pytest.raises(ValueError, match="Emitted phrase"):
        verify(p)


@pytest.mark.parametrize("field,bad", [("language", "en"), ("original_split", False),
    ("text", "changed request"), ("audio", "/wrong/rewritten.wav")])
def test_production_rejects_resealed_wrong_request(synthetic_production_evidence, field, bad):
    p = synthetic_production_evidence
    path = p["attempt"] / "U01.request.json"
    value = read(path)
    value[field] = bad
    write_json(path, value)
    reseal_synthetic_evidence(p)
    with pytest.raises(ValueError, match="request differs"):
        verify(p)


@pytest.mark.parametrize("field,bad", [("backend", "FAKE-NO-MODEL"), ("model", {}),
    ("packages", {}), ("source_files", []), ("environment_files", []), ("validation_replay", {})])
def test_production_rejects_resealed_fake_model_software(synthetic_production_evidence, field, bad):
    p = synthetic_production_evidence
    software = p["value"]["software"]
    software[field] = bad
    write_json(p["attempt"] / "software.json", software)
    reseal_synthetic_evidence(p)
    with pytest.raises(ValueError):
        verify(p)


def test_production_rejects_resealed_sources_omitting_real_engine(synthetic_production_evidence):
    p = synthetic_production_evidence
    engine_path = p["trusted"]["source_files"][0]["path"]
    p["value"]["sources"] = [row for row in p["value"]["sources"] if row["path"] != engine_path]
    reseal_synthetic_evidence(p)
    with pytest.raises(ValueError, match="unbound"):
        verify(p)


@pytest.mark.parametrize("name", ["failure.json", "generation-plan.json"])
def test_production_rejects_failed_or_smoke_artifacts(synthetic_production_evidence, name):
    p = synthetic_production_evidence
    write_json(p["attempt"] / name, {"status": "failed_or_smoke"})
    with pytest.raises(ValueError):
        verify(p)


def test_production_rejects_fake_backend_without_any_runtime_probe(inputs, monkeypatch):
    value = run(inputs)
    assert value["test_only"] is True

    def never_probe(*args):
        raise AssertionError("Test-only evidence must fail before runtime/model inspection")

    monkeypatch.setattr(align, "_production_software_identity", never_probe)
    with pytest.raises(ValueError, match="test/fake/smoke"):
        align.verify_alignment_evidence(value, inputs["plan_path"], inputs["speech"])


def test_actual_runtime_boundary_is_not_replaced_by_synthetic_software(synthetic_production_evidence, monkeypatch):
    p = synthetic_production_evidence

    def real_boundary_rejects_synthetic(*args):
        raise ValueError("Real runtime identity does not match this synthetic fixture")

    monkeypatch.setattr(align, "_production_software_identity", real_boundary_rejects_synthetic)
    with pytest.raises(ValueError, match="Real runtime identity"):
        verify(p)


def test_production_rejects_copied_output_alias(synthetic_production_evidence):
    p = synthetic_production_evidence
    alias = p["output"].with_name("copied-timings.json")
    alias.write_bytes(p["output"].read_bytes())
    with pytest.raises(ValueError, match="exact create-only"):
        align.verify_production_timings(alias, plan_path=p["plan_path"], speech=p["speech"])


def test_production_rejects_wrong_expected_speech_directory(synthetic_production_evidence):
    p = synthetic_production_evidence
    with pytest.raises(ValueError):
        align.verify_production_timings(p["output"], plan_path=p["plan_path"], speech=p["speech"].parent)


def test_production_rejects_unknown_and_relative_source_paths(synthetic_production_evidence):
    p = synthetic_production_evidence
    p["value"]["sources"].append({"path": "relative-file.json", "sha256": "0" * 64})
    with pytest.raises(ValueError, match="absolute"):
        align.verify_alignment_evidence(p["value"], p["plan_path"], p["speech"])


def test_production_rejects_symlink_raw_evidence(synthetic_production_evidence):
    p = synthetic_production_evidence
    path = p["attempt"] / "U01.raw.json"
    outside = p["output"].with_name("external-raw.json")
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="nonsymlink"):
        verify(p)
