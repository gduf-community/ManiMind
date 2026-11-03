"""Fixture-only native CH07 identity, audio and retained-model checks."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.postproduce.traceable_film import validate_selection
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/derivative-ch07-traceable"


def read(name):
    return json.loads((FIX / name).read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        if any(path.resolve().is_relative_to(ROOT / name) for name in ("runtime", "outputs")):
            raise AssertionError("Fixture-only native tests")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(ROOT / "examples/derivative_ch07_traceable.py")


@pytest.fixture(scope="module")
def native(lesson):
    with native_run(lesson, lesson.DerivativeCh07Traceable, read("plan.json")) as scene:
        yield scene


def test_only_candidate_and_comparison_methods_revised(lesson):
    prior = sys.modules["derivative_ch07_extremes_v004"].DerivativeCh07ExtremesV004
    for name in ("construct", "beat", "graph", "opening", "parameter", "conditions", "open_interval", "closing"):
        assert getattr(lesson.DerivativeCh07Traceable, name) is getattr(prior, name)
    new, old = read("plan.json"), read("baseline-plan.json")
    assert new["duration"] == old["duration"]
    assert new["intended_full_wav_placement"] == old["intended_full_wav_placement"]
    for cue, before in zip(new["cues"], old["cues"], strict=True):
        if cue["id"] not in ("candidates", "compare"):
            assert cue == before


def test_intact_original_audio_is_feasible_on_actual_native_clock(native):
    assert read("narration.json")["units"] == read("baseline-narration.json")["units"]
    plan = read("plan.json")
    placed = schedule(visual_timeline(plan), read("narration.json"),
        {"duration":native.time, "windows":native._closed_focus}, read("timings.json"))
    assert native.time == pytest.approx(322.2) and not native._open_focus
    assert len(placed) == 7
    assert sum(row["duration_seconds"] for row in placed) == pytest.approx(297.44)
    for row, intended in zip(placed, plan["intended_full_wav_placement"], strict=True):
        assert abs(row["start"]-intended["intended_start"]) < .04
        for phrase in row["phrases"]:
            assert phrase["focus_start"] <= phrase["visual_start"] + 1e-6
            assert phrase["visual_end"] <= phrase["focus_end"] + 1e-6


@pytest.mark.parametrize("stage", ["stationary_to_candidate", "domain_to_endpoints", "substitute_0", "value_0_to_column",
    "substitute_1", "value_1_to_column", "substitute_3", "value_3_to_column", "select_minimum_value",
    "minimum_position", "select_maximum_value", "maximum_position"])
def test_real_sources_native_intermediates_and_landing(native, stage):
    rows = [r for r in native.motion_samples if r["kind"] == "traceable_roles" and r["stage"] == stage]
    assert len(rows) >= 15
    assert rows[-1]["time"]-rows[0]["time"] >= .45
    assert any(np.linalg.norm(np.array(a)-b) > .15 for a,b in zip(rows[0]["moving"], rows[0]["targets"]))
    np.testing.assert_allclose(rows[-1]["moving"], rows[-1]["targets"], atol=1e-5)


def test_substitution_roles_do_not_confuse_constant_input_and_result(lesson):
    for x, y in ((0,1), (1,0), (3,4)):
        f = lesson.SemanticFormula(f"({x}-1)^2={y}", tokens={"input":(str(x),0), "result":(str(y),1 if y == 1 else 0)})
        assert not set(map(id, f.tag("input").family_members_with_points())) & set(map(id, f.tag("result").family_members_with_points()))


def test_parameter_and_open_interval_full_model_motions_remain(native):
    moving = [r for r in native.motion_samples if r["kind"] == "moving_endpoint"]
    assert moving[0]["b"] == pytest.approx(1.25) and moving[-1]["b"] == pytest.approx(3)
    assert any(r["b"] == 2 and r["argmax"] == (0,2) for r in moving)
    approach = [r for r in native.motion_samples if r["kind"] == "open_approach"]
    assert approach[0]["x"] == pytest.approx(2.2) and approach[-1]["x"] == pytest.approx(2.99)
    assert all(1 < r["x"] < 3 and r["value"] < 4 for r in approach)
    assert "全域比较：左段与右支" in native.labels
    assert r"0<x\le1:\quad f(x)<1=f(2)" in native.labels
    assert r"1<x<3:\quad x<y<3,\ f(x)<f(y)" in native.labels


def test_current_v004_complete_inventory_and_selected_action_sources():
    contract, plan = read("contract.json"), read("plan.json")
    validate_contract(contract)
    validate_selection(plan["formula_transitions"])
    assert set(contract["assets"]) == {"visual_v004"}
    assert sum(len(u["features"]) for u in contract["units"]) == 24
    assert any(f["id"] == "v004-whole-domain-no-maximum" for u in contract["units"] for f in u["features"])
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v4.3.1-unit.json"
    for name in ("traceable_film.py", "traceable_film_v2.py", "formula-continuity.md", "formula-continuity-v2.md", "derivative_ch07_extremes_v004.py"):
        assert any(s.endswith(name) for s in plan["sources"])
    for times in plan["formula_review_times"].values():
        assert times["before"] < times["during"] < times["after"]
        assert set(times.values()) <= set(plan["review_times"])
