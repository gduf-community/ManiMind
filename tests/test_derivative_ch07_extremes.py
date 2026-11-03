"""Pure interval model plus camera-free native clock; no production reads."""

import ast
from fractions import Fraction
import json
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch07_extremes.py"
FIXTURE = ROOT / "tests/fixtures/derivative-ch07-extremes"
PURE = {"finite", "value", "candidates", "closed_extremes", "open_extremes", "graph_point"}


def read(name):
    return json.loads((FIXTURE / f"{name}-v001.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def isolate_production():
    original = Path.open

    def guarded(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT / "runtime/projects"):
            raise AssertionError("Production project access is forbidden in chapter tests")
        return original(path, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Path, "open", guarded)
        yield


@pytest.fixture(scope="module")
def model():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if
             isinstance(n, ast.Import) and any(a.name == "math" for a in n.names)
             or isinstance(n, ast.ImportFrom) and n.module == "numbers"
             or isinstance(n, ast.FunctionDef) and n.name in PURE]
    module = types.ModuleType("chapter07_pure")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), module.__dict__)
    return module


def test_closed_candidates_and_result(model):
    expected = read("model")["expected"]["closed"]
    assert model.candidates(0, 3) == tuple(map(tuple, expected["candidates"]))
    result = model.closed_extremes(0, 3)
    assert result["minimum"] == 0 and result["maximum"] == 4
    assert result["argmin"] == (1,) and result["argmax"] == (3,)


@pytest.mark.parametrize("a,b", [(0, 1), (1, 3), (-3, -1), (2, 4), (-2, 4)])
def test_candidates_do_not_duplicate_vertex_at_endpoint(model, a, b):
    rows = model.candidates(a, b)
    assert len({x for x, y in rows}) == len(rows)
    assert {a, b} <= {x for x, y in rows}
    assert (1 in {x for x, y in rows}) == (a <= 1 <= b)


def test_parameter_switch_and_two_argmaxes(model):
    for b, maximum, winners in read("model")["expected"]["parameters"]:
        result = model.closed_extremes(0, b)
        assert result["minimum"] == 0 and result["argmin"] == (1,)
        assert result["maximum"] == maximum
        assert result["argmax"] == tuple(winners)
    result = model.closed_extremes(0, 2)
    assert result["maximum"] == 1 and result["argmax"] == (0, 2)


def test_same_open_function_has_minimum_and_unattained_supremum_four_not_nine(model):
    result = model.open_extremes(0, 3)
    expected = read("model")["expected"]["open"]
    assert result["supremum"] == expected["supremum"] == 4 != 9
    assert result["minimum"] == expected["minimum"] == 0
    assert result["argmin"] == (1,) and model.value(1) == 0
    assert result["maximum"] is None and result["argmax"] == ()
    for denominator in (10, 100, 1000, 10000):
        h = Fraction(1, denominator)
        x = 3-h
        assert 0 <= model.value(x) < 4
        assert model.value(x) == 4-4*h+h*h
        assert model.value(x) < model.value(3-h/2) < 4


@pytest.mark.parametrize("a,b", [(0, .5), (1, 3), (2, 3)])
def test_open_interval_without_vertex_has_no_attained_minimum(model, a, b):
    result = model.open_extremes(a, b)
    assert result["minimum"] is None and result["argmin"] == ()
    assert result["maximum"] is None


@pytest.mark.parametrize("a,b", [(0, 0), (3, 0)])
def test_bad_interval(model, a, b):
    with pytest.raises(ValueError):
        model.candidates(a, b)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite(model, bad):
    with pytest.raises(ValueError):
        model.candidates(0, bad)


@pytest.mark.parametrize("bad", [True, None, "3", 1j])
def test_nonreal(model, bad):
    with pytest.raises(TypeError):
        model.value(bad)


def test_fixture_contracts_are_not_production():
    plan, narration = read("plan"), read("narration")
    assert plan["duration"] == sum(c["duration"] for c in plan["cues"]) == 276
    assert plan["subtitle_safe_bottom_px"] == 96
    assert not any(plan["production_boundary"].values())
    assert plan["author_agent"] == narration["author_context"] == "01a199e9-7432-7052-96f7-6bd6eb2e63bb"
    for data in (plan, narration, read("model")):
        assert data["artifact_type"] == "test_fixture"
        assert data["fixture_version"] == 1
        assert not {"sources", "lesson_context", "audio_path"} & data.keys()
        assert all(data[k] for k in ("writer", "consumers", "lifecycle", "invalidation"))
    assert narration["schema_version"] == 3
    assert all(u["text"] == "".join(r["text"] for r in u["references"]) for u in narration["units"])


def test_native_parameter_and_open_approach_without_camera():
    from lesson_native_harness import load_lesson, native_run
    from manimind.review.meaning_units import validate_narration
    from manimind.review.semantic_focus import focus_windows
    module = load_lesson(SOURCE)
    with native_run(module, module.DerivativeCh07Extremes, read("plan")) as scene:
        assert scene.time == 276
        focuses = json.loads(scene.out.files["focus-events.json"])
        validate_narration(read("narration"), scene.timeline, focuses)
        windows = focus_windows(focuses, scene.time)
        assert set(windows) == {f["id"] for f in read("plan")["focus_intents"]}
        rows = [r for r in scene.motion_samples if r["kind"] == "moving_endpoint"]
        assert rows[0]["b"] == pytest.approx(1.25)
        assert rows[-1]["b"] == pytest.approx(3)
        assert any(r["b"] == 2 and r["argmax"] == (0, 2) for r in rows)
        for row in rows:
            assert row["minimum"] == 0 and row["argmin"] == (1,)
            assert row["endpoint"][1] > -3.05
        approach = [r for r in scene.motion_samples if r["kind"] == "open_approach"]
        assert approach[0]["x"] == pytest.approx(2.2)
        assert approach[-1]["x"] == pytest.approx(2.99)
        assert all(r["x"] < 3 and 0 < r["gap"] and r["value"] < 4 for r in approach)
        assert not scene._open_focus
