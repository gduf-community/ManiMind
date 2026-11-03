"""CH06 v006 native role lifetime checks, not raster or editorial approval."""
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from lesson_native_harness import load_lesson,native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.meaning_units import schedule
from manimind.review.content_regression import validate_contract

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"tests/fixtures/derivative-ch06-traceable-v006"


def read(name):
    return json.loads((FIX/name).read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original=Path.open
    def guarded(path,*args,**kwargs):
        if any(path.resolve().is_relative_to(ROOT/name) for name in ("runtime","outputs")):
            raise AssertionError("Native tests consume fixtures only")
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,"open",guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(ROOT/"examples/derivative_ch06_traceable_v006.py")


@pytest.fixture(scope="module")
def native(lesson):
    with pytest.MonkeyPatch.context() as p:
        def initialize(scene):
            p.setattr(sys.modules["derivative_ch06_extrema_v004"],"SemanticFormula",lesson.SemanticFormula)
        with native_run(lesson,lesson.DerivativeCh06TraceableV006,read("plan.json"),initialize) as scene:
            yield scene


def test_unchanged_native_scientific_scenes_and_original_transfer(lesson):
    prior=sys.modules["derivative_ch06_traceable"].DerivativeCh06Traceable
    for key in ("opening","neighborhood","signs","turns","stationary","closing","reason_transfer","construct","beat"):
        assert getattr(lesson.DerivativeCh06TraceableV006,key) is getattr(prior,key)
    plan,old=read("plan.json"),read("baseline-plan.json")
    assert all(a==b for a,b in zip(plan["cues"],old["cues"]) if a["id"]!="necessary")


def test_complete_original_audio_has_a_real_native_feasible_schedule(native):
    plan=read("plan.json")
    assert read("narration.json")["units"]==read("baseline-narration.json")["units"]
    placed=schedule(visual_timeline(plan),read("narration.json"),
        {"duration":native.time,"windows":native._closed_focus},read("timings.json"))
    assert len(placed)==7 and not native._open_focus
    assert sum(p["duration_seconds"] for p in placed)==pytest.approx(335.04)
    for p,original in zip(placed,plan["intended_full_wav_placement"],strict=True):
        assert abs(p["start"]-original["intended_start"])<.04


def test_same_common_derivative_glyphs_stay_at_one_anchor_during_bounds_and_minimum(native):
    rows=[r for r in native.motion_samples if r["kind"]=="v006_common_anchor"]
    assert rows
    assert all(r["glyph_ids"]==rows[0]["glyph_ids"] for r in rows)
    np.testing.assert_allclose([r["center"] for r in rows],np.tile(rows[0]["center"],(len(rows),1)),atol=1e-5)
    assert all(min(r["opacity"])>.95 for r in rows)


@pytest.mark.parametrize("stage",["derivative_lower","bounds_join","bounds_to_zero"])
def test_only_required_roles_copy_from_actual_sources(native,stage):
    rows=[r for r in native.motion_samples if r["kind"]=="v006_role_copy" and r["stage"]==stage]
    assert len(rows)>20
    assert any(np.linalg.norm(np.array(a)-b)>.3 for a,b in zip(rows[0]["moving"],rows[0]["targets"]))
    np.testing.assert_allclose(rows[-1]["moving"],rows[-1]["targets"],atol=1e-5)


def test_new_relations_never_draw_with_retired_relations_opaque(native):
    rows=[r for r in native.motion_samples if r["kind"]=="v006_relation_reversal"]
    assert rows and any(any(r["new_present"]) for r in rows)
    for row in rows:
        if any(row["new_present"]):
            assert max(row["old"])<1e-6
    marks={e["id"]:e["time"] for e in native.visual_events}
    assert marks["minimum_old_relations_removed"]<marks["minimum_blank_relations_readable"]<marks["minimum_fresh_relations_ready"]


def test_clamp_is_preserved_history_during_zero_conclusion_not_replaced_in_place(native):
    marks={e["id"]:e["time"] for e in native.visual_events}
    assert marks["bounds_join_ready"]<marks["complete_clamp_readable"]<marks["common_zero_proved"]<marks["minimum_old_relations_removed"]
    assert "可导：L、R 对应同一个导数" in native.labels
    assert "0 是尖点极小，导数不存在" in native.labels
    assert "端点不套用“可导内点”的必要条件" in native.labels


def test_no_baseline_inventory_relaxation_and_new_provenance():
    plan,contract,prior=read("plan.json"),read("contract.json"),read("previous-contract.json")
    validate_contract(contract)
    assert contract["units"]==prior["units"] and contract["assets"]==prior["assets"]
    assert sum(len(u["features"]) for u in contract["units"])==28
    assert contract["previous_unmet_improvement_targets"]==prior["improvement_targets"]
    assert plan["scene"].endswith("derivative_ch06_traceable_v006.py")
    assert plan["author_agent"]==plan["author_context"]=="01a19f6b-174f-7431-a0fd-2adf59301a9e"
    assert all(plan[k]==read("previous-plan.json")[k] for k in ("duration","intended_full_wav_placement"))
    assert any(p.endswith("derivative_ch06_traceable.py") for p in plan["sources"])
