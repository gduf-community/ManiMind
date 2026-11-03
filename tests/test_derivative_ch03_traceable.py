"""Chapter-03 author native checks, not real-pixel or release approval."""

import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, validate_narration

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch03-traceable"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(ROOT / "examples/derivative_ch03_traceable.py")


@pytest.fixture(scope="module")
def native(lesson):
    import derivative_ch02_traceable as steps
    import derivative_ch03_rules as original
    import derivative_chapter_shared as shared
    import manimind.components.formula_transfer as transfer

    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            scene.motion_samples = []
            for module in (steps, original, shared, transfer):
                patcher.setattr(module, "SemanticFormula", lesson.SemanticFormula)

        with native_run(lesson, lesson.DerivativeCh03Traceable, read("plan-draft.json"), initialize) as scene:
            yield scene


def test_whole_scene_has_authored_clock_and_all_focuses(native):
    plan = read("plan-draft.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-7)
    assert not native._open_focus and not native._drivers
    assert {r["id"] for r in native._closed_focus} == {r["id"] for r in plan["focus_intents"]}


def test_all_selected_key_steps_execute_not_just_old_safe_formula(native):
    expected = {r["id"] for r in read("plan-draft.json")["formula_transitions"]}
    completed = {r["transition"] for r in native.motion_samples if r["kind"] == "traceable_complete"}
    assert expected == completed
    assert {"product_collect_areas", "product_example_first", "product_example_second", "quotient_cancel_uv",
            "quotient_square_denominator", "cost_substitute", "cost_cancel_square"} <= completed


def test_copy_origin_and_multi_source_role_assignment_are_real(native):
    rows = [r for r in native.motion_samples if r.get("transition") == "linear_divide_h" and r["kind"] == "traceable_formula"]
    assert rows[0]["moving"]["du"][1] > rows[0]["target"]["du"][1] + .5
    gathered = [r for r in native.motion_samples if r.get("transition") == "product_example_first" and r["kind"] == "traceable_gather"]
    assert len(gathered) > 30
    assert gathered[0]["roles"] == [("up", "up"), ("v", "v")]
    for left, right in zip(gathered[0]["moving"], gathered[0]["target"]):
        assert left[1] > right[1] + .5


def test_original_full_wavs_and_words_still_fit_the_new_process_focuses(native):
    plan, narration, timings = read("plan-draft.json"), read("narration.json"), read("timings.json")
    focus = {"duration": native.time, "windows": native._closed_focus}
    validate_narration(narration, visual_timeline(plan), focus)
    placed = schedule(visual_timeline(plan), narration, focus, timings)
    assert len(placed) == 9
    assert sum(r["duration_seconds"] for r in placed) == pytest.approx(sum(r["duration_seconds"] for r in timings["units"]))
    for actual, intended in zip(placed, plan["intended_full_wav_placement"], strict=True):
        assert abs(actual["start"] - intended["intended_start"]) <= .07


def test_area_shrink_and_cost_graph_are_still_original_math_states(native):
    areas = [s for s in native.motion_samples if s["kind"] == "product_area"]
    assert min(s["h"] for s in areas) == pytest.approx(.025)
    assert max(s["h"] for s in areas) == pytest.approx(.6)
    costs = [s for s in native.motion_samples if s["kind"] == "average_cost"]
    assert min(s["x"] for s in costs) == pytest.approx(1)
    assert max(s["x"] for s in costs) == pytest.approx(4)
    assert any(s["x"] == pytest.approx(2) and s["derivative"] == pytest.approx(0) for s in costs)


def test_current_selected_visual_v006_and_v431_sources_are_not_mislabelled():
    plan, contract = read("plan-draft.json"), read("contract-draft.json")
    validate_contract(contract)
    assert set(contract["assets"]) == {"selected_visual_v006"}
    assert sum(len(u["features"]) for u in contract["units"]) == 30
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19f5e-8733-71c0-ac2d-d507423acd13"
    assert "examples/derivative_ch02_traceable.py" in plan["sources"]
    assert "src/manimind/postproduce/traceable_film_v2.py" in plan["sources"]
