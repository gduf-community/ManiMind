import copy

import pytest

from manimind.review import meaning_units as subject


@pytest.fixture
def data():
    narration = {"schema_version": 3, "units": [{"id": "U1", "cue": "demo", "text": "First, then second.",
        "references": [{"id": "R1", "focus": "first", "text": "First, "},
                       {"id": "R2", "focus": "second", "text": "then second."}]}]}
    timeline = {"duration": 10, "cues": [{"id": "demo", "start": 0, "duration": 10}]}
    focus = {"duration": 10, "windows": [{"id": "first", "start": 1, "end": 3},
                                        {"id": "second", "start": 3, "end": 5}]}
    timing = {"schema_version": 1, "method": subject.TIMING_METHOD, "timing_scope": subject.TIMING_SCOPE,
              "plan_sha256": "a" * 64, "writer": "forced aligner", "consumers": ["scheduler"],
              "lifecycle": "this attempt", "invalidation": "plan/WAV/model/text change",
              "smoke_only": False, "test_only": False, "listening_reviewed": False,
              "acceptance": "estimated_not_listening_or_publication_approved", "attempt": "/test-only/attempt",
              "plan": "/test-only/plan.json", "software": {"backend": "test-structure-not-production"},
              "sources": [{"path": "/test-only/source.py", "sha256": "c" * 64}],
              "units": [{"id": "U1", "wav_sha256": "b" * 64, "duration_seconds": 4.5,
                         "phrases": [{"id": "R1", "text": "First, ", "start": .5, "end": 2},
                                     {"id": "R2", "text": "then second.", "start": 2.5, "end": 4}]}]}
    return narration, timeline, focus, timing


def test_multiple_visual_events_share_one_intact_continuous_wav(data):
    narration, timeline, focus, timing = data
    rows = subject.schedule(timeline, narration, focus, timing)
    assert len(rows) == 1 and rows[0]["start"] == .5 and rows[0]["end"] == 5
    assert rows[0]["phrases"][1]["visual_start"] == 3
    transport = subject.transport_segments(narration)
    assert len(transport) == 1 and transport[0]["focus"] == "U1"
    assert transport[0]["focus_scope"] == "meaning_unit_not_visual_focus"
    assert transport[0]["references"] == narration["units"][0]["references"]


@pytest.mark.parametrize("mutation", ["schema", "unit_focus", "text", "reference", "duplicate_unit", "duplicate_ref", "nan_cue", "unknown_cue"])
def test_pure_contract_rejects_legacy_fake_focus_and_text_loss(data, mutation):
    narration, timeline, focus, _ = data
    row = narration["units"][0]
    if mutation == "schema": narration["schema_version"] = 2
    if mutation == "unit_focus": row["focus"] = "first"
    if mutation == "text": row["text"] = row["text"].replace(",", "")
    if mutation == "reference": row["references"][1]["focus"] = "not_measured"
    if mutation == "duplicate_unit": narration["units"].append(copy.deepcopy(row))
    if mutation == "duplicate_ref": row["references"][1]["id"] = "R1"
    if mutation == "nan_cue": timeline["cues"][0]["start"] = float("nan")
    if mutation == "unknown_cue": row["cue"] = "unknown"
    with pytest.raises(ValueError):
        subject.validate_narration(narration, timeline, focus)


@pytest.mark.parametrize("mutation", ["method", "scope", "plan", "wav", "duration", "text", "id", "missing", "overlap", "negative", "nan", "bool", "bounds", "listening", "smoke", "metadata"])
def test_forced_timing_is_bound_ordered_exact_text_not_certified_listening(data, mutation):
    narration, _, _, timing = data
    unit = timing["units"][0]
    phrase = unit["phrases"][1]
    if mutation == "method": timing["method"] = "character_ratio"
    if mutation == "scope": timing["timing_scope"] = "ASR_accuracy_certified"
    if mutation == "plan": timing["plan_sha256"] = "c" * 64
    if mutation == "wav": unit["wav_sha256"] = "c" * 64
    if mutation == "duration": unit["duration_seconds"] = 4
    if mutation == "text": phrase["text"] = "changed"
    if mutation == "id": phrase["id"] = "R1"
    if mutation == "missing": unit["phrases"].pop()
    if mutation == "overlap": phrase["start"] = 1
    if mutation == "negative": unit["phrases"][0]["start"] = -1
    if mutation == "nan": phrase["end"] = float("nan")
    if mutation == "bool": phrase["end"] = True
    if mutation == "bounds": phrase["end"] = 6
    if mutation == "listening": timing["listening_reviewed"] = True
    if mutation == "smoke": timing["smoke_only"] = True
    if mutation == "metadata": timing.pop("writer")
    with pytest.raises(ValueError):
        subject.validate_timings(timing, narration, plan_sha256="a" * 64, wav_sha256s=["b" * 64], durations=[4.5])


