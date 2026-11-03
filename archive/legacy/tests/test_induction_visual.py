"""Physical invariants and native timing; placeholders do not approve pixels."""

import ast
import json
import math
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.semantic_focus import focus_windows, validate_narration


ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"examples/induction_visual.py"
FIXTURE=ROOT/"tests/fixtures/induction-visual"


def data(name):
    return json.loads((FIXTURE/name).read_text(encoding="utf-8"))


def functions():
    nodes=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef)]
    scope={"math":math}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),"exec"),scope)
    return scope


@pytest.mark.parametrize("velocity",[-6,-3,0,3,6])
def test_signed_emf_force_and_energy(velocity):
    f=functions()["conductor_state"]
    state=f(3,velocity)
    assert state["flux"] == -3
    assert state["emf"] == velocity
    assert state["current"] == velocity/5
    assert state["magnetic_force_x"]*velocity <= 0
    assert state["mechanical_power"] == pytest.approx(state["heat_power"])
    assert state["heat_power"] == pytest.approx(velocity*velocity/5)
    dt=.0001
    shifted=f(3+velocity*dt,velocity)
    assert -(shifted["flux"]-state["flux"])/dt == pytest.approx(state["emf"])


def test_quadratic_power_and_linear_current():
    f=functions()["conductor_state"]
    a,b=f(3,3),f(3,6)
    assert b["current"] == 2*a["current"]
    assert b["heat_power"] == 4*a["heat_power"]
    assert functions()["sweep_state"](.8)["x"] == pytest.approx(4.9)
    assert functions()["sweep_state"](.8,4.9,-3)["x"] == pytest.approx(2.5)


@pytest.mark.parametrize("args",[(-1,3),(1,float("nan")),(1,3,0),(1,3,.5,0),(1,3,.5,2,0)])
def test_invalid_parameters(args):
    with pytest.raises(ValueError):
        functions()["conductor_state"](*args)


@pytest.fixture(scope="module")
def scene():
    module=load_lesson(SOURCE)
    with native_run(module,module.InductionLesson,data("plan.json")) as value:
        yield value


def test_native_scene_clock_events_and_whole_focus_contract(scene):
    plan=data("plan.json")
    assert scene.time == pytest.approx(240)
    assert scene.frame == 7200
    validate_events(visual_timeline(plan),{"duration":scene.time,"events":scene.visual_events})
    focuses={"duration":scene.time,"windows":scene._closed_focus}
    actual=focus_windows(focuses,scene.time)
    assert set(actual) == {f["id"] for f in plan["focus_intents"]}
    validate_narration(data("narration-draft.json"),scene.timeline,focuses)
    assert not scene._open_focus
    for row in scene.plays:
        assert row["end"] > row["start"]
    report=json.loads(scene.out.files["induction-motion.json"])
    assert report["duration"] == 240
    assert report["samples"]


def test_shared_circuit_model_tracks_actual_geometry_and_both_directions(scene):
    rows=scene.model_samples
    assert any(row["velocity"]>0 for row in rows)
    assert any(row["velocity"]<0 for row in rows)
    assert any(row["velocity"]==0 for row in rows)
    for row in rows:
        assert row["rod_scene_x"] == pytest.approx(-5.25+1.1*row["x"])
        assert row["heat_power"] == pytest.approx(row["mechanical_power"])
    # Sampler is inactive in the open-rod/algebra and final prediction chapters.
    assert not any(20 < row["time"] < 88 for row in rows)
    assert not any(row["time"] > 208 for row in rows)


def test_precise_visible_terms_and_no_defensive_copy(scene):
    text=" ".join(scene.labels)
    for bad in ("仅用于","只是示意","仅供参考","不是实际运动","模型时钟"):
        assert bad not in text
    assert "开路导体棒" in text and "闭合回路" in text
    assert "感应磁场向纸外" in text and "感应磁场向纸内" in text
    assert "电阻发热" in text and "机械输入 → 电阻热功率" in text
    assert "多付多少功" not in text
    assert "外力功率增加多少" in text


def test_fresh_source_and_state_ownership_are_explicit():
    plan=data("plan.json")
    assert plan["revision_mode"] == "fresh"
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v3.1.json"
    assert "outputs/" not in SOURCE.read_text()
    methods={node.name for node in ast.walk(ast.parse(SOURCE.read_text())) if isinstance(node,ast.FunctionDef)}
    assert not {"get_time","get_time_progression","render","publish","sound"}&methods
    for contract in plan["state_contracts"]:
        assert all(contract.get(k) for k in ("writer","consumers","lifecycle","invalidation"))
