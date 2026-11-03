"""The two-term equality must not exist while its second term is missing."""

import hashlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, validate_narration

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch03-traceable-v011"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch03_traceable_v011.py")
        import derivative_ch02_traceable as steps
        import derivative_ch03_traceable as previous
        import derivative_ch03_traceable_v010 as prior
        import derivative_ch03_rules as original
        import derivative_chapter_shared as shared

        def initialize(scene):
            scene.motion_samples = []
            for owner in (steps, previous, prior, original, shared):
                patcher.setattr(owner, "SemanticFormula", module.SemanticFormula, raising=False)

        with native_run(module, module.DerivativeCh03TraceableV011, read("plan-draft.json"), initialize) as scene:
            yield scene


def test_full_clock_and_25_operations(native):
    plan = read("plan-draft.json")
    assert native.time == pytest.approx(plan["duration"])
    assert not native._open_focus and not native._drivers
    assert {r["id"] for r in plan["formula_transitions"]} == {
        r["transition"] for r in native.motion_samples if r["kind"] == "traceable_complete"}


def test_no_premature_derivative_equation_in_partial_contributions(native):
    rows = {r["transition"]: r for r in native.motion_samples if r["kind"] == "traceable_complete"}
    assert rows["product_example_first"]["target_tex"] == r"2x\sin x"
    assert rows["product_example_second"]["target_tex"] == r"x^2\cos x"
    assert rows["product_example_join_sum"]["target_tex"] == r"f'(x)=2x\sin x+x^2\cos x"
    joined = [r for r in native.motion_samples if r.get("transition") == "product_example_join_sum"
              and r["kind"] == "traceable_gather"]
    assert min(r["time"] for r in joined) > rows["product_example_second"]["time"]
    assert min(r["time"] for r in joined if r["phase"] == "new_syntax") > max(
        r["time"] for r in joined if r["phase"] == "travel_readable_term")
    assert {r["active_role"] for r in joined} >= {"left", "right"}


def test_all_original_full_units_and_content_contract(native):
    plan = read("plan-draft.json")
    focus = {"duration": native.time, "windows": native._closed_focus}
    validate_narration(read("narration.json"), visual_timeline(plan), focus)
    actual = schedule(visual_timeline(plan), read("narration.json"), focus, read("timings.json"))
    assert len(actual) == 9
    for placed, intended in zip(actual, plan["intended_full_wav_placement"], strict=True):
        assert abs(placed["start"]-intended["intended_start"]) <= .07
    contract = read("contract-draft.json")
    validate_contract(contract)
    assert sum(len(u["features"]) for u in contract["units"]) == 30


def test_all_rendered_parents_remain_frozen():
    record = json.loads((ROOT / "outputs/math-derivative-ch03-rules-20261102/visual-v010/render.json").read_text())
    for name in ("examples/derivative_ch02_traceable.py", "examples/derivative_ch03_traceable.py", "examples/derivative_ch03_traceable_v010.py"):
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == record["input_hashes"][str(ROOT / name)]
    plan = read("plan-draft.json")
    assert "examples/derivative_ch03_traceable_v010.py" in plan["sources"]
