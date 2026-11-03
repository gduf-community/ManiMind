"""CH05 fixture-only native checks; no pixels, listening or approval."""
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from lesson_native_harness import load_lesson,native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule
from manimind.postproduce.traceable_film import validate_selection

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"tests/fixtures/derivative-ch05-traceable"


def read(name):
    return json.loads((FIX/name).read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original=Path.open
    def guarded(path,*args,**kwargs):
        if any(path.resolve().is_relative_to(ROOT/name) for name in ("runtime","outputs")):
            raise AssertionError("Fixture-only native tests")
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,"open",guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as p:
        p.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(ROOT/"examples/derivative_ch05_traceable.py")


@pytest.fixture(scope="module")
def native(lesson):
    with pytest.MonkeyPatch.context() as p:
        def init(scene):
            p.setattr(sys.modules["derivative_ch05_monotonicity"],"SemanticFormula",lesson.SemanticFormula)
        with native_run(lesson,lesson.DerivativeCh05Traceable,read("plan.json"),init) as scene:
            yield scene


def test_only_two_methods_and_local_role_helpers(lesson):
    prior=sys.modules["derivative_ch05_monotonicity_v004"].DerivativeMonotonicityLessonV004
    for key in ("construct","beat","plots","opening","same_x","sweep","zero_point","disconnected_domain","branch_motion","handoff"):
        assert getattr(lesson.DerivativeCh05Traceable,key) is getattr(prior,key)
    plan,old=read("plan.json"),read("baseline-plan.json")
    assert plan["duration"]==old["duration"]
    assert plan["intended_full_wav_placement"]==old["intended_full_wav_placement"]
    assert all(a==b for a,b in zip(plan["cues"],old["cues"]) if a["id"] not in ("signs","interval"))


def test_actual_native_schedule_keeps_complete_original_units(native):
    assert read("narration.json")["units"]==read("baseline-narration.json")["units"]
    plan=read("plan.json")
    placed=schedule(visual_timeline(plan),read("narration.json"),
        {"duration":native.time,"windows":native._closed_focus},read("timings.json"))
    assert native.time==pytest.approx(371.3)
    assert len(placed)==8 and not native._open_focus
    assert sum(r["duration_seconds"] for r in placed)==pytest.approx(343.2)
    for row,old in zip(placed,plan["intended_full_wav_placement"],strict=True):
        assert abs(row["start"]-old["intended_start"])<.04
    assert sum(len(r["references"]) for r in placed)==sum(len(r["references"]) for r in read("narration.json")["units"])


@pytest.mark.parametrize("stage",["negative_factor_to_zero","positive_factor_to_zero","negative_root_to_boundary",
    "positive_root_to_boundary","left_sign_factors","middle_sign_factors","right_sign_factors",
    "witness_to_fb","witness_to_fa","witness_to_b","witness_to_a","witness_to_dc",
    "difference_to_product","slope_to_product","positive_delta_to_product","positive_product_to_difference",
    "difference_to_left_value","difference_to_right_value"])
def test_real_sources_intermediate_motion_and_destinations(native,stage):
    rows=[r for r in native.motion_samples if r["kind"]=="traceable_roles" and r["stage"]==stage]
    assert len(rows)>20 and rows[-1]["time"]-rows[0]["time"]>=.75
    np.testing.assert_allclose(rows[-1]["moving"],rows[-1]["targets"],atol=1e-5)
    assert any(np.linalg.norm(np.array(a)-b)>.15 for a,b in zip(rows[0]["moving"],rows[0]["targets"]))


def test_original_scientific_motions_and_domain_exception(native):
    linked=[r for r in native.motion_samples if r["kind"]=="linked_graphs"]
    assert linked and all(r["curve_point"][0]==pytest.approx(r["derivative_point"][0]) for r in linked)
    branches=[r for r in native.motion_samples if r["kind"]=="reciprocal_branch"]
    assert any(r["phase"]=="left" for r in branches) and any(r["phase"]=="right" for r in branches)
    assert all((r["x"]<0 if r["phase"]=="left" else r["x"]>0) for r in branches)
    assert "中值定理的区间条件未满足" in native.labels
    assert any(r["kind"]=="cube_motion" for r in native.motion_samples)


def test_v004_inventory_and_explicit_sources():
    plan,contract=read("plan.json"),read("contract.json")
    validate_contract(contract)
    validate_selection(plan["formula_transitions"])
    assert set(contract["assets"])=={"visual_v004"}
    assert sum(len(u["features"]) for u in contract["units"])==20
    for name in ("traceable_film.py","traceable_film_v2.py","formula-continuity.md","formula-continuity-v2.md","derivative_ch05_monotonicity_v004.py"):
        assert any(s.endswith(name) for s in plan["sources"])
    for times in plan["formula_review_times"].values():
        assert times["before"]<times["during"]<times["after"]
        assert set(times.values())<=set(plan["review_times"])
