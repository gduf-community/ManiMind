"""Exact measured-audio/native preflight, not GL or listening approval."""

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import string

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_intro_visual import forbid_production_project_reads


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-intro-voiced"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def load():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        return load_lesson(ROOT / "examples/derivative_intro_voiced.py")


@contextmanager
def run(lesson, value=None, real_tex=False):
    import derivative_intro_refined as refined
    import manimind.components.formula_motion as motion
    real_formula = refined.SemanticFormula
    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            if real_tex:
                refined.SemanticFormula = real_formula
                motion.SemanticFormula = real_formula
            patcher.setattr(refined.base, "SemanticFormula", refined.SemanticFormula)
            # Exercise this lesson's real removal hook and native recursive removal.
            # Only GL render-group assembly is disabled by this CPU test adapter.
            patcher.setattr(scene, "assemble_render_groups", lambda: None)
            patcher.setattr(scene, "remove", lesson.DerivativeIntroVoicedLesson.remove.__get__(scene))
        with native_run(refined, lesson.DerivativeIntroVoicedLesson,
                        read("plan.json") if value is None else value, initialize=initialize) as scene:
            yield scene


def placement_diagnostic(scene, narration, timings):
    from manimind.review.meaning_units import schedule
    focus = json.loads(scene.out.files["focus-events.json"])
    result = {"scope": "native estimate-based full-WAV preflight, not pixels/listening/approval", "units": []}
    try:
        result["full_placement"] = schedule(scene.timeline, narration, focus, timings)
        result["globally_feasible"] = True
    except ValueError as exc:
        result.update(globally_feasible=False, global_error=str(exc))
    for unit, measured in zip(narration["units"], timings["units"], strict=True):
        one_n = {**narration, "units": [unit]}
        one_t = {**timings, "units": [measured]}
        try:
            rows = schedule(scene.timeline, one_n, focus, one_t)
            result["units"].append({"id": unit["id"], "individually_feasible": True,
                                    "start": rows[0]["start"], "legal_start": rows[0]["legal_start"]})
        except ValueError as exc:
            result["units"].append({"id": unit["id"], "individually_feasible": False, "error": str(exc)})
    return result


@pytest.fixture(scope="module")
def lesson():
    return load()


@pytest.fixture(scope="module")
def native(lesson):
    with run(lesson) as scene:
        return scene


def test_full_original_wavs_have_a_global_native_placement(native):
    diagnostic = placement_diagnostic(native, read("narration.json"), read("measured-timings.json"))
    assert diagnostic["globally_feasible"], diagnostic
    assert all(row["individually_feasible"] for row in diagnostic["units"])
    assert len(diagnostic["full_placement"]) == 9
    assert sum(row["duration_seconds"] for row in diagnostic["full_placement"]) == pytest.approx(184.64)


def test_actual_stage_parameters_and_visibility_lifecycles(native, lesson):
    assert native.time == sum(lesson.CUE_DURATIONS) == read("plan.json")["duration"]
    assert len(native.visual_events) == 31 and len(native._closed_focus) == 28
    assert not native._deferred_visibility_ends and not native._open_focus
    windows = {row["id"]: row for row in native._closed_focus}
    for event in native._visibility_events:
        if event["phase"] == "history_removed":
            assert windows[event["focus"]]["end"] == event["time"]
        if event["phase"] == "target_fully_assembled_before_home":
            assert event["minimum_opacity"] >= .999
            if event["focus"] in {"expanded_terms", "simplified_rate"}:
                assert windows[event["focus"]]["start"] == event["time"]


def placed(native):
    return placement_diagnostic(native, read("narration.json"), read("measured-timings.json"))["full_placement"]


def word_span(rows, unit_id, ref_id, tokens):
    unit = next(row for row in rows if row["id"] == unit_id)
    phrase = next(row for row in unit["phrases"] if row["id"] == ref_id)
    words = phrase["words"]
    normalized = [word["word"].strip().strip(string.punctuation + "，。；、") for word in words]
    matches = [i for i in range(len(words) - len(tokens) + 1) if normalized[i:i + len(tokens)] == list(tokens)]
    assert len(matches) == 1, (unit_id, ref_id, tokens, normalized)
    index = matches[0]
    return unit["start"] + words[index]["start"], unit["start"] + words[index + len(tokens) - 1]["end"]