def test_a_large_union_window_cannot_hide_wrong_internal_phrase_timing(data):
    narration, timeline, focus, timing = data
    focus["windows"].append({"id": "whole_paragraph", "start": 0, "end": 10})
    timing["units"][0]["phrases"][1].update(start=2.01, end=4.5)
    with pytest.raises(ValueError, match="no intersection"):
        subject.schedule(timeline, narration, focus, timing)


@pytest.mark.parametrize("problem", ["cue", "wav_tail", "overlap", "sample_grid"])
def test_intersection_respects_cue_full_audio_nonoverlap_and_pcm_grid(data, problem):
    narration, timeline, focus, timing = data
    if problem == "cue": timeline["cues"][0]["duration"] = 4
    if problem == "wav_tail": timing["units"][0]["duration_seconds"] = 10
    if problem == "overlap":
        narration["units"].append({**copy.deepcopy(narration["units"][0]), "id": "U2"})
        timing["units"].append({**copy.deepcopy(timing["units"][0]), "id": "U2"})
    if problem == "sample_grid":
        focus["windows"][0].update(start=1.000001, end=2.500001)
        focus["windows"][1].update(start=3.000001, end=4.500001)
    with pytest.raises(ValueError, match="no intersection"):
        subject.schedule(timeline, narration, focus, timing)


def test_genuine_single_reference_is_not_a_fixed_pedagogical_template(data):
    narration, timeline, focus, _ = data
    row = narration["units"][0]
    row["text"] = row["references"][0]["text"]
    row["references"] = row["references"][:1]
    assert subject.validate_narration(narration, timeline, focus) == [row]


def test_actual_wav_duration_not_rounded_model_duration_bounds_the_tail(data):
    narration, timeline, focus, timing = data
    row = subject.schedule(timeline, narration, focus, timing, durations=[4.5 + 1 / 96000])[0]
    assert row["duration_seconds"] == 4.5 + 1 / 96000


def test_fractional_measured_cue_clock_accepts_renderer_rounding():
    assert subject.cue_windows({"duration": .1, "cues": [
        {"id": "a", "start": 0, "duration": 1 / 30},
        {"id": "b", "start": .033333333, "duration": 1 / 30},
        {"id": "c", "start": .066666667, "duration": 1 / 30}]}).keys() == {"a", "b", "c"}


@pytest.mark.parametrize("value", [None, [], {}, {"units": None}])
def test_malformed_timing_container_is_a_data_validation_error(data, value):
    narration, timeline, focus, _ = data
    with pytest.raises(ValueError): subject.schedule(timeline, narration, focus, value)


@pytest.mark.parametrize("field", ["sources", "software", "attempt", "plan", "smoke_only", "test_only", "listening_reviewed", "acceptance"])
def test_missing_provenance_cannot_default_to_a_real_backend(data, field):
    narration, _, _, timing = data
    timing.pop(field)
    with pytest.raises(ValueError):
        subject.validate_timings(timing, narration, plan_sha256="a" * 64, wav_sha256s=["b" * 64], durations=[4.5])


@pytest.mark.parametrize("field,value", [("sources", []), ("software", {}), ("attempt", "relative/attempt"),
    ("test_only", True), ("test_only", 0), ("smoke_only", None), ("listening_reviewed", None),
    ("sources", [{"path": "relative.py", "sha256": "a" * 64}]),
    ("sources", [{"path": "/absolute.py", "sha256": "not-a-hash"}])])
def test_empty_fake_or_ambiguous_alignment_provenance_is_rejected(data, field, value):
    narration, _, _, timing = data
    timing[field] = value
    with pytest.raises(ValueError):
        subject.validate_timings(timing, narration, plan_sha256="a" * 64, wav_sha256s=["b" * 64], durations=[4.5])
