"""Chapter 05 fixture-only mathematics and native geometry, without a camera."""

import ast
from fractions import Fraction
import json
from pathlib import Path
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch05_monotonicity.py"
FIXTURE = ROOT / "tests/fixtures/derivative-ch05-monotonicity"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def model():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name != "polyline"
             or isinstance(node, ast.Import) and any(item.name == "math" for item in node.names)
             or isinstance(node, ast.ImportFrom) and node.module == "numbers"]
    module = types.ModuleType("monotonicity_pure_v001")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), module.__dict__)
    return module


def test_versioned_polynomial_states(model):
    for expected in read("mathematics-v001.json")["samples"]:
        state = model.linked_state(expected["x"])
        assert {key: state[key] for key in expected} == expected


@pytest.mark.parametrize("x", [Fraction(-9, 2), Fraction(-5, 4), Fraction(-1), Fraction(-1, 10),
                               Fraction(0), Fraction(1), Fraction(5, 4), Fraction(9, 2)])
def test_derivative_factorization_and_finite_difference_identity(model, x):
    assert model.derivative(x) == 3*(x-1)*(x+1)
    h = Fraction(1, 1000)
    quotient = (model.function(x+h)-model.function(x))/h
    assert quotient == model.derivative(x)+3*x*h+h*h


def test_factor_sign_on_every_versioned_open_interval(model):
    for interval in read("mathematics-v001.json")["intervals"]:
        left, right = interval["left"], interval["right"]
        points = [Fraction(left)+(Fraction(right-left)*i/40) for i in range(1, 40)]
        assert all(model.derivative_sign(x) == interval["sign"] for x in points)
        values = [model.function(x) for x in points]
        assert all((b-a)*interval["sign"] > 0 for a, b in zip(values, values[1:]))
    assert model.derivative_sign(-1) == model.derivative_sign(1) == 0


@pytest.mark.parametrize("a,b", [(-2, -1.15), (-3, -2), (-1.5, -1.1)])
def test_mean_value_witness_is_inside_pair_and_matches_secant(model, a, b):
    c = model.secant_witness(a, b)
    assert a < c < b
    assert model.derivative(c) == pytest.approx((model.function(b)-model.function(a))/(b-a))


@pytest.mark.parametrize("a,b", [(0, 1), (-1, -2), (-2, -1), (1, 1)])
def test_witness_rejects_pair_outside_displayed_interval(model, a, b):
    with pytest.raises(ValueError, match="a < b < -1"):
        model.secant_witness(a, b)


def test_zero_derivative_and_strict_increase_are_compatible(model):
    assert model.cube_derivative(0) == 0
    for a, b in read("mathematics-v001.json")["cube_pairs"]:
        a, b = Fraction(str(a)), Fraction(str(b))
        assert model.cube_difference(a, b) == model.cube(b)-model.cube(a) > 0
        assert a*a+a*b+b*b == (a+b/2)**2+3*b*b/4 > 0
    with pytest.raises(ValueError, match="a < b"):
        model.cube_difference(0, 0)


def test_two_axes_share_horizontal_map_but_not_vertical_meaning(model):
    mapping = read("mathematics-v001.json")["mapping"]
    for x in (-2, -1.3, -1, 0, .7, 1, 2):
        state = model.linked_state(x)
        assert state["curve_point"][0] == state["derivative_point"][0] == mapping["x_offset"]+mapping["x_scale"]*x
        assert state["curve_point"][1] == pytest.approx(mapping["f_y_offset"]+mapping["f_y_scale"]*state["f"])
        assert state["derivative_point"][1] == pytest.approx(mapping["df_y_offset"]+mapping["df_y_scale"]*state["df"])
        left, right = model.tangent_endpoints(x)
        screen_slope = (right[1]-left[1])/(right[0]-left[0])
        assert screen_slope == pytest.approx(.15*state["df"])
        assert min(left[1], right[1]) > -3.1


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_values_rejected(model, bad):
    for fn in (model.function, model.derivative, model.linked_state, model.cube, model.cube_derivative):
        with pytest.raises(ValueError, match="finite"):
            fn(bad)


@pytest.mark.parametrize("bad", [True, "1", None, 1j])
def test_nonreal_values_rejected(model, bad):
    with pytest.raises(TypeError, match="real"):
        model.linked_state(bad)


