"""Native 30-fps interpolation only: no renderer, TeX, voice or pixel claims."""

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.semantic_focus import focus_windows, validate_narration
from test_projectile_paced import native_smoke as paced_native_smoke
from test_projectile_integrated import MemoryPath


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/projectile_nonlinear.py"
FIXTURE = ROOT / "tests/fixtures/projectile-nonlinear"


def data(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def clock_inventory(scene):
    return {"duration": scene.time, "fps": 30, "frames": scene.frame,
            "chapter_events": [e for e in scene.full_formula_events
                               if e["kind"] in {"chapter_begin", "chapter_end"}],
            "focus_windows": scene._closed_focus,
            "visual_events": scene.visual_events,
            "nonlinear_sample_count": len(scene.nonlinear_samples),
            "formula_sample_count": len(scene.full_formula_frames),
            "landing_sample_count": len(json.loads(scene.out.files["motion-samples.json"])["samples"]),
            "evidence_type": "native 30fps interpolation with mocked text/TeX geometry; no renderer or pixels"}


@pytest.fixture(scope="module")
def physics():
    tree = ast.parse(SOURCE.read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    scope = {"math": __import__("math")}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), scope)
    return scope


def test_free_fall_sign_units_and_interval_distance(physics):
    fall, interval = physics["fall_state"], physics["interval_distance"]
    assert [fall(t)["vy"] for t in (0, 1, 2)] == [0, -10, -20]
    assert [fall(t)["speed"] for t in (0, 1, 2)] == [0, 10, 20]
    for lo, average, distance in ((0, 5, 5), (1, 15, 15)):
        result = interval(lo, lo + 1)
        assert result["average_speed"] == average
        assert result["distance"] == distance
        assert result["units"] == {"average_speed": "m/s", "duration": "s", "distance": "m"}
    for g in (1.6, 9.81, 10):
        for t in (.2, .75, 1.5):
            assert fall(2 * t, g)["drop"] == pytest.approx(4 * fall(t, g)["drop"])
            assert interval(.1, t, g)["distance"] == pytest.approx(fall(t, g)["drop"] - fall(.1, g)["drop"])


@pytest.mark.parametrize("t,g", [(-1, 10), (float("nan"), 10), (1, 0), (1, float("inf"))])
def test_invalid_physical_inputs(physics, t, g):
    with pytest.raises(ValueError):
        physics["fall_state"](t, g)


def test_equal_time_positions_are_actual_parabolas(physics):
    positions = physics["simultaneous_positions"]
    for speed_index, speed in enumerate((4, 8)):
        points = np.array([positions(t)[speed_index] for t in np.linspace(0, 1, 5)])
        assert np.diff(points[:, 0]) == pytest.approx(np.repeat(speed / 4, 4))
        assert np.all(np.diff(-np.diff(points[:, 1])) > 0)
    assert all(positions(t)[0][1] == positions(t)[1][1] for t in np.linspace(0, 1, 31))
    for t in (-.01, 1.01, float("nan")):
        with pytest.raises(ValueError):
            positions(t)
    with pytest.raises(ValueError):
        physics["interval_distance"](1, 1)


@pytest.fixture(scope="module")
def native_smoke(paced_native_smoke):
    # Reuse the existing native Scene.play/wait harness and semantic placeholders.
    # Its frozen candidate is redirected to the existing portable fixture only.
    import projectile_nonlinear as nonlinear
    import projectile_formula_motion_full as full

    harness = type(paced_native_smoke.scene)

    class Smoke(nonlinear.NonlinearLesson):
        __init__ = harness.__init__
        add, remove = harness.add, harness.remove
        formula, number = harness.formula, harness.number

        def cn(self, text, size=32, color="#EEF1F4"):
            # Apply the production display adapters before substituting geometry.
            import projectile_precise as precise
            if text == "理想模型：质点 · 匀强重力 · 无空气阻力":
                text = "小球视为质点，忽略空气阻力，重力加速度不变"
            return harness.cn(self, precise.display_term(text), size=size, color=color)

    scene = Smoke()
    scene.timeline = visual_timeline(data("plan.json"))
    scene.cues = scene.timeline["cues"]
    scene.out = MemoryPath()
    scene.nonlinear_samples, scene._nonlinear_probe = [], None
    # The inherited fixture patches both semantic matching and full formulas.
    assert full.SemanticFormula.__name__ == "Formula"
    scene.construct()
    scene.tear_down()
    return scene


def test_native_clock_cues_and_focus(native_smoke):
    scene, plan = native_smoke, data("plan.json")
    assert scene.time == pytest.approx(plan["duration"])
    validate_events(scene.timeline, {"duration": scene.time, "events": scene.visual_events})
    assert scene.frame == round(plan["duration"] * 30)
    for cue in scene.cues:
        rows = [row for row in scene.plays if row["chapter"] == cue["id"]]
        assert min(row["start"] for row in rows) == pytest.approx(cue["start"])
        assert max(row["end"] for row in rows) <= cue["start"] + cue["duration"] + 1e-6
    measured = focus_windows({"duration": scene.time, "windows": scene._closed_focus}, scene.time)
    assert set(measured) == {row["id"] for row in plan["focus_intents"]}
    validate_narration(data("narration-draft.json"), scene.timeline,
                       {"duration": scene.time, "windows": scene._closed_focus})
    assert not scene._open_focus and scene._legacy_offset is None
    assert not scene._direct_steps and not scene._expansion_plays
    assert scene._nonlinear_probe is None
    for filename in ("full-formula-motion.json", "nonlinear-motion.json"):
        report = json.loads(scene.out.files[filename])
        assert report["duration"] == pytest.approx(scene.time)
        assert report["cue_boundaries"] == plan["cue_boundaries"]
    landing = json.loads(scene.out.files["motion-samples.json"])
    assert landing["start"] == pytest.approx(69.2)
    assert landing["duration"] == pytest.approx(39.5)


