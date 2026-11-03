"""Offline native geometry/clock tests, never raster or independent approval."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule
from manimind.postproduce.traceable_film import validate_selection

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/derivative-ch06-traceable"


def read(name):
    return json.loads((FIX/name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def offline_inputs_only(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        if any(path.resolve().is_relative_to(ROOT/name) for name in ("runtime", "outputs")):
            raise AssertionError("Native tests consume fixture inputs only")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(ROOT/"examples/derivative_ch06_traceable.py")


@pytest.fixture(scope="module")
def native(lesson):
    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            patcher.setattr(sys.modules["derivative_ch06_extrema_v004"], "SemanticFormula", lesson.SemanticFormula)
        with native_run(lesson, lesson.DerivativeCh06Traceable, read("plan.json"), initialize) as scene:
            yield scene


def test_only_proof_overridden_and_real_transfer_preserved(lesson):
    base = sys.modules["derivative_ch06_extrema_v004"].DerivativeCh06ExtremaV004
    for name in ("construct", "opening", "neighborhood", "signs", "turns", "stationary", "closing", "reason_transfer", "beat", "focus_end"):
        assert getattr(lesson.DerivativeCh06Traceable, name) is getattr(base, name)
    old, new = read("baseline-plan.json"), read("plan.json")
    assert old["duration"] == new["duration"]
    assert old["intended_full_wav_placement"] == new["intended_full_wav_placement"]
    assert all(a == b for a,b in zip(old["cues"],new["cues"]) if a["id"] != "necessary")


def test_complete_original_words_references_wavs_and_measured_focus(native):
    plan = read("plan.json")
    assert read("narration.json")["units"] == read("baseline-narration.json")["units"]
    placed = schedule(visual_timeline(plan), read("narration.json"),
        {"duration":native.time,"windows":native._closed_focus}, read("timings.json"))
    assert native.time == pytest.approx(354.7)
    assert not native._open_focus and len(placed) == 7
    assert sum(len(r["references"]) for r in placed) == 20
    assert sum(r["duration_seconds"] for r in placed) == pytest.approx(335.04)
    for p, original in zip(placed,plan["intended_full_wav_placement"],strict=True):
        assert abs(p["start"]-original["intended_start"]) < .04


@pytest.mark.parametrize("stage", ["comparison_to_numerator","negative_h_quotient","positive_h_quotient"])
def test_old_real_transfers_still_have_intermediate_positions(native, stage):
    rows = [r for r in native.motion_samples if r["kind"] == "proof_transfer" and r["stage"] == stage]
    assert len(rows)>20 and all(r["copy_preserves_source"] for r in rows)
    for key in ("near","center"):
        np.testing.assert_allclose(rows[-1]["moving_centers"][key],rows[-1]["target_centers"][key],atol=1e-5)


@pytest.mark.parametrize("stage", ["equal_derivative","derivative_lower","derivative_upper","bounds_join"])
def test_assembly_begins_at_true_sources_and_reaches_roles(native, stage):
    rows = [r for r in native.motion_samples if r["kind"] == "traceable_assembly" and r["stage"] == stage]
    assert len(rows)>25
    assert rows[-1]["time"]-rows[0]["time"] >= .95
    assert any(np.linalg.norm(np.array(a)-b)>.4 for a,b in zip(rows[0]["moving"],rows[0]["targets"]))
    np.testing.assert_allclose(rows[-1]["moving"],rows[-1]["targets"],atol=1e-5)


def test_original_conditions_minimum_and_cusp_remain_in_order(native):
    marks = {r["id"]:r["time"] for r in native.visual_events}
    assert marks["equal_derivative_ready"] < marks["derivative_lower_ready"] < marks["derivative_upper_ready"] < marks["bounds_join_ready"] < marks["common_zero_proved"]
    assert marks["minimum_old_relations_removed"] < marks["minimum_same_zero_ready"] < marks["cusp_condition_ready"]
    assert "可导的内点 a" in native.labels
    assert "0 是尖点极小，导数不存在" in native.labels
    assert "端点不套用“可导内点”的必要条件" in native.labels


def test_current_v004_inventory_and_v2_explicit_source_selection():
    plan,contract = read("plan.json"),read("contract.json")
    validate_contract(contract)
    validate_selection(plan["formula_transitions"])
    assert set(contract["assets"]) == {"visual_v004"}
    assert len(contract["units"]) == 7
    assert sum(len(u["features"]) for u in contract["units"]) == 28
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19f6b-174f-7431-a0fd-2adf59301a9e"
    for dependency in ("traceable_film.py","traceable_film_v2.py","formula-continuity.md","formula-continuity-v2.md","derivative_ch06_extrema_v004.py"):
        assert any(p.endswith(dependency) for p in plan["sources"])
    assert set(plan["formula_review_times"]) == {r["id"] for r in plan["formula_transitions"]}
    for times in plan["formula_review_times"].values():
        assert times["before"]<times["during"]<times["after"]
        assert set(times.values()) <= set(plan["review_times"])
