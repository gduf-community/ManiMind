"""Serial scalar visibility and unchanged native scene/audio contracts."""

import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch04-traceable-v011"


def read(name):
    return json.loads((FIXTURE / name).read_text())


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "examples"))
        module = load_lesson(ROOT / "examples/derivative_ch04_traceable_v011.py")
        import derivative_ch04_chain as base
        import manimind.components.formula_motion as motion
        def initialize(scene):
            patch.setattr(base, "SemanticFormula", motion.SemanticFormula)
        with native_run(module, module.DerivativeChainTraceableV011, read("plan.json"), initialize) as scene:
            yield scene


def test_original_complete_wav_and_cue_clock(native):
    plan = read("plan.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-6)
    rows = schedule(visual_timeline(plan), read("narration.json"),
        {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))
    assert len(rows) == 8 and sum(len(r["references"]) for r in rows) == 26
    for got, old in zip(rows, plan["intended_full_wav_placement"], strict=True):
        assert got["start"] == pytest.approx(old["intended_start"], abs=.04)
        assert got["duration_seconds"] == old["duration_seconds"]


def test_twelve_never_overlaps_old_constant_factors(native):
    rows = [r for r in native.motion_samples if r["kind"] == "collection_scalar_visibility"]
    assert len(rows) > 40
    assert any(r["old"] > .9 and r["new"] < .01 for r in rows)
    assert any(r["new"] > .9 and r["old"] < .01 for r in rows)
    assert not any(r["old"] > .001 and r["new"] > .001 for r in rows)


def test_fixed_inner_factor_and_lhs_through_final_cleanup(native):
    rows = [r for r in native.motion_samples if r["kind"] == "collection_fixed_geometry"]
    final = next(r for r in native.motion_samples if r["kind"] == "collection_constants_finalize")
    assert len({r["factor"] for r in rows}) == len({r["lhs"] for r in rows}) == 1
    assert final["factor"] == rows[0]["factor"] and final["lhs"] == rows[0]["lhs"]
    assert rows[-1]["time"] > 296.2


def test_contract_and_result_introduction_are_sampled():
    validate_contract(read("contract.json"))
    plan = read("plan.json")
    assert {295.9, 296.0, 296.067, 296.1, 296.2, 296.3, 296.4, 296.5, 296.7}.issubset(plan["review_times"])
    assert any(r["id"] == "collect_result_introduction" for r in plan["substage_review_times"])
