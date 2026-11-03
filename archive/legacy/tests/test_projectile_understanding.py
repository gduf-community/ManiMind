"""Non-render regressions. The dry clock is not measured pixel evidence."""

import ast
import copy
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.semantic_focus import focus_windows, validate_narration


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/projectile_understanding.py"
PROJECT = ROOT / "tests/fixtures/projectile-understanding"


def data(name):
    return json.loads((PROJECT / name).read_text(encoding="utf-8"))


def source_tree():
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def physics():
    return geometry_functions()["flight_state"]


def geometry_functions():
    functions = [node for node in source_tree().body if isinstance(node, ast.FunctionDef)]
    namespace = {"math": math, "np": np}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("case", data("plan.json")["facts"]["cases"])
def test_physics_matches_structured_facts(case):
    result = physics()(case["h_m"], case["vx_m_s"], case["T_s"])
    assert result["drop"] == pytest.approx(case["h_m"])
    assert result["landing_time"] == pytest.approx(case["T_s"])
    assert result["range"] == pytest.approx(case["R_m"])


def test_equal_time_vertical_state_and_square_law():
    state = physics()
    for time in (0, .25, .5, .75, 1):
        a, b = state(5, 4, time), state(5, 8, time)
        assert a["drop"] == b["drop"]
        assert a["vy"] == b["vy"]
        assert b["x"] == 2 * a["x"]
    assert state(20, 4, 1)["drop"] == 5
    assert state(20, 4, 2)["drop"] - state(20, 4, 1)["drop"] == 15
    assert state(5, 4, 100)["time"] == 1
    with pytest.raises(ValueError):
        state(0, 4, 1)


class Shape:
    """Minimal geometry/animation double, deliberately no GL, font or TeX IO."""
    def __init__(self, *args, **kwargs):
        self.children = list(args)
        self.center = np.zeros(3)
        self.opacity = 1
        self.kind = kwargs.get("kind", "shape")
        self.start, self.end = np.zeros(3), np.zeros(3)
        if len(args) == 2 and all(isinstance(arg, np.ndarray) for arg in args):
            self.start, self.end = args[0].copy(), args[1].copy()

    def move_to(self, point):
        delta = np.array(point) - self.center
        for child in self.children:
            if isinstance(child, Shape):
                child.move_to(child.center + delta)
        self.center = np.array(point)
        return self

    def add(self, *items):
        self.children.extend(items)
        return self

    def set_value(self, value):
        self.value = value
        return self

    def set_opacity(self, opacity):
        self.opacity = opacity
        for child in self.children:
            if isinstance(child, Shape):
                child.set_opacity(opacity)
        return self

    def set_color(self, color):
        self.color = color
        return self

    def put_start_and_end_on(self, start, end):
        assert isinstance(start, np.ndarray) and isinstance(end, np.ndarray)
        self.start, self.end = start.copy(), end.copy()
        return self

    set_points_by_ends = put_start_and_end_on

    def get_center(self):
        return self.center.copy()

    def copy(self):
        return copy.deepcopy(self)

    def arrange(self, direction, buff):
        for index, child in enumerate(self.children):
            child.move_to(direction * index * (1.5 + buff))
        return self

    def tag(self, identity):
        assert identity == "time"
        return Shape().move_to(self.center + np.array([1., 0., 0.]))

    def __iter__(self):
        return iter(self.children)


class DryClock:
    def __init__(self):
        self.timeline = visual_timeline(data("plan.json"))
        self.cues = self.timeline["cues"]
        self.time = 0
        self.camera = SimpleNamespace()
        self._subtitle_driver = Shape()
        self.mobjects = [self._subtitle_driver]
        self.events, self.windows, self.open_focus = [], [], {}
        self.numbers, self.motion = [], []

    def cn(self, *args, **kwargs):
        return Shape()

    formula = cn
    def number(self, value, **kwargs):
        shape = Shape().set_value(value)
        self.numbers.append(shape)
        return shape

    def add(self, *objects):
        self.mobjects.extend(objects)

    def remove(self, *objects):
        self.mobjects = [old for old in self.mobjects if all(old is not obj for obj in objects)]

    def play(self, *animations, run_time, **kwargs):
        # Sample motion without invoking ManimGL or generating any media.
        assert run_time * 30 == pytest.approx(round(run_time * 30))
        for kind, obj, callback in animations:
            if callback:
                for alpha in np.linspace(0, 1, 31):
                    callback(obj, alpha)
                    self.motion.append({"play_start": self.time, "alpha": alpha,
                                        "name": callback.__name__, "point": obj.center.copy(),
                                        "children": [item.center.copy() for item in obj.children if isinstance(item, Shape)],
                                        "numbers": [item.value for item in self.numbers],
                                        "arrows": [{"start": item.start.copy(), "end": item.end.copy(), "opacity": item.opacity}
                                                   for item in self.mobjects if item.kind == "Arrow"]})
            if kind == "out":
                self.mobjects = [old for old in self.mobjects if old is not obj]
            elif obj not in self.mobjects:
                self.mobjects.append(obj)
        self.time = round(self.time + run_time, 9)

    def until(self, time):
        assert time >= self.time - 1e-7
        self.time = time

    def mark(self, identity):
        self.events.append({"id": identity, "time": self.time})

    def focus_begin(self, identity):
        assert identity not in self.open_focus
        assert identity not in {row["id"] for row in self.windows}
        self.open_focus[identity] = self.time

    def focus_end(self, identity):
        self.windows.append({"id": identity, "start": self.open_focus.pop(identity), "end": self.time})


