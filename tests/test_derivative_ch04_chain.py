"""Chapter 04 fixture-only tests; no camera, audio, publication or approval."""

import ast
from fractions import Fraction
import json
from pathlib import Path
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch04_chain.py"
FIXTURE = ROOT / "tests/fixtures/derivative-ch04-chain"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def model():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             or isinstance(node, ast.Import) and any(item.name == "math" for item in node.names)
             or isinstance(node, ast.ImportFrom) and node.module == "numbers"]
    module = types.ModuleType("chain_pure_v001")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), module.__dict__)
    return module


def test_versioned_base_states(model):
    for state in read("mathematics-v001.json")["states"]:
        assert model.chain_state(state["x"]) == state


@pytest.mark.parametrize("h", [Fraction(-9, 10), Fraction(-1, 10), Fraction(-1, 1000),
                               Fraction(1, 1000), Fraction(1, 100), Fraction(1, 10)])
def test_exact_difference_quotient_factorization_and_remainders(model, h):
    increments = model.chain_increments(Fraction(1), h)
    du, dy = increments["du"], increments["dy"]
    assert du == h*(2+h) != 0
    assert dy == 12*du+6*du**2+du**3
    ratios = model.chain_ratios(Fraction(1), h)
    assert ratios["total_ratio"] == ratios["inner_ratio"]*ratios["outer_ratio"]
    assert ratios["inner_ratio"] == 2+h
    assert ratios["outer_ratio"] == 12+6*du+du**2


def test_golden_finite_ratios(model):
    row = read("mathematics-v001.json")["exact_ratio"]
    actual = model.chain_ratios(Fraction(row["x"]), Fraction(row["h"]))
    for name in ("inner_ratio", "outer_ratio", "total_ratio"):
        assert actual[name] == Fraction(row[name])


def test_limit_from_both_sides_and_zero_inner_rate(model):
    errors = []
    for denominator in (10, 100, 1000, 10000):
        errors.append(max(abs(model.chain_ratios(Fraction(1), sign*Fraction(1, denominator))["total_ratio"]-24)
                          for sign in (-1, 1)))
    assert all(a > b for a, b in zip(errors, errors[1:]))
    assert errors[-1] < Fraction(1, 100)
    assert model.chain_state(0)["total_rate"] == 0
    with pytest.raises(ValueError, match="du != 0"):
        model.chain_ratios(1, -2)
    with pytest.raises(ValueError, match="dx != 0"):
        model.chain_ratios(1, 0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_inputs_rejected(model, bad):
    for fn in (model.inner, model.outer, model.composite, model.chain_state,
               model.affine_fourth, model.affine_fourth_derivative):
        with pytest.raises(ValueError, match="finite"):
            fn(bad)


@pytest.mark.parametrize("bad", [True, "1", None, 1j])
def test_nonreal_inputs_rejected(model, bad):
    with pytest.raises(TypeError, match="real"):
        model.chain_state(bad)


def test_second_composite(model):
    for row in read("mathematics-v001.json")["affine"]:
        assert model.affine_fourth(row["x"]) == row["value"]
        assert model.affine_fourth_derivative(row["x"]) == row["derivative"]


@pytest.mark.parametrize("a,b", [(3, -1), (-2, 5), (0, 7), (1, 0)])
def test_linear_inner_exact_increment_including_zero(model, a, b):
    x, h = Fraction(2, 3), Fraction(-1, 100)
    assert model.affine_input(x+h, a, b)-model.affine_input(x, a, b) == model.affine_increment(h, a)
    if a == 0:
        assert model.affine_cube_derivative(x, a, b) == 0
    else:
        u = a*x+b
        assert model.affine_cube_derivative(x, a, b) == 3*u*u*a


def test_schema3_reference_concatenation_and_no_acoustic_claims():
    plan, draft = read("plan-v001.json"), read("narration-v001.json")
    assert draft["schema_version"] == 3
    focuses = {row["id"]: row["cue"] for row in plan["focus_intents"]}
    assert {row["cue"] for row in draft["units"]} == {row["id"] for row in plan["cues"]}
    for unit in draft["units"]:
        assert set(unit) == {"id", "cue", "text", "references"}
        assert "".join(ref["text"] for ref in unit["references"]) == unit["text"]
        assert all(focuses[ref["focus"]] == unit["cue"] for ref in unit["references"])
    assert draft["audio_status"] == "not_generated"
    assert draft["alignment_status"] == "not_performed_no_acoustic_times"
    assert all(plan["state_contracts"][0][key] for key in ("writer", "consumers", "lifecycle", "invalidation"))
    assert not plan["production_boundary"]["rendered"]
    assert "sources" not in plan


@pytest.fixture(scope="module")
def native():
    from lesson_native_harness import load_lesson, native_run
    import sys
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        lesson = load_lesson(SOURCE)
        with native_run(lesson, lesson.DerivativeChainLesson, read("plan-v001.json")) as scene:
            yield scene


def test_native_events_windows_and_total_duration(native):
    plan = read("plan-v001.json")
    assert native.time == plan["duration"] == 336
    expected = {r["id"] for r in plan["focus_intents"]}
    assert {r["id"] for r in native._closed_focus} == expected
    assert not native._open_focus
    assert all(row["start"] < row["end"] for row in native._closed_focus)
    from manimind.review.semantic_focus import focus_windows
    focus_windows({"duration": native.time, "windows": native._closed_focus}, native.time)


def test_successive_updates_complete_before_next_stage(native):
    rows = [row for row in native.motion_samples if row["kind"] == "chain_transfer"]
    input_rows = [r for r in rows if r["phase"] == "input"]
    inner_rows = [r for r in rows if r["phase"] == "inner"]
    outer_rows = [r for r in rows if r["phase"] == "outer"]
    assert all(r["u"] == 2 and r["y"] == 8 for r in input_rows)
    assert all(r["x"] == pytest.approx(1.1) and r["y"] == 8 for r in inner_rows)
    assert all(r["u"] == pytest.approx(2.21) for r in outer_rows)
    assert outer_rows[-1]["y"] == pytest.approx(10.793861)
    marks = {r["id"]: r["time"] for r in native.visual_events}
    windows = {r["id"]: r for r in native._closed_focus}
    assert windows["inner_change"]["start"] >= marks["input_change_complete"]
    assert windows["outer_change"]["start"] >= marks["inner_change_complete"]
    assert windows["transfer_complete"]["start"] > marks["outer_change_complete"]
    for focus, event in (("chain_rule", "chain_rule_ready"), ("affine_product", "affine_product_ready")):
        assert windows[focus]["start"] >= marks[event]


def test_no_forbidden_runtime_actions_or_old_intro_dependency():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "derivative_chapter_shared" in imported
    assert not any(name and "intro" in name for name in imported)
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"sound", "render", "publish", "add_sound"}
