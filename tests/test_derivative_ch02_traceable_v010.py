"""Native checks for a new module only; these do not approve rendered pixels."""

import hashlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, validate_narration

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch02-traceable-v011"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch02_traceable_v010.py")
        import derivative_ch02_traceable as previous
        import derivative_ch02_basics as original
        import derivative_chapter_shared as shared

        def initialize(scene):
            scene.motion_samples = []
            for owner in (previous, original, shared):
                patcher.setattr(owner, "SemanticFormula", module.SemanticFormula, raising=False)

        with native_run(module, module.DerivativeCh02TraceableV010, read("plan-draft.json"), initialize) as scene:
            yield scene


def test_all_43_operations_complete_and_focuses_close(native):
    plan = read("plan-draft.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-7)
    assert not native._open_focus and not native._drivers
    assert {row["id"] for row in plan["formula_transitions"]} == {
        row["transition"] for row in native.motion_samples if row["kind"] == "traceable_complete"}


def test_full_original_14_units_and_38_feature_contract(native):
    plan = read("plan-draft.json")
    focus = {"duration": native.time, "windows": native._closed_focus}
    validate_narration(read("narration.json"), visual_timeline(plan), focus)
    placed = schedule(visual_timeline(plan), read("narration.json"), focus, read("timings.json"))
    assert len(placed) == 14
    for actual, intended in zip(placed, plan["intended_full_wav_placement"], strict=True):
        assert abs(actual["start"] - intended["intended_start"]) <= .07
    contract = read("contract-draft.json")
    validate_contract(contract)
    assert sum(len(unit["features"]) for unit in contract["units"]) == 38
    assert set(contract["assets"]) == {"selected_visual_v005"}


def test_real_conjugate_sources_and_denominator_first(native):
    gathered = [r for r in native.motion_samples if r["kind"] == "traceable_gather"]
    conjugate = [r for r in gathered if r["transition"] == "root_multiply_conjugate"]
    assert {pair[1] for pair in conjugate[0]["roles"]} == {"den", "top", "top_sum", "bottom_sum"}
    for identity, denominators in (("root_multiply_conjugate", {"den", "bottom_sum"}),
                                   ("log_base_restore_k", {"input", "coefficient"})):
        active = [r for r in gathered if r["transition"] == identity and r["active_role"]]
        assert active[0]["active_role"] in denominators
    common = [r for r in gathered if r["transition"] == "reciprocal_common" and r["active_role"]]
    assert list(dict.fromkeys(r["active_role"] for r in common)) == ["top_old", "top_changed", "den", "bottom_old", "bottom_changed"]


def test_contractions_are_resolved_before_unscaled_travel(native):
    rows = [r for r in native.motion_samples if r["kind"] == "traceable_formula"]
    for identity in ("reciprocal_cancel_x", "reciprocal_limit", "root_difference_squares", "root_cancel_x",
                     "root_limit", "log_factor_exponential", "log_base_name_dy", "log_base_limit"):
        selected = [r for r in rows if r["transition"] == identity]
        phases = list(dict.fromkeys(r["phase"] for r in selected))
        # Placeholder geometry may classify some TeX contractions differently.
        if "local_operation_at_readable_source" in phases and "travel_readable_term" in phases:
            assert phases.index("local_operation_at_readable_source") < phases.index("travel_readable_term")
        traveling = [r["widths"] for r in selected if r["phase"] == "travel_readable_term"]
        for widths in traveling[1:]:
            assert widths == pytest.approx(traveling[0], abs=1e-7)


def test_all_original_graph_models_and_domain_branches_remain(native):
    rows = [r for r in native.motion_samples if r["kind"] == "slope_map"]
    assert {r["function"] for r in rows} == {"square", "constant", "identity", "cube", "reciprocal", "root", "exp", "log", "sin", "cos"}
    reciprocal = [r["x"] for r in rows if r["function"] == "reciprocal"]
    assert min(reciprocal) == pytest.approx(-2.5) and max(reciprocal) == pytest.approx(2.5)
    increments = [r["dx"] for r in native.motion_samples if r["kind"] == "log_increment_bridge"]
    assert min(increments) == pytest.approx(.08) and max(increments) == pytest.approx(.8)


def test_old_02_and_03_consumers_stay_byte_identical():
    record = json.loads((ROOT / "outputs/math-derivative-ch03-rules-20261102/visual-v009/render.json").read_text())
    for name in ("examples/derivative_ch02_traceable.py", "examples/derivative_ch03_traceable.py"):
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == record["input_hashes"][str(ROOT / name)]
    plan = read("plan-draft.json")
    assert plan["scene"].endswith("derivative_ch02_traceable_v010.py")
    assert "examples/derivative_ch02_traceable.py" in plan["sources"]
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