def dry_scene():
    tree = source_tree()
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    namespace = {"math": math, "np": np, "UnderstandingScene": DryClock,
                 "color_to_rgba": lambda color: color, "UP": np.array([0, 1, 0]), "RIGHT": np.array([1, 0, 0])}
    namespace.update({name: (lambda *args, kind=name, **kwargs: Shape(*args, kind=kind, **kwargs))
                      for name in ("Group", "Line", "Arrow", "ParametricCurve", "Dot", "Circle", "SemanticFormula")})
    namespace.update({name: (lambda obj, kind=name: (kind, obj, None))
                      for name in ("FadeIn", "ShowCreation")})
    namespace["FadeOut"] = lambda obj: ("out", obj, None)
    namespace["UpdateFromAlphaFunc"] = lambda obj, callback: ("update", obj, callback)
    namespace["linear"] = lambda value: value
    exec(compile(tree, str(SOURCE), "exec"), namespace)
    scene = namespace["UnderstandingLesson"]()
    scene.construct()
    return scene


def test_all_authored_marks_and_focuses_fit_the_clock():
    scene = dry_scene()
    assert scene.time == 147
    assert not scene.open_focus
    validate_events(scene.timeline, {"duration": scene.time, "events": scene.events})
    report = {"duration": scene.time, "windows": scene.windows}
    windows = focus_windows(report, scene.time)
    assert set(windows) == {row["id"] for row in data("plan.json")["focus_intents"]}
    validate_narration(data("narration-draft.json"), scene.timeline, report)
    assert windows["same_height_result"]["end"] == 31.8
    assert windows["same_height_result"]["end"] - windows["same_height_result"]["start"] >= 10
    assert windows["prediction_space"]["end"] - windows["prediction_space"]["start"] >= 6
    for row in data("narration-draft.json")["segments"]:
        cue = next(cue for cue in scene.cues if cue["id"] == row["cue"])
        window = windows[row["focus"]]
        assert cue["start"] <= window["start"] < window["end"] < cue["start"] + cue["duration"]
        # No fixed character-rate proxy for natural speech. The lead must use
        # whole utterances and actual WAV lengths after independent first look.
    assert "prediction_space" not in {row["focus"] for row in data("narration-draft.json")["segments"]}


def test_review_samples_cover_every_cue_and_key_transitions():
    scene = dry_scene()
    times = data("plan.json")["review_times"]
    assert times == sorted(set(times))
    assert all(0 <= time < scene.time for time in times)
    for cue in scene.cues:
        assert cue["start"] in times
        assert any(cue["start"] + .3 * cue["duration"] <= time <= cue["start"] + .7 * cue["duration"] for time in times)
        assert any(cue["start"] + cue["duration"] - .3 <= time < cue["start"] + cue["duration"] for time in times)
    for event in scene.events:
        assert any(-1e-7 <= sample - event["time"] <= .7 for sample in times), event


def test_requested_pacing_and_construct_order_match():
    scene = dry_scene()
    assert [cue["duration"] for cue in scene.cues] == [7, 7, 18, 18, 20, 13, 26, 12, 13, 13]
    construct = next(node for node in ast.walk(source_tree()) if isinstance(node, ast.FunctionDef) and node.name == "construct")
    methods = [node.value.func.attr.removeprefix("_") for node in construct.body
               if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]
    assert methods == [cue["id"] for cue in scene.cues]