def test_actual_motion_rate_and_increasing_gaps(native_smoke):
    rows = native_smoke.nonlinear_samples
    motion = [row for row in rows if row["chapter"] == "recombine"]
    assert len(motion) >= 290
    for row in motion:
        t = row["physical_time"]
        a, b = row["ball_centers"]
        assert a[1] == pytest.approx(b[1])
        assert a[:2] == pytest.approx([-5.1 + 4 * t, -1.55 + .6 * (5 - 5 * t * t)])
        assert b[0] == pytest.approx(-5.1 + 8 * t)
    fall = [row for row in rows if row["chapter"] == "height_steps" and row["phase"] == "fall"]
    assert len(fall) > 500
    for row in fall:
        t = row["physical_time"]
        assert row["ball_center"][1] == pytest.approx(2.1 - .8 * t * t)
        assert row["cursor_center"][:2] == pytest.approx([-1.4 + 3.1 * t, -1.1 + 1.4 * t])
    ghosts = max((row["ghost_centers"] for row in fall), key=len)
    assert len(ghosts) == 5
    ys = np.array(ghosts)[:, 1]
    assert -np.diff(ys) == pytest.approx([.2, .6, 1., 1.4])


def test_semantic_formula_chains_and_visible_language(native_smoke):
    events = native_smoke.full_formula_events
    assert len([e for e in events if e["kind"] == "matching_end" and e.get("name") == "vertical"]) == 3
    for focus in ("height_substitution", "root_split", "root_four_evaluated", "original_time_identified",
                  "range_time_substitution", "range_factor_extracted", "original_range_identified",
                  "final_time_transport", "final_radical_expansion"):
        assert any(e["kind"] == "paced_step_begin" and e.get("focus") == focus for e in events)
    expansion = next(e for e in events if e["kind"] == "local_expansion_end")
    assert expansion["actual"]["latex"] == r"R=v_x\sqrt{\frac{{2}{h}}{{g}}}"
    labels = " ".join(native_smoke.labels)
    for forbidden in ("仅用于", "不是实际运动", "箭头表示速度，不是重力", "横速", "模型时钟", "重置", "待释放", "暂停", "倍慢放", "标尺"):
        assert forbidden not in labels
    assert "时间" in labels and "下落速率" in labels
    assert r"v_y=-gt" in labels and "15" in labels


def test_area_dissection_and_both_triangle_dimensions_are_live(native_smoke):
    def area(points):
        p = np.asarray(points)[:, :2]
        return abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1))) / 2

    rows = native_smoke.nonlinear_samples
    marks = {row["id"]: row["time"] for row in native_smoke.visual_events}
    for identity, expected in (("first_average_distance", 5), ("second_average_distance", 15)):
        proof = [row for row in rows if row.get("phase") == identity and row["proof_vertices"]]
        assert len(proof) > 200
        assert np.ptp([row["proof_vertices"]["cap"][1] for row in proof], axis=0).max() > .5
        for row in proof:
            assert sum(area(p) for p in row["proof_vertices"].values()) == pytest.approx(expected * 3.1 * .14)
        ready = marks[identity + "_rectangle_ready"]
        row = next(row for row in proof if row["time"] >= ready)
        points = np.vstack(list(row["proof_vertices"].values()))
        assert np.ptp(points[:, 0]) == pytest.approx(3.1)
        assert np.ptp(points[:, 1]) == pytest.approx(expected * .14)
    growing = [row for row in rows if "scale_factor" in row]
    assert len(growing) > 250
    for row in growing:
        k = row["scale_factor"]
        assert area(row["triangle_vertices"]) == pytest.approx(5 * 3.1 * .14 * k * k)
        assert np.linalg.norm(np.diff(row["base_ends"], axis=0)) == pytest.approx(3.1 * k)
        assert np.linalg.norm(np.diff(row["side_ends"], axis=0)) == pytest.approx(1.4 * k)


def test_measured_inventory_is_reproducible(native_smoke):
    assert clock_inventory(native_smoke) == data("native-clock-smoke.json")


def test_source_scope_and_handoff_contract():
    tree = ast.parse(SOURCE.read_text())
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert not {"get_time", "get_time_progression", "render", "sound", "publish"} & methods
    plan = data("plan.json")
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v3.1.json"
    assert plan["revision_contract"] == "runtime/projects/projectile-nonlinear-20261027/revision-contract.json"
    assert plan["revision_review"] == "runtime/sessions/projectile-nonlinear-20261027/review-regression-v002.json"
    assert {"examples/projectile_nonlinear.py", "examples/projectile_precise.py", "examples/projectile_paced.py",
            "examples/projectile_integrated.py", "examples/projectile_formula_motion_full.py",
            "examples/projectile_formula_motion.py", "outputs/sol61-visual-first-20261024-v1/candidate.py"} <= set(plan["sources"])
    for row in plan["state_contracts"]:
        assert all(row.get(key) for key in ("writer", "consumers", "lifecycle", "invalidation"))


def test_area_consequence_replaces_law_below_axis_label(native_smoke):
    event = next(row for row in native_smoke.full_formula_events
                 if row["kind"] == "matching_end"
                 and row.get("actual", {}).get("latex") == r"s(2T)=4s(T)")
    assert event["actual"]["position"][1] == pytest.approx(-2.85)
    assert event["actual"]["bounds"]["max"][1] < -2.5
    rows = [row for row in native_smoke.full_formula_frames
            if row["time"] >= event["time"]
            and row["formulas"].get("distance_law", {}).get("latex") == r"s(2T)=4s(T)"]
    assert rows[-1]["time"] - rows[0]["time"] >= 3
