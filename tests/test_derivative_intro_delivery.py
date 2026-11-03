"""Native layout regression over versioned fixtures, without production runtime."""

from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_intro_refined import plan


ROOT = Path(__file__).resolve().parents[1]


def test_condition_moves_outside_formula_assembly_without_changing_cue_clock():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        lesson = load_lesson(ROOT / "examples/derivative_intro_delivery.py")
        import derivative_intro_refined as refined

        def initialize(scene):
            patcher.setattr(refined.base, "SemanticFormula", refined.SemanticFormula)

        with native_run(refined, lesson.DerivativeIntroDeliveryLesson, plan(), initialize=initialize) as scene:
            relocation = [row for row in scene.motion_samples if row["kind"] == "condition_relocation"]
            assert [row["phase"] for row in relocation] == ["before", "after"]
            assert relocation[1]["time"] > relocation[0]["time"]
            assert relocation[1]["bounds"][0][0] > 3
            assert relocation[1]["bounds"][0][1] > -1.1
            assert scene.time == 338
            assert not scene._open_focus
            assert len(scene._closed_focus) == 28
            assert len(scene.visual_events) == 31