def test_spoken_approach_values_have_actual_stable_readouts(native):
    rows = placed(native)
    for tokens, expected in ((["四", "点", "一"], .1), (["四", "点", "零", "二"], .02)):
        start, end = word_span(rows, "approaching", "motion", tokens)
        samples = [row for row in native.motion_samples if row["kind"] == "approach" and start <= row["time"] <= end]
        assert samples
        assert all(row["h"] == pytest.approx(expected) and row["slope"] == pytest.approx(4 + expected)
                   for row in samples)
    first, last = (next(row for row in native._visibility_events if row["phase"] == phase)
                   for phase in ("origin_rate_record_added", "origin_rate_record_visible_at_cue_end"))
    start, end = word_span(rows, "approaching", "motion", ["五"])
    assert first["time"] < start < end < last["time"]
    assert first["presentation"] == "historical_start_value_not_current_readout"


def test_spoken_prediction_bounds_match_motion_not_character_ratios(native):
    rows = placed(native)
    start, end = word_span(rows, "use_nearby", "prediction", ["零", "点", "四"])
    samples = [row for row in native.motion_samples if row["kind"] == "prediction" and start <= row["time"] <= end]
    assert samples and all(row["h"] == pytest.approx(.4) for row in samples)
    one_start, one_end = word_span(rows, "use_nearby", "prediction", ["一"])
    samples = [row for row in native.motion_samples if row["kind"] == "prediction" and one_start <= row["time"] <= one_end]
    assert samples and all(row["h"] == pytest.approx(.1) for row in samples)
    decreasing = [row for row in native.motion_samples if row["kind"] == "prediction" and .1 < row["h"] < .4]
    assert decreasing and decreasing[0]["time"] >= end - 1 / 30


def test_limit_reason_has_real_two_sided_motion_and_signed_values(native):
    rows = placed(native)
    unit = next(row for row in rows if row["id"] == "both_directions")
    phrase = next(row for row in unit["phrases"] if row["id"] == "reason")
    samples = [row for row in native.motion_samples if row["kind"] == "two_sides"
               and phrase["visual_start"] <= row["time"] <= phrase["visual_end"]]
    assert max(row["radius"] for row in samples) - min(row["radius"] for row in samples) > .02
    assert all(row["right"] > 4 > row["left"] and row["right_dy"] > 0 > row["left_dy"] for row in samples)
    assert min(row["radius"] for row in samples) == pytest.approx(.02)


def test_nine_unchanged_units_and_every_reference_fit_the_actual_windows(native):
    rows = placed(native)
    previous = 0
    for unit, measured, draft in zip(rows, read("measured-timings.json")["units"], read("narration.json")["units"], strict=True):
        assert unit["id"] == measured["id"] == draft["id"]
        assert unit["text"] == draft["text"] and unit["references"] == draft["references"]
        assert unit["duration_seconds"] == measured["duration_seconds"]
        assert unit["end"] - unit["start"] == pytest.approx(measured["duration_seconds"])
        assert unit["start"] >= previous
        for phrase in unit["phrases"]:
            assert phrase["focus_start"] - 1e-10 <= phrase["visual_start"] <= phrase["visual_end"] <= phrase["focus_end"] + 1e-10
        previous = unit["end"]


def test_real_tex_has_full_opacity_and_feasible_native_schedule(lesson, monkeypatch):
    from manimind.render.manim_renderer import _render_environment
    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    with run(lesson, real_tex=True) as scene:
        diagnostic = placement_diagnostic(scene, read("narration.json"), read("measured-timings.json"))
        assert diagnostic["globally_feasible"], diagnostic
        assert len(scene.symbol_transitions) == 5
        complete = [row for row in scene._visibility_events if row["phase"] == "target_fully_assembled_before_home"]
        assert len(complete) == 5
        assert all(row["minimum_opacity"] >= .999 and row["bounds"][0][1] > -3.05 for row in complete)
