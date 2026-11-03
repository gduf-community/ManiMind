"""v008 source-origin native and real-Tex preflight, never review approval."""

from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_intro_voiced import placement_diagnostic
from test_derivative_intro_visual import forbid_production_project_reads


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-intro-traceable-motion"
ACTIONS = {"average_ratio", "average_substitution", "expanded", "combined", "factored",
           "simplified", "general_position"}


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def load():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        return load_lesson(ROOT / "examples/derivative_intro_traceable_motion.py")


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
            patcher.setattr(lesson, "SemanticFormula", refined.SemanticFormula)
            patcher.setattr(refined.base, "SemanticFormula", refined.SemanticFormula)
            patcher.setattr(scene, "assemble_render_groups", lambda: None)
            patcher.setattr(scene, "remove", lesson.DerivativeIntroTraceableMotionLesson.remove.__get__(scene))
        with native_run(refined, lesson.DerivativeIntroTraceableMotionLesson, read("plan.json"),
                        initialize=initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def lesson():
    return load()


@pytest.fixture(scope="module")
def native(lesson):
    with run(lesson) as scene:
        return scene


def check_clock(scene):
    diagnostic = placement_diagnostic(scene, read("narration.json"), read("measured-timings.json"))
    assert diagnostic["globally_feasible"], diagnostic
    assert len(diagnostic["full_placement"]) == 9
    assert sum(row["duration_seconds"] for row in diagnostic["full_placement"]) == pytest.approx(184.64)
    assert sum(len(row["phrases"]) for row in diagnostic["full_placement"]) == 28
    assert all(row["individually_feasible"] for row in diagnostic["units"])
    assert scene.time == 228 and scene.frame == 6840
    assert len(scene._closed_focus) == 28 and len(scene.visual_events) == 31
    assert not scene._open_focus and not scene._chain_deferred_ends
    assert not scene._deferred_visibility_ends and not scene._early_state_windows
    return diagnostic


def test_full_original_audio_clock_and_focuses(native):
    check_clock(native)


def test_original_numeric_words_still_match_actual_stable_geometry(native):
    from test_derivative_intro_final import test_spoken_numeric_words_keep_their_actual_geometric_states
    test_spoken_numeric_words_keep_their_actual_geometric_states(native)


def test_copies_are_visible_at_the_true_source_before_any_motion(native):
    events = native._transfer_events
    assert {row["action"] for row in events} == ACTIONS
    keys = {(row["action"], row["role"], row["start"]) for row in events}
    for key in keys:
        rows = [row for row in events if (row["action"], row["role"], row["start"]) == key]
        assert rows[0]["time"] == rows[0]["start"]
        assert rows[0]["moving_bounds"] == pytest.approx(rows[0]["origin_bounds"])
        assert rows[-1]["moving_bounds"] == pytest.approx(rows[-1]["destination_bounds"])
        assert rows[0]["origin_bounds"] != pytest.approx(rows[0]["destination_bounds"])
        assert all(row["source_bounds"] == pytest.approx(rows[0]["origin_bounds"]) for row in rows)
        assert all(row["moving_minimum_opacity"] >= .999 and row["source_minimum_opacity"] >= .999 for row in rows)
        assert any(row["moving_bounds"] != pytest.approx(rows[0]["origin_bounds"])
                   and row["moving_bounds"] != pytest.approx(rows[-1]["destination_bounds"]) for row in rows[1:-1])


def test_one_transfer_at_a_time_and_no_false_expansion_power_identity(native):
    starts = {}
    for row in native._transfer_events:
        starts.setdefault((row["action"], row["role"], row["start"]), row)
    for action in ACTIONS:
        rows = sorted((row for row in starts.values() if row["action"] == action), key=lambda row: row["start"])
        assert all(a["finish"] <= b["start"] + 1/30 for a, b in zip(rows, rows[1:]))
    expanded = [row for row in starts.values() if row["action"] == "expanded"]
    assert {row["role"] for row in expanded} == {"h_den", "h_primary", "sub_four"}
    assert [row["role"] for row in starts.values() if row["action"] == "factored"] == [
        "h_den", "h_primary", "coefficient", "h_extra"]


def test_preserves_complete_history_general_comparison_and_original_anchors(native):
    completed = [row for row in native._visibility_events if row["phase"] == "chain_row_completed"]
    assert len(completed) == 6
    assert all(row["minimum_opacity"] >= .999 for row in completed)
    assert all(row["status"] == "closed" for row in native._formula_window_states.values())
    assert len(native.symbol_transitions) == 5
    assert all(row["source_retained"] for row in native.symbol_transitions)
    ready = {row["id"]: row["time"] for row in native.visual_events}
    assert ready["increments_ready"] == 21.5
    assert ready["average_quotient_ready"] == 26.2
    assert ready["expanded_ready"] == 72.9 and ready["definition_pattern_ready"] == 167.1
    retained = [row for row in native._visibility_events if row["phase"].startswith("promotion_")]
    assert len(retained) == 2 and all(row["time"] == 182 for row in retained)


def test_current_baseline_v43_gate_action_selection_and_immutable_original_text():
    plan, contract = read("plan.json"), read("contract.json")
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v4.3-unit.json"
    assert plan["scene_class"] == "DerivativeIntroTraceableMotionLesson"
    assert {row["id"] for row in plan["formula_transitions"]} == ACTIONS
    assert {"docs/formula-motion.md", "docs/formula-continuity.md",
            "src/manimind/postproduce/traceable_film.py"} <= set(plan["sources"])
    assert "examples/derivative_intro_clean_motion.py" not in plan["sources"]
    assert set(contract["assets"]) == {"intro_v007"}
    assert contract["assets"]["intro_v007"]["duration"] == 228
    assert contract["assets"]["intro_v007"]["path"].startswith("outputs/math-derivative-intro-20261101/visual-v007/")
    assert len(contract["units"]) == 9 and sum(len(row["features"]) for row in contract["units"]) == 14
    assert plan["author_context"] != "019eaf8b-9151-75e2-9db4-5ff834335577"
    original = json.loads((ROOT / "tests/fixtures/derivative-intro-voiced/narration.json").read_text())
    assert read("narration.json") == original


def test_real_tex_native_source_origins_complete_rows_and_full_wav_schedule(lesson, monkeypatch):
    from manimind.render.manim_renderer import _render_environment
    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    with run(lesson, real_tex=True) as scene:
        check_clock(scene)
        test_copies_are_visible_at_the_true_source_before_any_motion(scene)
        test_one_transfer_at_a_time_and_no_false_expansion_power_identity(scene)
        test_preserves_complete_history_general_comparison_and_original_anchors(scene)
        test_original_numeric_words_still_match_actual_stable_geometry(scene)
        for row in scene._visibility_events:
            if row["phase"] == "chain_row_completed":
                assert row["bounds"][0][1] > -3.05


@contextmanager
def run_v009():
    from manimind.render.manim_renderer import _render_environment
    import derivative_intro_refined as refined
    import manimind.components.formula_motion as motion
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        patcher.setenv("PATH", _render_environment()["PATH"])
        module = load_lesson(ROOT / "examples/derivative_intro_traceable_motion_v009.py")
        real_formula = refined.SemanticFormula

        def initialize(scene):
            refined.SemanticFormula = real_formula
            motion.SemanticFormula = real_formula
            patcher.setattr(module, "SemanticFormula", real_formula)
            patcher.setattr(refined.base, "SemanticFormula", real_formula)
            patcher.setattr(scene, "formula", refined.base.DerivativeIntroLesson.formula.__get__(scene))
            patcher.setattr(scene, "assemble_render_groups", lambda: None)
            patcher.setattr(scene, "remove", module.DerivativeIntroTraceableMotionLessonV009.remove.__get__(scene))
        plan = json.loads((FIXTURE / "v009/plan.json").read_text())
        with native_run(refined, module.DerivativeIntroTraceableMotionLessonV009, plan,
                        initialize=initialize) as scene:
            yield scene


def test_v009_real_tex_complete_source_copy_clock_and_structured_rewrite():
    with run_v009() as scene:
        check_clock(scene)
        test_original_numeric_words_still_match_actual_stable_geometry(scene)
        test_preserves_complete_history_general_comparison_and_original_anchors(scene)
        stages = {"expanded", "combined", "factored", "simplified", "general_position"}
        assert {row["stage"] for row in scene._structured_copy_events} == stages
        before = {row["stage"]: row for row in scene._chain_events if row["phase"] == "before"}
        for stage in stages:
            rows = [row for row in scene._structured_copy_events if row["stage"] == stage]
            transport = [row for row in rows if row["phase"] == "complete_copy_transport"]
            assert transport[0]["active_bounds"] == pytest.approx(before[stage]["source_bounds"])
            assert all(row["active_tex"] == row["source_tex"] for row in transport)
            assert all(row["active_minimum_opacity"] >= .999 for row in transport)
            assert all(row["source_minimum_opacity"] >= .999 for row in rows)
            assert any(row["active_bounds"] != pytest.approx(transport[0]["active_bounds"]) for row in transport)
            assert any(row["phase"] == "structured_local_rewrite" for row in rows)
        reveals = {row["part"]: row["time"] for row in scene._average_reveals}
        assert reveals["symbolic_ratio_scaffold"] == 23.2
        assert reveals["substitution_scaffold"] == 24.7
        assert reveals["numeric_result_after_complete_substitution"] == 26.2


def test_v009_fixture_binds_new_scene_v2_and_preserves_v008_inputs():
    plan = json.loads((FIXTURE / "v009/plan.json").read_text())
    assert plan["scene"] == "examples/derivative_intro_traceable_motion_v009.py"
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v4.3.1-unit.json"
    assert {"examples/derivative_intro_traceable_motion.py", "docs/formula-continuity-v2.md",
            "src/manimind/postproduce/traceable_film.py", "src/manimind/postproduce/traceable_film_v2.py"} <= set(plan["sources"])
    assert plan["revision_review"].endswith("/review/content-regression-v009.json")
    assert read("plan.json")["scene"] == "examples/derivative_intro_traceable_motion.py"
