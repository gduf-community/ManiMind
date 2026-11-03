"""Real-Tex numerical-scope regression, not independent media approval."""

from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_intro_traceable_motion import check_clock
from test_derivative_intro_final import test_spoken_numeric_words_keep_their_actual_geometric_states as check_words
from test_derivative_intro_visual import forbid_production_project_reads


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-intro-traceable-motion/v010"


@contextmanager
def run():
    from manimind.render.manim_renderer import _render_environment
    import derivative_intro_refined as refined
    import manimind.components.formula_motion as motion
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        patcher.setenv("PATH", _render_environment()["PATH"])
        module = load_lesson(ROOT / "examples/derivative_intro_traceable_motion_v010.py")
        real_formula = refined.SemanticFormula

        def initialize(scene):
            refined.SemanticFormula = real_formula
            motion.SemanticFormula = real_formula
            patcher.setattr(module, "SemanticFormula", real_formula)
            patcher.setattr(refined.base, "SemanticFormula", real_formula)
            patcher.setattr(scene, "formula", refined.base.DerivativeIntroLesson.formula.__get__(scene))
            patcher.setattr(scene, "assemble_render_groups", lambda: None)
            patcher.setattr(scene, "remove", module.DerivativeIntroTraceableMotionLessonV010.remove.__get__(scene))
        with native_run(refined, module.DerivativeIntroTraceableMotionLessonV010,
                        json.loads((FIXTURE / "plan.json").read_text()), initialize=initialize) as scene:
            yield scene


def test_real_tex_entire_promotion_has_no_point_only_result_in_moving_actor():
    with run() as scene:
        check_clock(scene)
        check_words(scene)
        rows = scene._general_scope_events
        assert rows and rows[0]["time"] == pytest.approx(165.2)
        assert rows[-1]["time"] == pytest.approx(166.6)
        assert all(row["active_numeric_tail_count"] == 0 and "=4" not in row["active_tex"] for row in rows)
        assert all(row["source_tex"].endswith("=4") for row in rows)
        assert all(row["source_minimum_opacity"] >= .999 and row["upper_numeric_tail_minimum_opacity"] >= .999 for row in rows)
        assert all(row["source_bounds"] == pytest.approx(rows[0]["source_bounds"]) for row in rows)
        assert all(row["upper_numeric_tail_bounds"] == pytest.approx(rows[0]["upper_numeric_tail_bounds"]) for row in rows)
        moving = [row for row in rows if row["phase"] == "complete_copy_transport"]
        assert all(row["active_minimum_opacity"] >= .999 for row in moving)
        assert any(row["active_bounds"] != pytest.approx(moving[0]["active_bounds"]) for row in moving)
        retained = [row for row in scene._visibility_events if row["phase"].startswith("promotion_")]
        assert len(retained) == 2 and all(row["time"] == 182 and row["minimum_opacity"] >= .999 for row in retained)
        assert scene.symbol_transitions[-1]["numeric_result_only_in_upper_specific_formula"]


def test_plan_keeps_the_same_profile_and_seven_actions_with_dense_promotion_frames():
    plan = json.loads((FIXTURE / "plan.json").read_text())
    old = json.loads((FIXTURE.parent / "v009/plan.json").read_text())
    assert plan["workflow_profile"] == old["workflow_profile"] == "configs/visual-first-workflow-v4.3.1-unit.json"
    assert plan["scene_class"] == "DerivativeIntroTraceableMotionLessonV010"
    assert plan["duration"] == 228 and plan["focus_intents"] == old["focus_intents"]
    assert plan["narration_draft"] == old["narration_draft"]
    assert {row["id"] for row in plan["formula_transitions"]} == {row["id"] for row in old["formula_transitions"]}
    assert {round(frame/30, 3) for frame in range(4956, 4999)} <= set(plan["review_times"])
    assert "examples/derivative_intro_traceable_motion_v009.py" in plan["sources"]
    assert plan["revision_review"].endswith("content-regression-v010.json")
