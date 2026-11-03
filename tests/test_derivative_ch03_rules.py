"""Signed-increment algebra and draft contracts, entirely without GL or TTS."""

from fractions import Fraction
import ast
import json
import math
from pathlib import Path

import pytest

from test_derivative_ch02_basics import pure_module, symbolic_run, assert_contracts


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch03_rules.py"
FIXTURES = ROOT / "tests/fixtures/derivative-ch03-rules"


def read_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_native_line_endpoint_updates_do_not_receive_python_lists():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "put_start_and_end_on"]
    assert calls
    assert all(not isinstance(arg, ast.List) for node in calls for arg in node.args[:2])


@pytest.fixture(autouse=True)
def forbid_runtime_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT / "runtime"):
            raise AssertionError("Offline tests consume versioned fixtures, not runtime")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def model():
    return pure_module(SOURCE)


@pytest.mark.parametrize("x", [Fraction(-3), Fraction(0), Fraction(1), Fraction(5, 2)])
@pytest.mark.parametrize("h", [Fraction(-1, 2), Fraction(-1, 1000), Fraction(1, 1000), Fraction(1, 2)])
@pytest.mark.parametrize("c", [-3, 0, 3])
def test_linear_increment_and_rate_identities_exact(model, x, h, c):
    s = model.linear_state(x, h, c)
    u0, u1, v0, v1 = x*x, (x+h)**2, x, x+h
    assert s["sum_increment"] == (u1+v1)-(u0+v0)
    assert s["difference_increment"] == (u1-v1)-(u0-v0)
    assert s["scaled_increment"] == c*u1-c*u0
    assert s["sum_rate"] == s["sum_increment"]/h
    assert s["difference_rate"] == s["difference_increment"]/h
    assert s["scaled_rate"] == s["scaled_increment"]/h


@pytest.mark.parametrize("x", [Fraction(-3), Fraction(-1), Fraction(0), Fraction(1), Fraction(5, 2)])
@pytest.mark.parametrize("h", [Fraction(-1, 2), Fraction(-1, 1000), Fraction(1, 1000), Fraction(1, 2)])
def test_three_area_terms_equal_signed_product_increment(model, x, h):
    s = model.product_state(x, h)
    actual = (2+x+h)*(1+(x+h)**2)-(2+x)*(1+x*x)
    assert s["increment"] == s["right"]+s["top"]+s["corner"] == actual
    q = model.product_quotient(x, h)
    assert q["rate"] == actual/h == q["right_rate"]+q["top_rate"]+q["corner_rate"]
    assert q["corner_rate"] == (s["du"]/h)*s["dv"]
    assert s["derivative"] == 1+4*x+3*x*x


@pytest.mark.parametrize("sign", [-1, 1])
def test_normalized_corner_converges_not_only_unscaled_area(model, sign):
    previous = math.inf
    for denominator in (10, 100, 1000, 10000):
        h = Fraction(sign, denominator)
        s = model.product_quotient(Fraction(1), h)
        assert s["corner_rate"] == 2*h+h*h
        assert abs(s["corner_rate"]) < previous
        previous = abs(s["corner_rate"])
        assert s["rate"]-s["derivative"] == 5*h+h*h


@pytest.mark.parametrize("u,v,du,dv", [(3, 2, 1, 2), (-3, 2, -1, Fraction(1, 3)),
    (3, -2, Fraction(1, 10), Fraction(-1, 20)), (0, 1, 0, Fraction(1, 2)),
    (3, 2, -4, -3)])
def test_quotient_every_intermediate_row_exact(model, u, v, du, dv):
    u, v, du, dv = map(Fraction, (u, v, du, dv))
    raw = (u+du)/(v+dv)-u/v
    common = (v*(u+du)-u*(v+dv))/(v*(v+dv))
    reduced = (v*du-u*dv)/(v*(v+dv))
    assert raw == common == reduced == model.quotient_increment(u, v, du, dv)


@pytest.mark.parametrize("x", [Fraction(1, 2), Fraction(1), Fraction(2), Fraction(4)])
def test_cost_model_units_and_rule(model, x):
    s = model.average_cost_state(x)
    assert s["total_cost"] == x*x+4
    assert s["average_cost"] == x+4/x
    assert s["derivative"] == 1-4/x**2
    for h in (Fraction(-1, 100), Fraction(1, 100)):
        raw = ((x+h+4/(x+h))-(x+4/x))/h
        assert raw == model.average_cost_quotient(x, h)
        du, dv = 2*x*h+h*h, h
        assert raw == model.quotient_increment(x*x+4, x, du, dv)/h


def test_cost_minimum_has_sign_change_not_just_stationary_point(model):
    assert model.average_cost_state(1)["derivative"] < 0
    assert model.average_cost_state(2)["derivative"] == 0
    assert model.average_cost_state(4)["derivative"] > 0
    assert model.average_cost_state(2)["average_cost"] == 4


@pytest.mark.parametrize("x", [-2.1, -1, 0, .4, 1.7])
def test_product_trig_example_by_numeric_difference(model, x):
    h = 1e-5
    approximate = (model.product_example(x+h)["value"]-model.product_example(x-h)["value"])/(2*h)
    assert model.product_example(x)["derivative"] == pytest.approx(approximate, abs=2e-9)


def test_domains_and_invalid_data_rejected(model):
    cases = [lambda: model.linear_state(1, 0), lambda: model.product_quotient(1, 0),
             lambda: model.quotient_increment(1, 0, 1, 1),
             lambda: model.quotient_increment(1, 2, 1, -2),
             lambda: model.quotient_derivative(1, 0, 1, 1),
             lambda: model.average_cost_state(0), lambda: model.average_cost_state(-1),
             lambda: model.average_cost_quotient(1, -2), lambda: model.average_cost_quotient(1, 0)]
    for fn in cases:
        with pytest.raises(ValueError):
            fn()
    for bad in (float("nan"), float("inf"), True, None, "1", 1j):
        for fn in (model.average_cost_state, model.product_example, lambda x: model.product_state(x, .1)):
            with pytest.raises((ValueError, TypeError)):
                fn(bad)


def test_draft_control_flow_and_versioned_contracts():
    scene = assert_contracts(SOURCE, "DerivativeRulesLesson", read_fixture("plan.json"),
                             read_fixture("narration.json"), read_fixture("science.json"))
    assert {s["kind"] for s in scene.samples} == {"linear_increments", "product_area", "average_cost"}
    by_id = {w["id"]: w for w in scene.closed}
    assert by_id["product_corner_shrink"]["end"] < by_id["product_rule"]["start"]
    assert by_id["cost_decreasing"]["end"] < by_id["cost_stationary"]["start"]
    assert by_id["cost_stationary"]["end"] < by_id["cost_increasing"]["start"]


def test_durations_can_be_retimed_locally():
    plan = read_fixture("plan.json")
    plan["cues"][3]["duration"] += 20
    plan["cues"][3]["stage_times"] = {"0.69": 57.0}
    scene, _ = symbolic_run(SOURCE, "DerivativeRulesLesson", plan)
    assert scene.time == plan["duration"]+20


def test_rejects_wrong_cue_order():
    plan = read_fixture("plan.json")
    plan["cues"][0], plan["cues"][1] = plan["cues"][1], plan["cues"][0]
    with pytest.raises(ValueError, match="cue order"):
        symbolic_run(SOURCE, "DerivativeRulesLesson", plan)
