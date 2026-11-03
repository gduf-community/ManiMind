"""Deterministic intent + native geometry smoke; no pixels, TeX, audio or approval."""

import ast
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
import pytest

from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.semantic_focus import focus_windows, validate_narration


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/projectile_integrated.py"
FIXTURE = ROOT / "tests/fixtures/projectile-integrated"


def data(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def pure_functions():
    nodes = [node for node in ast.parse(SOURCE.read_text()).body if isinstance(node, ast.FunctionDef)]
    namespace = {"math": math, "np": np}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("case", data("plan.json")["facts"]["cases"])
def test_upward_positive_model_matches_complete_landings(case):
    state = pure_functions()["flight_state"](case["h_m"], case["vx_m_s"], case["T_s"])
    assert state["y"] == 0
    assert state["drop"] == pytest.approx(case["h_m"])
    assert state["landing_time"] == pytest.approx(case["T_s"])
    assert state["range"] == pytest.approx(case["R_m"])
    assert state["vy"] == -10 * case["T_s"]


@pytest.mark.parametrize("args", [(0, 4, 1), (5, -1, 1), (5, 4, -1), (5, 4, float("nan")), (5, 4, 1, 0)])
def test_invalid_model_inputs_fail(args):
    with pytest.raises(ValueError):
        pure_functions()["flight_state"](*args)


def test_shared_slices_are_position_decompositions_in_original_coordinates():
    positions = pure_functions()["slice_positions"]
    for time in (.25, .5, .75, 1):
        for spread in np.linspace(0, 1, 31):
            common, points = positions(time, spread)
            assert common[0] == -5.10
            assert common[1] == pytest.approx(-1.55 + .6 * (5 - 5 * time * time))
            for speed, point in zip((4, 8), points):
                assert point[1] == common[1]
                assert point[0] - common[0] == pytest.approx(speed * time * spread)
    text = SOURCE.read_text()
    assert "横向展开不是实际运动" in text
    assert "同一时刻的位置分解" in text


def test_velocity_arrow_grows_and_equal_second_distances_are_unequal():
    functions = pure_functions()
    for time in np.linspace(0, 2, 61):
        start, end = functions["speed_arrow_ends"](time)
        assert end[0] == start[0] and end[1] <= start[1]
        assert np.linalg.norm(end - start) == pytest.approx(.085 * 10 * time)
    state = functions["flight_state"]
    assert state(20, 0, 1)["drop"] == 5
    assert state(20, 0, 2)["drop"] - state(20, 0, 1)["drop"] == 15
    assert "v_y=-10t" in SOURCE.read_text()


class MemoryPath:
    """Only actual sampler JSON writes are captured; nothing touches disk."""
    def __init__(self, files=None, name=""):
        self.files = {} if files is None else files
        self.name = name

    def __truediv__(self, name):
        return MemoryPath(self.files, name)

    def open(self, mode, **kwargs):
        if mode == "x" and self.name in self.files:
            raise FileExistsError(self.name)
        path = self

        class Stream(io.StringIO):
            def close(self):
                path.files[path.name] = self.getvalue()
                super().close()

        return Stream()

    def write_text(self, text, **kwargs):
        self.files[self.name] = text


@pytest.fixture(scope="module")
def native_module():
    """Load production classes with a tracked snapshot of their frozen helper."""
    patcher = pytest.MonkeyPatch()
    original = importlib.util.spec_from_file_location

    def spec(name, location, *args, **kwargs):
        if str(location).endswith("outputs/sol61-visual-first-20261024-v1/candidate.py"):
            location = FIXTURE / "frozen_candidate.py"
        return original(name, location, *args, **kwargs)

    patcher.setattr(importlib.util, "spec_from_file_location", spec)
    patcher.syspath_prepend(str(ROOT / "examples"))
    patcher.delitem(sys.modules, "projectile_formula_motion_full", raising=False)
    module_spec = original("integrated_native_test", SOURCE)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    yield module
    patcher.undo()


@pytest.fixture(scope="module")
def native_smoke(native_module):
    """Run inherited chapter control flow with native vectors, no GL camera.

    Rectangles stand in for glyphs, so this checks geometry/control flow, not
    actual font layout or visibility. Production samplers still execute.
    """
    import manimlib as gl
    import projectile_formula_motion as landing
    import projectile_formula_motion_full as full
    from manimind.experiments.understanding_support import UnderstandingScene
    from manimind.experiments.visual_first_support import VisualLessonScene
    from manimlib.animation.animation import prepare_animation

    patcher = pytest.MonkeyPatch()

    class Formula(gl.VGroup):
        def __init__(self, latex, tokens=None, font_size=38, **kwargs):
            self.latex = latex
            self.selectors = tokens or {}
            self.semantic_ids = tuple(self.selectors)
            unit = .065 * font_size / 38
            super().__init__(*(gl.Rectangle(width=unit * .8, height=.32 * font_size / 38,
                                           fill_opacity=1, stroke_width=0).move_to([index * unit, 0, 0])
                               for index in range(len(latex))))
            self.center()

        def get_tex(self):
            return self.latex

        def get_parts_by_tex(self, literal):
            return gl.VGroup(*(gl.VGroup(*self.submobjects[match.start():match.end()])
                               for match in re.finditer(re.escape(literal), self.latex)))

        def tag(self, identity):
            selector = self.selectors[identity]
            literal, occurrence = (selector, 0) if isinstance(selector, str) else selector
            return self.get_parts_by_tex(literal)[occurrence]

    class Number(gl.VGroup):
        def __init__(self, value=0, **kwargs):
            super().__init__(gl.Rectangle(width=.65, height=.3, fill_opacity=1))
            self.value = value
            self.decimals = kwargs.get("decimals", kwargs.get("num_decimal_places", 2))

        def set_value(self, value):
            self.value = value
            return self

    class Smoke(native_module.IntegratedLesson):
        def __init__(self):
            self.time, self.mobjects = 0., []
            self.out = MemoryPath()
            self.timeline = visual_timeline(data("plan.json"))
            self.cues = self.timeline["cues"]
            self.visual_events, self.sound_events = [], []
            self._open_focus, self._closed_focus = {}, []
            self.full_formula_frames, self.full_formula_events = [], []
            self.full_active, self.full_flights = {}, {}
            self._legacy_offset, self._reading_focus, self._chapter_id = None, None, None
            self._legacy_extra, self._height_step = 0., 0
            self.model_samples, self.conditions_seen, self.expansions, self.numbers = [], [], [], []

        def get_time(self):
            return self.time

        def add(self, *objects):
            for obj in objects:
                if not any(old is obj for old in self.mobjects):
                    self.mobjects.append(obj)
            return self

        def remove(self, *objects):
            self.mobjects = [obj for obj in self.mobjects if all(obj is not old for old in objects)]
            return self

        def cn(self, text, size=32, **kwargs):
            self.conditions_seen.append(str(text))
            return gl.Rectangle(width=max(.01, min(11., len(str(text)) * .11)), height=.3,
                                fill_opacity=1, stroke_width=0)

        def formula(self, latex, size=38, **kwargs):
            self.conditions_seen.append(latex)
            return Formula(latex, font_size=size)

        def number(self, value, **kwargs):
            number = Number(value, **kwargs)
            self.numbers.append(number)
            return number

        def play(self, *animations, run_time, **kwargs):
            start = self.time
            animations = [prepare_animation(animation) for animation in animations]
            for animation in animations:
                self.add(animation.mobject)
                animation.begin()
            for alpha in (0., .25, .5, .75, 1.):
                self.time = round(start + run_time * alpha, 9)
                for animation in animations:
                    animation.interpolate(alpha)
                for obj in list(self.mobjects):
                    obj.update(0)
                if self._chapter_id == "height_steps":
                    for animation in animations:
                        if isinstance(animation, gl.UpdateFromAlphaFunc):
                            arrows = [part for obj in self.mobjects for part in obj.get_family()
                                      if isinstance(part, gl.Arrow) and np.allclose(part.get_start(), [.45, 1.05, 0])]
                            self.model_samples.append({"clock": self.numbers[-2].value,
                                "velocity": self.numbers[-1].value, "point": animation.mobject.get_center().copy(),
                                "arrow": arrows[0].copy(), "decimals": [item.decimals for item in self.numbers[-2:]]})
                if self.full_active or self.full_flights:
                    self.full_formula_frames.append({"time": self.time,
                        "formulas": {key: self._snapshot(value) for key, value in self.full_active.items()}})
            for animation in animations:
                animation.finish()
                animation.clean_up_from_scene(self)
            self.time = round(start + run_time, 9)

        def wait(self, duration, **kwargs):
            self.time = round(self.time + duration, 9)

        def _expand_time_here(self, target, root):
            source = self.full_active["final_range"]
            self.expansions.append({key: np.linalg.norm(source.tag(key).get_center() - target.tag(key).get_center())
                                    for key in ("range", "eq", "speed")})
            super()._expand_time_here(target, root)

    def until(scene, absolute_seconds, *animations, **kwargs):
        assert absolute_seconds >= scene.time - 1e-6, (absolute_seconds, scene.time)
        scene.wait(max(0., absolute_seconds - scene.time))

    def visual_teardown(scene):
        validate_events(scene.timeline, {"duration": scene.time, "events": scene.visual_events})
        (scene.out / "visual-events.json").write_text(json.dumps({"duration": scene.time, "events": scene.visual_events}))

    patcher.setattr(full, "SemanticFormula", Formula)
    patcher.setattr(full, "matching_transform", lambda source, target, **kwargs: gl.Transform(source, target))
    patcher.setattr(full._frozen, "DecimalNumber", Number)
    patcher.setattr(landing, "SemanticFormula", Formula)
    patcher.setattr(VisualLessonScene, "until", until)
    patcher.setattr(VisualLessonScene, "tear_down", visual_teardown)
    scene = Smoke()
    try:
        scene.construct()
        scene.tear_down()
        yield scene
    finally:
        patcher.undo()


def test_full_inherited_control_flow_has_actual_clock_marks_and_focus(native_smoke):
    scene = native_smoke
    assert scene.time == 194
    assert not scene._open_focus and scene._legacy_offset is None
    assert len(scene.visual_events) >= 40
    inventory = data("handoff-inventory.json")
    assert [row["id"] for row in scene.visual_events] == [mark for cue in inventory["cues"] for mark in cue["marks"]]
    windows = focus_windows({"duration": scene.time, "windows": scene._closed_focus}, scene.time)
    assert set(windows) == {row["id"] for row in data("plan.json")["focus_intents"]}
    assert set(windows) == set(inventory["focus_ids"])
    validate_narration(data("narration-draft.json"), scene.timeline,
                       {"duration": scene.time, "windows": scene._closed_focus})
    for row in data("narration-draft.json")["segments"]:
        cue = next(cue for cue in scene.cues if cue["id"] == row["cue"])
        assert cue["start"] <= windows[row["focus"]]["start"] < windows[row["focus"]]["end"] <= cue["start"] + cue["duration"]
        assert row["focus"] != "prediction_space"


def test_complete_results_hold_before_height_algebra_and_slow_symbol_steps(native_smoke):
    events = {row["id"]: row["time"] for row in native_smoke.visual_events}
    assert events["both_landings_full_size_held"] - events["high_ball_landed"] == pytest.approx(5)
    transitions = [row for row in native_smoke.full_formula_events if row.get("name") in {"height_time", "height_range"}
                   and row["kind"] in {"matching_begin", "matching_end", "transport_begin", "transport_end"}]
    assert len(transitions) == 14
    for begin, end in zip(transitions[::2], transitions[1::2]):
        assert begin["time"] > events["both_landings_full_size_held"]
        assert end["time"] - begin["time"] == pytest.approx(1.4)
    assert events["height_scaling_verified"] - transitions[0]["time"] > 18


def test_both_motion_logs_keep_global_time_and_new_cue_boundaries(native_smoke):
    files = native_smoke.out.files
    assert {"motion-samples.json", "full-formula-motion.json", "visual-events.json", "focus-events.json"} <= files.keys()
    portable = json.loads(files["motion-samples.json"])
    full = json.loads(files["full-formula-motion.json"])
    assert portable["start"] == 60 and portable["duration"] == 20
    assert all(60 <= row["time"] <= 80 for row in portable["samples"])
    assert all(row["local_time"] == pytest.approx(row["time"] - 60, abs=1e-6) for row in portable["samples"])
    assert {route["stage"] for route in portable["routes"]} == {"relocated_term", "twice_height", "isolated_square"}
    assert full["cue_boundaries"] == data("plan.json")["cue_boundaries"]
    assert full["source_cue_boundaries"] == [0, 18, 38, 58, 74, 102, 114]
    assert full["duration"] == 194 and full["samples"] and full["events"]
    assert all(value < 1e-4 for value in native_smoke.expansions[0].values())
    assert full["events"][-1]["kind"] == "complete"


def test_actual_opening_retains_all_model_boundaries(native_smoke):
    text = " ".join(native_smoke.conditions_seen)
    assert all(token in text for token in ("质点", "匀强重力", "无空气阻力", "v_{y0}=0", "向上为正"))


def test_old_algebra_and_units_survive_in_actual_control_flow(native_smoke):
    events = native_smoke.full_formula_events
    vertical = [row for row in events if row.get("name") == "vertical"]
    assert "y_{10}" in vertical[0]["target"]["latex"]
    actual = [row["actual"]["latex"] for row in vertical if row["kind"] == "matching_end"]
    assert "{0}{t}" in actual[0]
    assert "{0}{t}" not in actual[1] and "{g}{t}" in actual[1]
    assert actual[2] == "y_1(t)=y_2(t)"
    products = next(row["formulas"] for row in events if row["kind"] == "substitute_products_end")
    assert all(r"\mathrm{m/s}\times{1}\,\mathrm{s}" in value["latex"] for value in products.values())
    canceled = [row for row in events if row["kind"] == "matching_end" and row.get("name") in {"range1", "range2"}]
    assert len(canceled) == 2
    assert all(r"\mathrm{m}" in row["actual"]["latex"] and r"\mathrm{s}" not in row["actual"]["latex"] for row in canceled)
    final = next(row for row in events if row["kind"] == "local_expansion_end")
    assert final["actual"]["latex"] == r"R=v_x\sqrt{\frac{{2}{h}}{{g}}}"


def test_actual_speed_updates_share_time_precision_sign_and_arrow(native_smoke):
    samples = native_smoke.model_samples
    assert len(samples) == 10
    assert {row["clock"] for row in samples} >= {0., 1., 2.}
    for row in samples:
        assert row["decimals"] == [2, 2]
        assert row["velocity"] == pytest.approx(-10 * row["clock"])
        assert row["point"][1] == pytest.approx(-1.65 + .18 * (20 - 5 * row["clock"] ** 2))
        if row["clock"]:
            length = np.linalg.norm(row["arrow"].get_end() - row["arrow"].get_start())
            assert length == pytest.approx(.085 * abs(row["velocity"]), abs=1e-5)


def test_plan_is_revision_with_all_seven_contract_functions_and_lifecycle():
    plan, contract = data("plan.json"), data("revision-contract.json")
    assert len(contract["units"]) == 7
    assert sum(len(row["features"]) for row in contract["units"]) == 30
    assert plan["revision_mode"] == "revision"
    assert plan["workflow_profile"] == "configs/visual-first-workflow-v3.json"
    assert plan["revision_contract"].endswith("/revision-contract.json")
    assert plan["revision_review"].endswith("/review-regression-v001.json")
    assert plan["duration"] == visual_timeline(plan)["duration"] == 194
    assert len(data("narration-draft.json")["segments"]) > 17
    assert data("narration-draft.json")["status"] == "semantic_intent_only_not_installed"
    assert "outputs/sol61-visual-first-20261024-v1/candidate.py" in plan["sources"]
    for row in plan["state_contracts"]:
        assert all(row.get(key) for key in ("writer", "consumers", "lifecycle", "invalidation"))


def test_real_scene_never_replaces_get_time_or_starts_external_work():
    tree = ast.parse(SOURCE.read_text())
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "get_time" not in methods
    assert not {"sound", "add_sound", "render", "assemble", "publish"} & methods
    assert "UnderstandingScene.tear_down(self)" in SOURCE.read_text()
    assert "source_cue_boundaries" in SOURCE.read_text()
    assert "self._legacy_extra += 1.4 - original_duration" in SOURCE.read_text()


def test_distance_sum_keeps_units_on_both_sides():
    formulas = [node.value for node in ast.walk(ast.parse(SOURCE.read_text()))
                if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert r"20\,\mathrm m=5\,\mathrm m+15\,\mathrm m" in formulas
    assert r"20=5+15\;\mathrm m" not in formulas
