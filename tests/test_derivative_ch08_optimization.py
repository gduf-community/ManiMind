"""Chapter-08 pure geometry/math and camera-free native execution, not review."""

import ast
from fractions import Fraction
import json
import math
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch08_optimization.py"
FIXTURE = ROOT / "tests/fixtures/derivative-ch08-optimization"
PURE = {"finite", "dimensions", "volume", "derivative", "feasible", "optimum", "panel_vertices", "projected", "net_point"}


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
    module = types.ModuleType("chapter08_pure")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), module.__dict__)
    return module


def test_versioned_values_dimensions_and_optima(model):
    fixture = read("model")["expected"]
    assert fixture["sheet_side_cm"] == 12
    for x, volume in fixture["samples"]:
        assert model.volume(x) == volume
    for x, derivative in fixture["derivative_samples"]:
        assert model.derivative(x) == derivative
    for key, height in (("original", 0), ("constrained", 3)):
        expected = fixture[key]
        result = model.optimum(height)
        assert result["x_cm"] == expected["x_cm"]
        assert result["dimensions_cm"] == tuple(expected["dimensions_cm"])
        assert result["volume_cm3"] == expected["volume_cm3"]


@pytest.mark.parametrize("x", [Fraction(1, 10), Fraction(1), Fraction(2), Fraction(5, 2), Fraction(3), Fraction(59, 10)])
def test_all_derivative_algebra_and_exact_global_peak(model, x):
    assert model.derivative(x) == (12-2*x)**2-4*x*(12-2*x) == (12-2*x)*(12-6*x)
    assert 128-model.volume(x) == 4*(x-2)**2*(8-x) >= 0
    if x != 2:
        assert model.volume(x) < 128
    assert (model.derivative(x) > 0) if x < 2 else (model.derivative(x) <= 0)


def test_domains_include_only_realizable_boxes_and_new_height_boundary(model):
    assert not model.feasible(0) and not model.feasible(6)
    assert model.feasible(2) and not model.feasible(2, 3)
    assert model.feasible(3, 3) and model.feasible(Fraction(599, 100), 3)
    assert not model.feasible(6, 3)
    assert model.derivative(3) == -36 != 0
    for x in (Fraction(3), Fraction(7, 2), Fraction(4), Fraction(5), Fraction(599, 100)):
        assert model.derivative(x) < 0
        assert model.volume(x) <= 108
    assert model.volume(3) == 108 < model.volume(2) == 128


def test_both_degenerate_limits_approach_zero_without_fake_physical_box(model):
    for denominator in (100, 1000, 10000):
        h = Fraction(1, denominator)
        assert 0 < model.volume(h) < 144*h
        assert 0 < model.volume(6-h) < 24*h*h
    assert model.volume(0) == model.volume(6) == 0
    for boundary in (0, 6):
        with pytest.raises(ValueError):
            model.dimensions(boundary)
        with pytest.raises(ValueError):
            model.panel_vertices(boundary, 0)


@pytest.mark.parametrize("x", [Fraction(1), Fraction(2), Fraction(3), Fraction(9, 2)])
@pytest.mark.parametrize("angle", [0, math.pi/8, math.pi/4, math.pi/2])
def test_native_panel_model_preserves_real_lengths_and_fixed_hinges(model, x, angle):
    faces = model.panel_vertices(x, angle)
    assert len(faces) == 5
    length = 12-2*x
    for name, face in faces.items():
        edge = lambda a, b: math.sqrt(sum((u-v)**2 for u, v in zip(a, b)))
        assert edge(face[0], face[1]) == pytest.approx(length)
        assert edge(face[1], face[2]) == pytest.approx(length if name == "base" else x)
        assert face[0][2] == face[1][2] == 0
        if name != "base":
            assert face[2][2] == pytest.approx(float(x)*math.sin(angle))
    flat = model.panel_vertices(x, 0)
    folded = model.panel_vertices(x, math.pi/2)
    for name in faces:
        assert flat[name][:2] == folded[name][:2]
        for point in faces[name]:
            screen = model.projected(point, x)
            assert all(math.isfinite(t) for t in screen)
            assert -6.5 < screen[0] < .3 and -3.05 < screen[1] < 2.8
    assert max(p[2] for name in folded for p in folded[name]) == pytest.approx(float(x))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite(model, bad):
    for fn in (model.volume, model.derivative, model.optimum):
        with pytest.raises(ValueError):
            fn(bad)


@pytest.mark.parametrize("bad", [True, None, "2", 1j])
def test_nonreal(model, bad):
    with pytest.raises(TypeError):
        model.volume(bad)


@pytest.mark.parametrize("bad", [-1, 6, 7])
def test_invalid_height_requirement(model, bad):
    with pytest.raises(ValueError):
        model.optimum(bad)


@pytest.mark.parametrize("bad", [-.1, math.pi])
def test_fold_angles_are_not_arbitrary_physics(model, bad):
    with pytest.raises(ValueError):
        model.panel_vertices(2, bad)


def test_fixture_contracts_and_continuous_meaning_units():
    plan, narration = read("plan"), read("narration")
    assert plan["duration"] == sum(c["duration"] for c in plan["cues"]) == 312
    assert plan["subtitle_safe_bottom_px"] == 96
    assert not any(plan["production_boundary"].values())
    assert plan["author_agent"] == narration["author_context"] == "01a199e9-7432-7052-96f7-6bd6eb2e63bb"
    for data in (plan, narration, read("model")):
        assert data["artifact_type"] == "test_fixture" and data["fixture_version"] == 1
        assert not {"sources", "lesson_context", "audio_path"} & data.keys()
        assert all(data[k] for k in ("writer", "consumers", "lifecycle", "invalidation"))
    assert narration["schema_version"] == 3
    assert all(u["text"] == "".join(r["text"] for r in u["references"]) for u in narration["units"])


def test_native_fold_boundary_and_new_constraint_without_camera():
    from lesson_native_harness import load_lesson, native_run
    from manimind.review.meaning_units import validate_narration
    from manimind.review.semantic_focus import focus_windows
    module = load_lesson(SOURCE)
    with native_run(module, module.DerivativeCh08Optimization, read("plan")) as scene:
        assert scene.time == 312
        focuses = json.loads(scene.out.files["focus-events.json"])
        validate_narration(read("narration"), scene.timeline, focuses)
        windows = focus_windows(focuses, scene.time)
        assert set(windows) == {f["id"] for f in read("plan")["focus_intents"]}
        folds = [r for r in scene.motion_samples if r["kind"] == "fold"]
        assert folds[0]["angle"] == 0 and folds[-1]["angle"] == pytest.approx(math.pi/2)
        assert all(r["x_cm"] == 2 for r in folds)
        bounds = [r for r in scene.motion_samples if r["kind"] == "boundary_box"]
        assert min(r["x_cm"] for r in bounds) == pytest.approx(.08)
        assert max(r["x_cm"] for r in bounds) == pytest.approx(5.92)
        constrained = [r for r in scene.motion_samples if r["kind"] == "constrained_box"]
        assert constrained[0]["x_cm"] == 2 and constrained[0]["feasible"] is False
        assert constrained[-1]["x_cm"] == 3 and constrained[-1]["volume_cm3"] == 108
        assert any(r["x_cm"] == 4.5 for r in constrained)
        assert all(r["feasible"] == (r["x_cm"] >= 3) for r in constrained)
        assert not scene._open_focus
