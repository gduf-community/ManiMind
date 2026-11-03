"""Persistent common identity, fixture-only native timing and glyph lifetime."""
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from lesson_native_harness import load_lesson,native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule
from manimind.review.content_regression import validate_contract
from test_derivative_ch06_traceable_v006 import (
    test_only_required_roles_copy_from_actual_sources as check_role_copy,
    test_new_relations_never_draw_with_retired_relations_opaque as check_reversal,
)

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"tests/fixtures/derivative-ch06-traceable-v007"


def read(name):
    return json.loads((FIX/name).read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original=Path.open
    def guard(path,*args,**kwargs):
        if any(path.resolve().is_relative_to(ROOT/name) for name in ("runtime","outputs")):
            raise AssertionError("Fixture-only tests")
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,"open",guard)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as p:
        p.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(ROOT/"examples/derivative_ch06_traceable_v007.py")


@pytest.fixture(scope="module")
def native(lesson):
    with pytest.MonkeyPatch.context() as p:
        def initialize(scene):
            p.setattr(sys.modules["derivative_ch06_extrema_v004"],"SemanticFormula",lesson.SemanticFormula)
        with native_run(lesson,lesson.DerivativeCh06TraceableV007,read("plan.json"),initialize) as scene:
            yield scene


def test_identity_letters_equalities_and_same_derivative_do_not_retire_during_bounds(native):
    rows=[r for r in native.motion_samples if r["kind"]=="v007_identity_bridge"]
    assert len(rows)>300 and rows[-1]["time"]-rows[0]["time"]>9
    assert all(r["glyph_ids"]==rows[0]["glyph_ids"] for r in rows)
    assert all(min(r["opacity"])>.95 for r in rows)
    anchors=[r for r in native.motion_samples if r["kind"]=="v006_common_anchor"]
    assert all(r["glyph_ids"]==anchors[0]["glyph_ids"] for r in anchors)
    np.testing.assert_allclose([r["center"] for r in anchors],np.tile(anchors[0]["center"],(len(anchors),1)),atol=1e-5)
    for stage,side in (("derivative_lower","left"),("bounds_join","right")):
        samples=[r for r in native.motion_samples if r.get("stage")==stage]
        target_x=samples[-1]["targets"][0][0]
        edge=rows[0][side][0]
        assert target_x<edge if side=="left" else target_x>edge


@pytest.mark.parametrize("stage",["derivative_lower","bounds_join","bounds_to_zero"])
def test_original_source_role_copies_still_native(native,stage):
    check_role_copy(native,stage)


def test_opposing_relations_still_exit_before_new_ones(native):
    check_reversal(native)


def test_all_other_scientific_scenes_and_original_reason_transfer_inherited(lesson):
    prior=sys.modules["derivative_ch06_traceable_v006"].DerivativeCh06TraceableV006
    for name in ("construct","opening","neighborhood","signs","turns","stationary","closing","reason_transfer","copy_parts","reverse_relations","beat"):
        assert getattr(lesson.DerivativeCh06TraceableV007,name) is getattr(prior,name)
    plan,old=read("plan.json"),read("previous-plan.json")
    assert plan["duration"]==old["duration"] and plan["intended_full_wav_placement"]==old["intended_full_wav_placement"]
    assert all(c==p for c,p in zip(plan["cues"],old["cues"],strict=True) if c["id"]!="necessary")


def test_original_full_WAV_schedule_and_complete_v004_inventory_not_relaxed(native):
    plan,contract,prior=read("plan.json"),read("contract.json"),read("previous-contract.json")
    assert read("narration.json")["units"]==read("baseline-narration.json")["units"]
    placed=schedule(visual_timeline(plan),read("narration.json"),{"duration":native.time,"windows":native._closed_focus},read("timings.json"))
    assert len(placed)==7 and native.time==pytest.approx(354.7)
    assert sum(r["duration_seconds"] for r in placed)==pytest.approx(335.04)
    for row,old in zip(placed,plan["intended_full_wav_placement"],strict=True):
        assert abs(row["start"]-old["intended_start"])<.04
    validate_contract(contract)
    assert contract["units"]==prior["units"] and contract["assets"]==prior["assets"]
    assert sum(len(u["features"]) for u in contract["units"])==28
