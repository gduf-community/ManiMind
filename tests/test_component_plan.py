from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from manimind.components.plan import CompiledShot, PlanError, parse_plan, preflight, validate_plan, parameter_state

FIXTURE = Path(__file__).parents[1] / "configs/component-foundation.json"


@pytest.fixture
def plan():
    return json.loads(FIXTURE.read_text())


def test_three_different_topics_share_one_contract(plan):
    original = deepcopy(plan)
    validated = validate_plan(plan)
    assert validated == plan == original
    validated["shots"][0]["parameters"]["p"] = 99
    assert plan == original
    assert parse_plan(json.dumps(plan)) == plan


@pytest.mark.parametrize("change", [
    lambda p: p.update(code="import os"),
    lambda p: p.update(schema_version="other"),
    lambda p: p.update(id="../../escape"),
    lambda p: p.update(shots=[]),
    lambda p: p["shots"].append(deepcopy(p["shots"][0])),
    lambda p: p["shots"][0].update(duration=True),
    lambda p: p["shots"][0].update(duration=float("nan")),
    lambda p: p["shots"][0]["axes"].update(x_range=[1, 4, 1]),
    lambda p: p["shots"][0]["axes"].update(x_range=[0, 4, 0]),
    lambda p: p["shots"][0]["axes"].update(y_range=[0, 4, .001]),
    lambda p: p["shots"][1]["axes"].update(equal_units=False),
    lambda p: p["shots"][0]["components"][0].update(kind="python"),
    lambda p: p["shots"][0]["components"][0].update(kind=[]),
    lambda p: p["shots"][0]["components"][0].update(color=[]),
    lambda p: p["shots"][0]["components"][0].update(color="#abcdef"),
    lambda p: p["shots"][0]["components"][1].update(source="missing"),
    lambda p: p["shots"][0]["components"][1].update(source="phase"),
    lambda p: p["shots"][0]["components"][1].update(lhs=r"\input{file}"),
    lambda p: p["shots"][0]["components"][2].update(position=["missing", 0]),
    lambda p: p["shots"][0]["components"][3].update(decimals=True),
    lambda p: p["shots"][0]["keyframes"].reverse(),
    lambda p: p["shots"][0]["keyframes"][0].update(at=.1),
    lambda p: p["shots"][0]["keyframes"][-1].update(at=.9),
    lambda p: p["shots"][0]["keyframes"][-1].update(values={"p": 1}),
    lambda p: p["shots"][0]["keyframes"][-2].update(at=.99),
    lambda p: p["shots"][0]["keyframes"][1].update(values={"p": 1, "x": 2}),
    lambda p: p["provenance"].update(kind=[]),
    lambda p: p["provenance"].pop("interventions"),
])
def test_fail_closed_contract(plan, change):
    change(plan)
    with pytest.raises(ValueError):
        validate_plan(plan)


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '[]'])
def test_strict_json(raw):
    with pytest.raises(ValueError):
        parse_plan(raw)


def test_parameter_clock_and_terminal_hold(plan):
    shot = plan["shots"][0]
    assert parameter_state(shot, 0) == {"p": -1.5}
    assert parameter_state(shot, .1) == {"p": -1.5}
    assert parameter_state(shot, .475)["p"] == pytest.approx(0)
    assert parameter_state(shot, .95) == parameter_state(shot, 1) == {"p": 1.5}


def test_shared_bindings_and_signed_coordinates(plan):
    sine = CompiledShot(plan["shots"][0])
    start, end = sine.evaluate(0), sine.evaluate(1)
    assert start["objects"]["zero"]["position"] == [-1.5, 0]
    assert end["objects"]["zero"]["position"] == [1.5, 0]
    assert end["objects"]["phase"]["value"] == 1.5
    assert start["objects"]["wave"]["points"][60][1] == pytest.approx(math.sin(1.5))
    assert end["objects"]["wave"]["points"][60][1] == pytest.approx(math.sin(-1.5))
    assert "sin" in end["objects"]["law"]["latex"]
    vector = CompiledShot(plan["shots"][1]).evaluate(1)["objects"]
    assert vector["first"]["end"] == vector["second"]["start"]
    assert vector["second"]["end"] == vector["result"]["end"] == [1, 3]
    assert vector["length"]["value"] == pytest.approx(math.sqrt(10))
    roots = CompiledShot(plan["shots"][2]).evaluate(1)["objects"]
    assert roots["left-root"]["position"] == [-2, 4]
    assert roots["right-root"]["position"] == [2, 4]


def test_formula_derives_from_curve_not_duplicate_expression(plan):
    shot = plan["shots"][0]
    shot["components"][0]["expression"] = {"op": "cos", "args": ["x"]}
    assert "cos" in CompiledShot(shot).evaluate(.5)["objects"]["law"]["latex"]


def test_invalid_intermediate_frame_detected(plan):
    shot = plan["shots"][0]
    shot["components"][3]["expression"] = {"op": "div", "args": [1, "p"]}
    shot["parameters"] = {"p": -1}
    # The singularity lands on emitted frame 60, rather than between samples.
    shot["keyframes"] = [{"at": 0, "values": {"p": -1}}, {"at": 120 / 269, "values": {"p": 1}}, {"at": 1, "values": {"p": 1}}]
    with pytest.raises(ValueError):
        preflight({**plan, "shots": [shot]})


def test_out_of_bounds_and_degenerate_geometry_rejected(plan):
    shot = plan["shots"][0]
    shot["components"][0]["expression"] = 100
    with pytest.raises(PlanError, match="outside"):
        CompiledShot(shot).evaluate(.5)
    shot = plan["shots"][1]
    shot["components"][0]["end"] = [0, 0]
    with pytest.raises(PlanError, match="Degenerate"):
        CompiledShot(shot).evaluate(0)


def test_every_render_frame_is_preflighted(plan):
    report = preflight(plan)
    assert report["status"] == "pass"
    assert report["total_frames"] == 810
    assert report["duration"] == 27
    assert [r["frames_checked"] for r in report["shots"]] == [270, 270, 270]
    assert [r["start_frame"] for r in report["shots"]] == [0, 270, 540]
