"""New module candidate checks; frozen v009 tests and files stay unchanged."""

import hashlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, validate_narration

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch03-traceable-v010"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch03_traceable_v010.py")
        import derivative_ch02_traceable as steps
        import derivative_ch03_traceable as previous
        import derivative_ch03_rules as original
        import derivative_chapter_shared as shared

        def initialize(scene):
            scene.motion_samples = []
            for owner in (steps, previous, original, shared):
                patcher.setattr(owner, "SemanticFormula", module.SemanticFormula, raising=False)

        with native_run(module, module.DerivativeCh03TraceableV010, read("plan-draft.json"), initialize) as scene:
            yield scene


def test_complete_authored_clock_and_all_24_steps(native):
    plan = read("plan-draft.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-7)
    assert not native._open_focus and not native._drivers
    assert {row["id"] for row in plan["formula_transitions"]} == {
        row["transition"] for row in native.motion_samples if row["kind"] == "traceable_complete"}


def test_original_full_voice_schedule_and_full_math_content(native):
    plan = read("plan-draft.json")
    focus = {"duration": native.time, "windows": native._closed_focus}
    validate_narration(read("narration.json"), visual_timeline(plan), focus)
    actual = schedule(visual_timeline(plan), read("narration.json"), focus, read("timings.json"))
    assert len(actual) == 9
    for placed, intended in zip(actual, plan["intended_full_wav_placement"], strict=True):
        assert abs(placed["start"] - intended["intended_start"]) <= .07
    contract = read("contract-draft.json")
    validate_contract(contract)
    assert sum(len(row["features"]) for row in contract["units"]) == 30


def test_gather_routes_have_more_time_and_denominator_first(native):
    rows = [r for r in native.motion_samples if r["kind"] == "traceable_gather"]
    for identity, minimum in (("product_collect_areas", 7), ("quotient_cross_multiply", 9)):
        selected = [r for r in rows if r["transition"] == identity]
        assert selected[-1]["time"] - selected[0]["time"] >= minimum
    common = [r for r in rows if r["transition"] == "quotient_cross_multiply" and r["active_role"]]
    assert common[0]["active_role"] in {"old_v_bottom", "new_v_bottom"}
    cost = [r for r in rows if r["transition"] == "cost_substitute" and r["active_role"]]
    assert cost[0]["active_role"] == "bottom_den"


def test_cost_working_row_is_consumed_not_repeatedly_overlaid(native):
    rows = [r for r in native.motion_samples if r.get("transition") == "cost_expand_numerator"
            and r["kind"] == "traceable_formula"]
    assert rows and all(row["retained"] is False for row in rows)
    costs = [s for s in native.motion_samples if s["kind"] == "average_cost"]
    assert min(row["x"] for row in costs) == pytest.approx(1)
    assert max(row["x"] for row in costs) == pytest.approx(4)
    assert any(row["x"] == pytest.approx(2) and row["derivative"] == pytest.approx(0) for row in costs)


def test_frozen_consumers_and_versioned_source_manifest_stay_unchanged():
    record = json.loads((ROOT / "outputs/math-derivative-ch03-rules-20261102/visual-v009/render.json").read_text())
    for name in ("examples/derivative_ch02_traceable.py", "examples/derivative_ch03_traceable.py"):
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == record["input_hashes"][str(ROOT / name)]
    plan = read("plan-draft.json")
    assert plan["scene"].endswith("derivative_ch03_traceable_v010.py")
    assert "examples/derivative_ch03_traceable.py" in plan["sources"]
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
