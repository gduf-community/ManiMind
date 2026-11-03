"""v005 native/real-Tex checks; no GL, listening or independent approval."""

from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_intro_voiced import placement_diagnostic, word_span
from test_derivative_intro_visual import forbid_production_project_reads


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-intro-final"
VOICE_FIXTURE = ROOT / "tests/fixtures/derivative-intro-voiced"


def read(name):
    directory = FIXTURE if name in {"plan.json", "design.json"} else VOICE_FIXTURE
    return json.loads((directory / name).read_text(encoding="utf-8"))


def load():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        return load_lesson(ROOT / "examples/derivative_intro_final.py")


@contextmanager
def run(lesson, real_tex=False):
    import derivative_intro_refined as refined
    import manimind.components.formula_motion as motion
    real_formula = refined.SemanticFormula
    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            if real_tex:
                refined.SemanticFormula = real_formula
                motion.SemanticFormula = real_formula
                patcher.setattr(scene, "formula", refined.base.DerivativeIntroLesson.formula.__get__(scene))
            patcher.setattr(refined.base, "SemanticFormula", refined.SemanticFormula)
            patcher.setattr(scene, "assemble_render_groups", lambda: None)
            patcher.setattr(scene, "remove", lesson.DerivativeIntroFinalLesson.remove.__get__(scene))
        with native_run(refined, lesson.DerivativeIntroFinalLesson, read("plan.json"),
                        initialize=initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def lesson():
    return load()


@pytest.fixture(scope="module")
def native(lesson):
    with run(lesson) as scene:
        return scene


def test_full_original_wavs_and_28_references_fit(native):
    diagnostic = placement_diagnostic(native, read("narration.json"), read("measured-timings.json"))
    assert diagnostic["globally_feasible"], diagnostic
    assert len(diagnostic["full_placement"]) == 9
    assert all(row["individually_feasible"] for row in diagnostic["units"])
    assert sum(row["duration_seconds"] for row in diagnostic["full_placement"]) == pytest.approx(184.64)
    previous = 0
    for row in diagnostic["full_placement"]:
        assert row["start"] >= previous
        for ref in row["phrases"]:
            assert ref["focus_start"] - 1e-10 <= ref["visual_start"] <= ref["visual_end"] <= ref["focus_end"] + 1e-10
        previous = row["end"]
    assert sum(len(row["phrases"]) for row in diagnostic["full_placement"]) == 28


def test_algebra_rows_stay_fixed_and_each_old_equation_stays_opaque(native):
    assert len(native.symbol_transitions) == 5
    for stage in ("expanded", "combined", "factored", "simplified"):
        rows = [row for row in native._chain_events if row.get("stage") == stage]
        before = next(row for row in rows if row["phase"] == "before")
        after = next(row for row in rows if row["phase"] == "after")
        during = [row for row in rows if row["phase"] == "during"]
        assert during and before["time"] < after["time"]
        assert all(row["source_bounds"] == pytest.approx(before["source_bounds"]) for row in during)
        assert after["source_bounds"] == pytest.approx(before["source_bounds"])
        assert all(row["source_minimum_opacity"] >= .999 for row in during)
        assert after["minimum_opacity"] >= .999
        assert after["target_bounds"][3] < before["source_bounds"][2]
        assert any(row["target_syntax_opacity"] > .05 for row in during[:-1])
    assert len(native._chain_rows) == 6


def test_actual_removal_closes_retained_states_and_all_lifecycles(native):
    assert native.time == read("plan.json")["duration"] == 228
    assert len(native.visual_events) == 31 and len(native._closed_focus) == 28
    assert not native._chain_deferred_ends and not native._deferred_visibility_ends and not native._open_focus
    windows = {row["id"]: row for row in native._closed_focus}
    for row in native._visibility_events:
        if row["phase"] == "history_removed":
            assert windows[row["focus"]]["end"] == row["time"]
    for identity in ("quotient_substitution", "expanded_terms", "combined_terms", "factored_h", "nonzero_cancel"):
        assert windows[identity]["end"] == 105
    assert all(row["status"] == "closed" for row in native._formula_window_states.values())


def test_general_position_starts_with_complete_copy_and_retains_both_structures(native):
    copy = next(row for row in native._visibility_events if row["phase"] == "complete_specific_copy_before_promotion")
    assert copy["minimum_opacity"] >= .999 and "f'(2)" in copy["latex"]
    rows = [row for row in native._chain_events if row.get("stage") == "general_position"]
    before = next(row for row in rows if row["phase"] == "before")
    after = next(row for row in rows if row["phase"] == "after")
    assert before["time"] < copy["time"] < after["time"]
    assert all(row["source_bounds"] == pytest.approx(before["source_bounds"])
               for row in rows if "source_bounds" in row)
    assert after["target_bounds"][3] < before["source_bounds"][2]
    assert native.symbol_transitions[-1]["strategy"] == "complete_copy_in_place_promotion"
    source = next(row for row in native._formula_window_events
                  if row["focus"] == "definition_pattern" and row["phase"] == "ready_marked")
    window = next(row for row in native._closed_focus if row["id"] == "definition_pattern")
    assert source["time"] < window["end"] == 182
    retained = [r for r in native._visibility_events if r["phase"].startswith("promotion_")]
    assert len(retained) == 2 and all(r["time"] == 182 and r["minimum_opacity"] >= .999 for r in retained)
    placed = placement_diagnostic(native, read("narration.json"), read("measured-timings.json"))["full_placement"]
    _, a_end = word_span(placed, "name_derivative", "pattern", ["成", "a"])
    assert after["time"] <= a_end + 1e-10


def test_spoken_numeric_words_keep_their_actual_geometric_states(native):
    placed = placement_diagnostic(native, read("narration.json"), read("measured-timings.json"))["full_placement"]
    for tokens, h in ((["四", "点", "一"], .1), (["四", "点", "零", "二"], .02)):
        start, end = word_span(placed, "approaching", "motion", tokens)
        rows = [r for r in native.motion_samples if r["kind"] == "approach" and start <= r["time"] <= end]
        assert rows and all(r["h"] == pytest.approx(h) and r["slope"] == pytest.approx(4+h) for r in rows)
    for tokens, h in ((["零", "点", "四"], .4), (["一"], .1)):
        start, end = word_span(placed, "use_nearby", "prediction", tokens)
        rows = [r for r in native.motion_samples if r["kind"] == "prediction" and start <= r["time"] <= end]
        assert rows and all(r["h"] == pytest.approx(h) for r in rows)


def test_fixture_contract_keeps_v003_baseline_and_original_measured_inputs(lesson):
    plan, design = read("plan.json"), read("design.json")
    assert plan["revision_mode"] == "revision" and plan["narration_draft"].endswith("narration-draft-v003.json")
    assert len(design["units"]) == 9 and sum(len(row["features"]) for row in design["units"]) == 14
    assert design["assets"]["intro_v003"]["sha256"] == "61637ddbb0141d2cbd83c944d5238fc6671a2b39892f807053fa0e157df812fe"
    assert design["timing"]["voice_plan_sha256"] == lesson.VOICE_PLAN_SHA256
    assert design["timing"]["timings_sha256"] == lesson.TIMINGS_SHA256
    assert "examples/derivative_intro_voiced.py" in plan["sources"]
    from derivative_intro_audio_aligned import validate_reference_bindings
    assert len(validate_reference_bindings(read("narration.json"))) == 5


def test_real_tex_row_separation_opacity_and_global_original_audio(lesson, monkeypatch):
    from manimind.render.manim_renderer import _render_environment
    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    with run(lesson, real_tex=True) as scene:
        diagnostic = placement_diagnostic(scene, read("narration.json"), read("measured-timings.json"))
        assert diagnostic["globally_feasible"], diagnostic
        complete = [row for row in scene._visibility_events if row["phase"] == "chain_row_completed"]
        assert len(complete) == 6
        assert all(row["minimum_opacity"] >= .999 and row["bounds"][0][1] > -3.05 for row in complete)
        for row in scene._chain_events:
            if row["phase"] == "after":
                assert row["target_bounds"][3] < row["source_bounds"][2]
        algebra = [row for row in complete if row["focus"] != "definition_pattern"]
        assert all(row["bounds"][2][1] < 3.05 and row["bounds"][2][0] < 6.9 for row in algebra)


def test_closed_windows_cannot_be_ended_or_marked_ready_twice(native):
    with pytest.raises(ValueError):
        native.focus_end("expanded_terms")
    with pytest.raises(ValueError):
        native.mark("expanded_ready")
