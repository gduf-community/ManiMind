"""Portable mathematics and native interpolation, never render approval."""

import ast
from fractions import Fraction
import json
import math
from pathlib import Path

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.semantic_focus import focus_windows, validate_narration


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/pi_bounds_visual.py"
FIXTURE = ROOT / "tests/fixtures/pi-bounds-visual"


def data(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def module():
    return load_lesson(SOURCE)


def test_root_enclosures_are_exact_rational_inequalities(module):
    for value in (Fraction(0), Fraction(1), Fraction(3, 4), Fraction(1, 13), Fraction(7, 2)):
        low, high = module.root_interval(value)
        assert low * low <= value <= high * high
        assert high - low <= Fraction(1, 10 ** 60)
    with pytest.raises(ValueError):
        module.root_interval(-1)


def test_seed_geometry_recurrence_and_monotone_bounds(module):
    rows = module.geometric_bounds(9)
    assert [r["n"] for r in rows] == [6 * 2 ** k for k in range(10)]
    assert rows[0]["a"] == (Fraction(1, 2), Fraction(1, 2))
    assert rows[0]["lower"] == 3
    for row in rows:
        a, b = row["a"], row["b"]
        assert a[0] ** 2 + b[0] ** 2 <= 1 <= a[1] ** 2 + b[1] ** 2
        assert 0 < a[0] <= a[1] < 1
        assert 0 < b[0] <= b[1] < 1
        assert row["lower"] < Fraction(str(math.pi)) < row["upper"]
        # Trigonometry is a TEST oracle only, never the bound producer.
        angle = math.pi / row["n"]
        assert float(row["lower"]) == pytest.approx(row["n"] * math.sin(angle), abs=1e-12)
        assert float(row["upper"]) == pytest.approx(row["n"] * math.tan(angle), abs=1e-12)
    for old, new in zip(rows, rows[1:]):
        assert old["lower"] < new["lower"] < new["upper"] < old["upper"]
        assert new["a"][0] ** 2 <= (1 - old["b"][1]) / 2
        assert new["a"][1] ** 2 >= (1 - old["b"][0]) / 2
        assert new["b"][0] ** 2 <= (1 + old["b"][0]) / 2
        assert new["b"][1] ** 2 >= (1 + old["b"][1]) / 2


def test_every_displayed_decimal_rounds_outward_and_final_cell_is_stable(module):
    for row in module.geometric_bounds(9):
        for places in (0, 5, 6, 7, 12):
            low, high = map(Fraction, module.outward_text(row, places))
            assert low <= row["lower"] < row["upper"] <= high
            unit = Fraction(1, 10 ** places)
            assert row["lower"] - low < unit
            assert high - row["upper"] < unit
    final = module.geometric_bounds(9)[-1]
    low, high = map(Fraction, module.outward_text(final, 7))
    assert Fraction("3.141585") < low < high < Fraction("3.141595")
    assert high - low > 0
    for endpoint in (low, high):
        rounded = (endpoint * 100000 + Fraction(1, 2)).numerator // (endpoint * 100000 + Fraction(1, 2)).denominator
        assert rounded == 314159


@pytest.mark.parametrize("n", [6, 12, 24, 48, 96])
def test_actual_polygon_counts_nested_vertices_and_tangent_distance(module, n):
    points = module.polygon_points(n)
    assert points.shape == (n, 3)
    assert np.linalg.norm(points[:, :2], axis=1) == pytest.approx(np.ones(n))
    finer = module.polygon_points(2 * n)
    assert all(np.min(np.linalg.norm(finer - p, axis=1)) < 1e-12 for p in points)
    outer = module.polygon_points(n, True)
    for p, q in zip(outer, np.roll(outer, -1, axis=0)):
        edge = q - p
        distance = abs(p[0] * edge[1] - p[1] * edge[0]) / np.linalg.norm(edge)
        assert distance == pytest.approx(1)
    center = [0., 0., 0.]
    scene = module.PiBoundsLesson.__new__(module.PiBoundsLesson)
    assert len(scene.polygon(n, center)) == n
    assert len(scene.polygon(n, center, outer=True)) == n


def path_length(points):
    return np.linalg.norm(np.diff(points, axis=0), axis=1).sum()


def test_local_triangle_inequalities_explain_both_directions(module):
    splits = [module.chord_split(t) for t in np.linspace(0, 1, 61)]
    cuts = [module.corner_cut(t) for t in np.linspace(0, 1, 61)]
    assert np.all(np.diff([path_length(p) for p in splits]) > 0)
    assert np.all(np.diff([path_length(p) for p in cuts]) < 0)
    assert all(np.allclose(p[[0, 2]], splits[0][[0, 2]]) for p in splits)
    assert all(np.allclose(p[[0, 2]], cuts[0][[0, 2]]) for p in cuts)
    assert path_length(cuts[-1]) == pytest.approx(np.linalg.norm(cuts[-1][2] - cuts[-1][0]))
    p, _, q = cuts[-1]
    assert p[0] == q[0] == 1
    # The old two lines really are tangents at the old chord endpoints.
    a, _, b = splits[0]
    v = cuts[0][1]
    assert np.dot(a, v - a) == pytest.approx(0)
    assert np.dot(b, v - b) == pytest.approx(0)


def test_no_unknown_pi_can_enter_numeric_producer(module, monkeypatch):
    expected = [module.outward_text(row) for row in module.geometric_bounds()]
    # Layout functions may use pi; numerical bounds must survive a poisoned pi.
    with monkeypatch.context() as patch:
        patch.setattr(math, "pi", float("nan"))
        for name in ("sin", "cos", "tan", "asin", "acos", "atan"):
            patch.setattr(math, name, lambda *_: pytest.fail("Trigonometry entered numerical bound production"))
        assert [module.outward_text(row) for row in module.geometric_bounds()] == expected


@pytest.fixture(scope="module")
def native_scene(module):
    with native_run(module, module.PiBoundsLesson, data("plan.json")) as scene:
        yield scene


def test_native_frame_clock_cues_events_and_focus_close(native_scene):
    scene, plan = native_scene, data("plan.json")
    assert scene.time == plan["duration"] == 226
    assert scene.frame == 6780
    assert not scene._open_focus
    validate_events(scene.timeline, {"duration": scene.time, "events": scene.visual_events})
    windows = {"duration": scene.time, "windows": scene._closed_focus}
    measured = focus_windows(windows, scene.time)
    assert set(measured) == {row["id"] for row in plan["focus_intents"]}
    validate_narration(data("narration-draft-v001.json"), scene.timeline, windows)
    for row in data("narration-draft-v001.json")["segments"]:
        cue = next(c for c in scene.cues if c["id"] == row["cue"])
        window = measured[row["focus"]]
        assert cue["start"] <= window["start"] < window["end"] <= cue["start"] + cue["duration"]
    for cue in scene.cues:
        plays = [p for p in scene.plays if cue["start"] <= p["start"] < cue["start"] + cue["duration"]]
        assert min(p["start"] for p in plays) == pytest.approx(cue["start"])
        assert max(p["end"] for p in plays) <= cue["start"] + cue["duration"]
    report = json.loads(scene.out.files["focus-events.json"])
    assert report["duration"] == 226
    assert report["windows"] == scene._closed_focus


def test_native_runs_both_local_interpolations(module, monkeypatch):
    sampled = {"chord_split": [], "corner_cut": []}
    for name in sampled:
        original = getattr(module, name)

        def probe(alpha, original=original, name=name):
            result = original(alpha)
            sampled[name].append((alpha, path_length(result)))
            return result

        monkeypatch.setattr(module, name, probe)
    with native_run(module, module.PiBoundsLesson, data("plan.json")):
        pass
    for name in sampled:
        values = sampled[name]
        assert len(values) >= 121
        assert any(0 < alpha < 1 for alpha, _ in values)
        assert any(alpha == 1 for alpha, _ in values)


def test_native_inventory_and_scope_are_portable(native_scene):
    scene, plan = native_scene, data("plan.json")
    inventory = {"duration": scene.time, "frames": scene.frame, "fps": 30,
                 "visual_events": scene.visual_events, "focus_windows": scene._closed_focus,
                 "evidence_type": "native interpolation with vector text/TeX placeholders; no renderer or pixels"}
    assert inventory == data("native-clock.json")
    assert plan["native_clock_check"]["actual_focus_windows"] == scene._closed_focus
    assert plan["native_clock_check"]["actual_visual_events"] == scene.visual_events
    assert plan["revision_mode"] == "fresh"
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v3.1.json"
    for row in plan["state_contracts"]:
        assert all(row.get(key) for key in ("writer", "consumers", "lifecycle", "invalidation"))
    tree = ast.parse(SOURCE.read_text())
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    assert len(classes) == 1 and classes[0].bases[0].id == "UnderstandingScene"
    methods = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not methods & {"get_time", "get_time_progression", "render", "publish", "sound", "play", "wait"}
    assert not any(text in SOURCE.read_text() for text in ("outputs/", "projectile_", "subprocess", "ssh"))
    labels = " ".join(scene.labels)
    assert all(text not in labels for text in ("仅示意", "仅供参考", "模型时钟", "重置", "待审核"))
    assert "计算表" in labels
    assert "圆周长仍在区间" not in labels
    assert "π仍在区间里" in labels
    assert scene.timeline == visual_timeline(plan)
