"""Chapter-06 pure mathematics and camera-free native execution, not review."""

import ast
from fractions import Fraction
import json
from pathlib import Path
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch06_extrema.py"
FIXTURE = ROOT / "tests/fixtures/derivative-ch06-extrema"
PURE = {"finite", "cubic", "slope", "stationary_cubic", "local_difference", "turn", "graph_point"}


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
    module = types.ModuleType("chapter06_pure")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), module.__dict__)
    return module


def test_versioned_expected_values_and_signs(model):
    expected = read("model")["expected"]
    for x, value in expected["critical"]:
        assert model.cubic(x) == value
        assert model.slope(x) == 0
    for x, value in expected["sign_samples"]:
        assert model.slope(x) == value
    for left, right, kind in expected["turns"]:
        assert model.turn(left, right) == kind


@pytest.mark.parametrize("h", [Fraction(1, 100), Fraction(-1, 100), Fraction(2, 5), Fraction(-2, 5)])
def test_local_comparisons_are_exact_and_not_global(model, h):
    assert model.local_difference(-1, h) == model.cubic(-1+h)-2 < 0
    assert model.local_difference(1, h) == model.cubic(1+h)+2 > 0
    assert model.cubic(3) > 2
    assert model.cubic(-3) < -2


@pytest.mark.parametrize("r", [Fraction(1, 10), Fraction(1, 100), Fraction(1, 10000)])
def test_zero_slope_stationary_point_can_have_no_extremum(model, r):
    assert model.stationary_cubic(-r) < model.stationary_cubic(0) < model.stationary_cubic(r)
    assert 3*r*r > 0
    assert (model.stationary_cubic(r)-model.stationary_cubic(0))/r == r*r
    assert (model.stationary_cubic(-r)-model.stationary_cubic(0))/(-r) == r*r
    assert model.turn(1, 1) == "neither"


def test_cusp_extremum_has_no_equal_two_sided_derivative():
    h = Fraction(1, 100000)
    assert abs(-h) > abs(0) < abs(h)
    assert (abs(-h)-abs(0))/(-h) == -1
    assert (abs(h)-abs(0))/h == 1


@pytest.mark.parametrize("a", [-1, 1])
def test_necessity_explained_by_one_sided_quotients(model, a):
    h = Fraction(1, 1000)
    left = model.local_difference(a, -h)/(-h)
    right = model.local_difference(a, h)/h
    assert (left > 0 > right) if a == -1 else (left < 0 < right)
    assert abs(left) < Fraction(1, 100) and abs(right) < Fraction(1, 100)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite(model, bad):
    for fn in (model.cubic, model.slope, model.stationary_cubic):
        with pytest.raises(ValueError):
            fn(bad)


@pytest.mark.parametrize("bad", [True, None, "1", 1j])
def test_nonreal(model, bad):
    with pytest.raises(TypeError):
        model.cubic(bad)


def test_fixture_schema_provenance_and_draft_boundary():
    plan, narration = read("plan"), read("narration")
    assert 240 <= plan["duration"] <= 360
    assert plan["duration"] == sum(c["duration"] for c in plan["cues"])
    assert plan["fps"] == 30 and plan["resolution"] == [1920, 1080]
    assert plan["subtitle_safe_bottom_px"] == 96
    assert not any(plan["production_boundary"].values())
    for data in (plan, narration, read("model")):
        assert data["artifact_type"] == "test_fixture"
        assert data["fixture_version"] == 1
        assert not {"sources", "lesson_context", "audio_path"} & data.keys()
        assert all(data[k] for k in ("writer", "consumers", "lifecycle", "invalidation"))
    assert narration["schema_version"] == 3
    assert plan["author_agent"] == narration["author_context"] == "01a199e9-7432-7052-96f7-6bd6eb2e63bb"
    for unit in narration["units"]:
        assert set(unit) == {"id", "cue", "text", "references"}
        assert unit["text"] == "".join(r["text"] for r in unit["references"])
    focuses = {f["id"] for f in plan["focus_intents"]}
    assert focuses == {r["focus"] for u in narration["units"] for r in u["references"]}


def test_native_geometry_clock_and_referents_without_camera():
    from lesson_native_harness import load_lesson, native_run
    from manimind.experiments.visual_first_data import validate_events
    from manimind.review.meaning_units import validate_narration
    from manimind.review.semantic_focus import focus_windows
    module = load_lesson(SOURCE)
    with native_run(module, module.DerivativeCh06Extrema, read("plan")) as scene:
        assert scene.time == read("plan")["duration"] == 292
        validate_events(scene.timeline, {"duration": scene.time, "events": scene.visual_events})
        focuses = json.loads(scene.out.files["focus-events.json"])
        windows = focus_windows(focuses, scene.time)
        validate_narration(read("narration"), scene.timeline, focuses)
        assert set(windows) == {f["id"] for f in read("plan")["focus_intents"]}
        rows = [r for r in scene.motion_samples if r["kind"] == "local_window"]
        assert min(r["center"] for r in rows) == pytest.approx(-1)
        assert max(r["center"] for r in rows) == pytest.approx(1)
        assert all(r["point"][1] > -3.05 for r in rows)
        stationary = [r for r in scene.motion_samples if r["kind"] == "stationary_pass"]
        assert stationary[0]["x"] == pytest.approx(-1.2)
        assert stationary[-1]["x"] == pytest.approx(1.2)
        assert not scene._open_focus
