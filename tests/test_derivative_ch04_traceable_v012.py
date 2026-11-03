"""Pending and historical state roles; native tests are not GL acceptance."""

import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.review.meaning_units import schedule
from manimind.review.content_regression import validate_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch04-traceable-v012"


def read(name):
    return json.loads((FIXTURE/name).read_text())


@pytest.fixture(scope="module")
def native():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT/"examples"))
        module = load_lesson(ROOT/"examples/derivative_ch04_traceable_v012.py")
        import derivative_ch04_chain as base
        import manimind.components.formula_motion as motion
        def initialize(scene):
            patch.setattr(base,"SemanticFormula",motion.SemanticFormula)
        with native_run(module,module.DerivativeChainTraceableV012,read("plan.json"),initialize) as scene:
            yield scene


def closest(scene,time):
    rows = [r for r in scene.motion_samples if r["kind"] == "transfer_display_roles"]
    row = min(rows,key=lambda r:abs(r["time"]-time))
    assert abs(row["time"]-time) < .04
    return row


def test_input_new_value_does_not_expose_old_downstream_as_current(native):
    row = closest(native,66.447)
    assert row["roles"] == ["ready","pending","pending"]
    assert row["numeric_shown"] == [True,False,False]
    assert row["base_reference_present"]


def test_new_intermediate_leaves_output_explicitly_pending(native):
    row = closest(native,74.887)
    assert row["roles"] == ["ready","ready","pending"]
    assert row["numeric_shown"] == [True,True,False]
    assert row["base_reference_present"]


def test_computing_roles_and_complete_original_numeric_trajectories(native):
    roles = [r for r in native.motion_samples if r["kind"] == "transfer_display_roles"]
    assert roles and all(r["base_reference_present"] for r in roles)
    for index,phase in ((1,"inner"),(2,"outer")):
        assert any(r["phase"]==phase and r["roles"][index]=="computing" and r["numeric_shown"][index] for r in roles)
    assert roles[-1]["roles"] == ["ready","ready","ready"]
    assert roles[-1]["numeric_shown"] == [True,True,True]
    values = [r for r in native.motion_samples if r["kind"] == "chain_transfer"]
    assert any(1<r["x"]<1.1 and r["u"]==2 and r["y"]==8 for r in values)
    assert any(2<r["u"]<2.21 and r["y"]==8 for r in values)
    assert any(8<r["y"]<10.793861 for r in values)
    assert (values[-1]["x"],values[-1]["u"],values[-1]["y"]) == pytest.approx((1.1,2.21,10.793861))
    assert {r"x_0=1",r"u_0=2",r"y_0=8","基点对照","内层计算中","外层计算中"}.issubset(native.labels)


def test_original_whole_wavs_references_and_clock_remain_feasible(native):
    plan = read("plan.json")
    assert native.time == pytest.approx(plan["duration"],abs=1e-6)
    rows = schedule(native.timeline,read("narration.json"),
        {"duration":native.time,"windows":native._closed_focus},read("timings.json"))
    assert len(rows)==8 and sum(len(r["references"]) for r in rows)==26
    for row,old in zip(rows,plan["intended_full_wav_placement"],strict=True):
        assert row["start"] == pytest.approx(old["intended_start"],abs=.04)
        assert row["duration_seconds"] == old["duration_seconds"]


def test_other_repaired_geometry_and_original_baseline_are_not_replaced(native):
    validate_contract(read("contract.json"))
    assert "visual_v005" in read("contract.json")["assets"]
    fixed = [r for r in native.motion_samples if r["kind"] == "collection_fixed_geometry"]
    assert len({r["factor"] for r in fixed}) == len({r["lhs"] for r in fixed}) == 1
    visible = [r for r in native.motion_samples if r["kind"] == "collection_scalar_visibility"]
    assert not any(r["old"]>.001 and r["new"]>.001 for r in visible)