def test_slice_spread_is_fixed_height_and_has_separated_endpoints():
    positions = geometry_functions()["slice_positions"]
    previous_y = None
    for time in (.25, .5, .75, 1):
        common, ends = positions(time)
        assert common[1] == pytest.approx(1.65 - .55 * 5 * time ** 2)
        assert ends[1][0] - ends[0][0] > .09 + .15 + .1
        if previous_y is not None:
            assert previous_y - common[1] > .4
        previous_y = common[1]
        for alpha in np.linspace(0, 1, 61):
            projection, points = positions(time, alpha)
            for speed, point in zip((4, 8), points):
                assert point[1] == projection[1]
                assert point[0] - projection[0] == pytest.approx(.55 * speed * time * alpha)
    scene = dry_scene()
    expanded = [row for row in scene.motion if row["name"] == "expand"]
    assert len(expanded) == 4 * 31
    for index in range(4):
        chunk = expanded[index * 31:(index + 1) * 31]
        for row in chunk:
            assert row["children"][0][1] == row["children"][1][1]
            assert row["children"][0][1] == chunk[0]["children"][0][1]
    events = {row["id"]: row["time"] for row in scene.events}
    window = next(row for row in scene.windows if row["id"] == "shared_time_slices")
    assert window["start"] == events["slice_025_ready"]
    assert events["slice_100_ready"] < events["shared_time_slices_ready"] < window["end"]
    assert events["shared_time_slices_ready"] <= 65.1
    text = SOURCE.read_text(encoding="utf-8")
    assert "同一时刻的位置分解" in text and "不是实际运动" in text


def test_speed_arrow_is_velocity_not_constant_acceleration():
    ends = geometry_functions()["speed_arrow_ends"]
    for time in np.linspace(0, 2, 61):
        start, end = ends(time)
        assert start[0] == end[0] and start[1] >= end[1]
        assert np.linalg.norm(end - start) == pytest.approx(.095 * 10 * time)
    scene = dry_scene()
    sampled = [row for row in scene.motion if row["play_start"] in (85, 94)]
    assert len(sampled) == 62
    for row in sampled:
        time, velocity = row["numbers"][-2:]
        assert velocity == pytest.approx(10 * time)
        assert row["point"][1] == pytest.approx(1.7 - .19 * 5 * time ** 2)
        arrow = next(item for item in row["arrows"] if item["start"][0] == 1)
        if time:
            assert arrow["opacity"] == 1
            assert np.linalg.norm(arrow["end"] - arrow["start"]) == pytest.approx(.095 * velocity)
        else:
            assert arrow["opacity"] == 0
    assert sampled[30]["numbers"][-1] == 10
    assert sampled[-1]["numbers"][-1] == 20


def test_one_T_copy_uses_clear_corridor_without_formula_morph():
    route = geometry_functions()["time_transfer_point"]
    start, end = np.array([-1.5, .8, 0]), np.array([4.4, .8, 0])
    assert np.allclose(route(start, end, 0), start)
    assert np.allclose(route(start, end, 1), end)
    for alpha in np.linspace(1 / 3, 2 / 3, 31):
        assert route(start, end, alpha)[1] == pytest.approx(-.85)
    landing = next(node for node in ast.walk(source_tree()) if isinstance(node, ast.FunctionDef) and node.name == "_landing_rule")
    formula = next(node for node in ast.walk(landing) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name) and node.func.id == "SemanticFormula")
    assert ast.literal_eval(formula.args[0]).count("T") == 1
    assert ast.literal_eval(next(kw.value for kw in formula.keywords if kw.arg == "tokens")) == {"time": "T"}
    assert "Transform" not in ast.unparse(landing)
    assert "carrier = vertical.tag('time').copy()" in ast.unparse(landing)
    assert "self.remove(carrier)" in ast.unparse(landing)


def test_scope_does_not_override_runtime_or_start_external_work():
    tree = source_tree()
    scene = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    assert not {"setup", "tear_down"} & {node.name for node in scene.body if isinstance(node, ast.FunctionDef)}
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr in {"write_text", "render", "sound", "add_sound", "open"} for node in calls)
    assert all(any(keyword.arg == "run_time" for keyword in node.keywords)
               for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "play")
    prediction = next(node for node in scene.body if isinstance(node, ast.FunctionDef) and node.name == "_prediction")
    assert "T=3" not in ast.unparse(prediction)
    assert "R=12" not in ast.unparse(prediction)
    assert data("plan.json")["authorship"] == "supervised"