def test_fixture_only_schema3_and_state_contracts():
    plan, draft = read("plan-v001.json"), read("narration-v001.json")
    assert plan["artifact_type"] == draft["artifact_type"] == "test_fixture"
    assert "sources" not in plan and "lesson_context" not in plan
    assert draft["schema_version"] == 3
    focuses = {row["id"]: row["cue"] for row in plan["focus_intents"]}
    assert {row["cue"] for row in draft["units"]} == {row["id"] for row in plan["cues"]}
    ids = []
    for unit in draft["units"]:
        assert set(unit) == {"id", "cue", "text", "references"}
        assert "".join(ref["text"] for ref in unit["references"]) == unit["text"]
        assert all(focuses[ref["focus"]] == unit["cue"] for ref in unit["references"])
        ids += [unit["id"], *(ref["id"] for ref in unit["references"])]
    assert len(ids) == len(set(ids))
    assert draft["audio_status"] == "not_generated"
    assert draft["alignment_status"] == "not_performed_no_acoustic_times"
    for state in plan["state_contracts"]:
        assert all(state[key] for key in ("writer", "consumers", "lifecycle", "invalidation"))
    assert not any(plan["production_boundary"][key] for key in ("rendered", "visual_approved", "narration_approved", "audio_generated", "published"))


@pytest.fixture(scope="module")
def native():
    from lesson_native_harness import load_lesson, native_run
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        lesson = load_lesson(SOURCE)
        with native_run(lesson, lesson.DerivativeMonotonicityLesson, read("plan-v001.json")) as scene:
            yield scene


def test_actual_native_clock_events_and_focus_lifecycle(native):
    plan = read("plan-v001.json")
    assert native.time == plan["duration"] == 324
    assert {r["id"] for r in native._closed_focus} == {r["id"] for r in plan["focus_intents"]}
    assert not native._open_focus
    from manimind.review.semantic_focus import focus_windows
    focus_windows({"duration": native.time, "windows": native._closed_focus}, native.time)
    windows = {r["id"]: r for r in native._closed_focus}
    marks = {r["id"]: r["time"] for r in native.visual_events}
    for focus, event in (("axes_meanings", "linked_axes_ready"), ("minus_one_horizontal", "left_boundary_reached"),
                         ("plus_one_horizontal", "right_boundary_reached"), ("interval_theorem", "interval_condition_ready"),
                         ("cube_zero_state", "cube_zero_tangent_ready"), ("cube_interval_reason", "cube_strict_increase_ready")):
        assert windows[focus]["start"] >= marks[event]


def test_every_native_frame_uses_same_x_for_all_linked_geometry(native, model):
    samples = [r for r in native.motion_samples if r["kind"] == "linked_graphs"]
    assert len(samples) > 2500
    for row in samples:
        assert row["curve_point"][0] == row["derivative_point"][0]
        assert row["f"] == pytest.approx(model.function(row["x"]))
        assert row["df"] == pytest.approx(model.derivative(row["x"]))
        left, right = row["tangent"]
        assert (right[1]-left[1])/(right[0]-left[0]) == pytest.approx(.15*row["df"])
        assert min(row["curve_point"][1], row["derivative_point"][1]) > -3.1


def test_motion_windows_contain_intermediate_states_and_end_after_motion(native):
    windows = {r["id"]: r for r in native._closed_focus}
    samples = [r for r in native.motion_samples if r["kind"] == "linked_graphs"]
    for name, low, high in (("left_interval_motion", -2, -1), ("middle_interval_motion", -1, 1),
                            ("right_interval_motion", 1, 2)):
        window = windows[name]
        rows = [r for r in samples if window["start"] < r["time"] <= window["end"]]
        assert any(low < r["x"] < high for r in rows)
        assert rows[-1]["x"] == pytest.approx(high)
    cube_rows = [r for r in native.motion_samples if r["kind"] == "cube_motion"]
    assert any(r["x"] < 0 for r in cube_rows)
    assert any(r["x"] == 0 for r in cube_rows)
    assert any(r["x"] > 0 for r in cube_rows)


def test_source_does_not_create_audio_or_claim_review():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"sound", "render", "publish", "add_sound"}
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "derivative_chapter_shared" in imported
    assert not any(name and "intro" in name for name in imported)
