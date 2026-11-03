"""Author A offline model/contract tests; never render GL, TeX or speech.

The symbolic scene below checks Python control flow and named-window lifecycle
only. It deliberately does not test native animation interpolation or pixels.
"""

import ast
from fractions import Fraction
import json
import math
from pathlib import Path
import types

import numpy as np
import pytest

from manimind.experiments.visual_first_data import visual_timeline, validate_events
from manimind.review.meaning_units import validate_units


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch02_basics.py"
FIXTURES = ROOT / "tests/fixtures/derivative-ch02-basics"


def read_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def forbid_runtime_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT / "runtime"):
            raise AssertionError("Offline tests consume versioned fixtures, not runtime")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


def pure_module(source):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             or isinstance(n, ast.ImportFrom) and n.module == "numbers"
             or isinstance(n, ast.Import) and any(a.name == "math" for a in n.names)]
    module = types.ModuleType(source.stem+"_pure")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), module.__dict__)
    return module


@pytest.fixture(scope="module")
def model():
    return pure_module(SOURCE)


@pytest.mark.parametrize("a", [Fraction(-3), Fraction(-1, 3), Fraction(0), Fraction(2), Fraction(5, 2)])
@pytest.mark.parametrize("h", [Fraction(-1, 2), Fraction(-1, 100), Fraction(1, 100), Fraction(1, 2)])
def test_square_generalization_exact(model, a, h):
    state = model.square_state(a)
    assert state == {"x": a, "value": a*a, "slope": 2*a}
    assert ((a+h)**2-a*a)/h == model.square_quotient(a, h)
    assert model.square_quotient(a, h)-state["slope"] == h


@pytest.mark.parametrize("n", [-4, -1, 0, 1, 2, 3, 7])
@pytest.mark.parametrize("x", [Fraction(-2), Fraction(-1, 2), Fraction(1, 2), Fraction(3)])
def test_integer_power_domain_and_formula(model, n, x):
    s = model.integer_power_state(x, n)
    assert s["value"] == x**n
    assert s["slope"] == (0 if n == 0 else n*x**(n-1))


def test_zero_and_endpoints(model):
    assert model.integer_power_state(0, 0)["slope"] == 0
    assert model.integer_power_state(0, 1)["slope"] == 1
    assert model.integer_power_state(0, 3)["slope"] == 0
    with pytest.raises(ValueError):
        model.integer_power_state(0, -1)
    for x in (0, -1):
        with pytest.raises(ValueError):
            model.positive_power_state(x, .5)
        with pytest.raises(ValueError):
            model.basic_state("root", x)
    for h in (1, .01, .0001):
        assert math.sqrt(h)/h == pytest.approx(1/math.sqrt(h))


@pytest.mark.parametrize("x,h", [(Fraction(-2), Fraction(1, 5)), (Fraction(2), Fraction(-1, 5)),
                                 (Fraction(1, 3), Fraction(1, 100))])
def test_reciprocal_quotient_exact(model, x, h):
    assert model.reciprocal_quotient(x, h) == (1/(x+h)-1/x)/h
    assert model.basic_state("reciprocal", x)["slope"] == -1/x**2


@pytest.mark.parametrize("x,h", [(1, -.5), (2, .1), (.1, -.1), (.04, .001)])
def test_root_conjugate_identity(model, x, h):
    assert model.root_quotient(x, h) == pytest.approx((math.sqrt(x+h)-math.sqrt(x))/h)


@pytest.mark.parametrize("kind,x,base", [("square", -1.2, math.e), ("constant", 2, math.e),
    ("identity", -1.2, math.e),
    ("cube", -1.2, math.e), ("reciprocal", -2, math.e), ("root", .3, math.e),
    ("exp", -.8, .5), ("exp", .8, 2), ("exp", 2, 1), ("exp", .7, math.e),
    ("log", .7, math.e), ("log", .7, .5), ("log", 2, 10),
    ("sin", 1.2, math.e), ("cos", 1.2, math.e)])
def test_analytic_slopes_against_two_sided_numeric_difference(model, kind, x, base):
    h = 1e-5
    s = model.basic_state(kind, x, base)
    numeric = (model.basic_state(kind, x+h, base)["value"]-model.basic_state(kind, x-h, base)["value"])/(2*h)
    assert s["slope"] == pytest.approx(numeric, abs=1e-8)


@pytest.mark.parametrize("x", [0, math.pi/2, math.pi, 3*math.pi/2, 2*math.pi])
def test_radian_phase_and_exponential_value_slope(model, x):
    assert model.basic_state("sin", x)["slope"] == pytest.approx(math.cos(x))
    assert model.basic_state("cos", x)["slope"] == pytest.approx(-math.sin(x))
    e = model.basic_state("exp", x)
    assert e["value"] == pytest.approx(e["slope"])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "2", None, 1j])
def test_bad_values_rejected(model, bad):
    for fn in (model.square_state, model.constant_state, lambda x: model.basic_state("sin", x)):
        with pytest.raises((ValueError, TypeError)):
            fn(bad)


def test_domain_guards(model):
    cases = [lambda: model.square_quotient(2, 0), lambda: model.reciprocal_quotient(0, 1),
             lambda: model.reciprocal_quotient(2, -2), lambda: model.reciprocal_quotient(2, 0),
             lambda: model.root_quotient(1, -2), lambda: model.root_quotient(1, 0),
             lambda: model.basic_state("exp", 1, -2), lambda: model.basic_state("log", 2, 1),
             lambda: model.basic_state("log", 0), lambda: model.basic_state("missing", 1),
             lambda: model.integer_power_state(2, .5)]
    for fn in cases:
        with pytest.raises((ValueError, TypeError)):
            fn()


class Symbol:
    """In-memory geometry placeholder, not a native Manim object."""
    def __init__(self, *items, **kwargs):
        self.items, self.updaters, self.center = list(items), [], np.zeros(3)
        self.value = items[0] if items and isinstance(items[0], (int, float)) else 0

    @property
    def animate(self):
        return self

    def move_to(self, position, **kwargs):
        self.center = np.array(position, dtype=float)
        return self

    def get_center(self):
        return self.center

    def get_width(self):
        return 1

    def set_value(self, value):
        self.value = value
        return self

    def get_value(self):
        return self.value

    def add(self, *items):
        self.items.extend(items)
        return self

    def add_updater(self, callback):
        self.updaters.append(callback)
        return self

    def clear_updaters(self):
        self.updaters = []
        return self

    def set_points_as_corners(self, points):
        self.points = points
        return self

    def put_start_and_end_on(self, a, b):
        self.points = (a, b)
        return self

    def set_color(self, *args):
        return self

    def set_stroke(self, *args):
        return self

    def set_width(self, *args):
        return self


class SymbolicClock:
    def __init__(self, plan):
        self.cues = visual_timeline(plan)["cues"]
        self._open_focus, self.closed, self.events, self.samples = {}, [], [], []
        self.mobjects, self._subtitle_driver, self.time = [], Symbol(), 0.

    def until(self, when):
        assert when >= self.time-1e-8, "Scene asked for a past target"
        self.time = when

    def begin_chapter(self, cue):
        assert not self._open_focus
        self._cue = cue
        self.mobjects = []
        self.beat(.06)

    def end_chapter(self):
        self.beat(1)
        for identity in tuple(self._open_focus):
            self.focus_end(identity)

    def beat(self, fraction, *animations, **kwargs):
        offset = self._cue.get("stage_times", {}).get(f"{fraction:.2f}", fraction*self._cue["duration"])
        assert 0 <= offset <= self._cue["duration"]
        self.until(self._cue["start"]+offset)
        for animation in animations:
            if isinstance(animation, tuple):
                mode, obj = animation
                if mode == "in":
                    self.add(obj)
                else:
                    self.remove(obj)
        for obj in tuple(self.mobjects):
            for callback in obj.updaters:
                callback(obj)

    def safe_formula(self, source, target, end, **kwargs):
        self.beat(end, ("in", target))

    def add(self, *objects):
        self.mobjects.extend(objects)

    def remove(self, *objects):
        self.mobjects = [obj for obj in self.mobjects if all(obj is not x for x in objects)]

    def mark(self, identity):
        self.events.append({"id": identity, "time": self.time})

    def focus_begin(self, identity):
        assert identity not in self._open_focus
        assert identity not in {row["id"] for row in self.closed}
        self._open_focus[identity] = self.time

    def focus_end(self, identity):
        start = self._open_focus.pop(identity)
        assert start < self.time
        self.closed.append({"id": identity, "start": start, "end": self.time})

    def sample(self, kind, **values):
        self.samples.append({"kind": kind, "time": self.time, **values})

    def label(self, *args, **kwargs):
        return Symbol(*args, **kwargs)

    def number(self, *args, **kwargs):
        return Symbol(*args, **kwargs)


def symbolic_run(source, scene_name, plan):
    module = pure_module(source)
    namespace = module.__dict__
    namespace.update(np=np, ChapterScene=SymbolicClock, INK="#fff", MUTED="#aaa",
                     CURVE="#0a0", RATE="#a00", ACCENT="#aa0", linear=None,
                     FadeIn=lambda obj: ("in", obj), FadeOut=lambda obj: ("out", obj))
    for name in ("Group", "Dot", "Line", "Polygon", "ValueTracker", "VMobject", "SemanticFormula"):
        namespace[name] = Symbol
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) or isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in {"CUE_IDS", "CUE_DURATIONS"} for t in n.targets)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    scene = namespace[scene_name](plan)
    scene.construct()
    return scene, namespace


def assert_contracts(source, scene_name, plan, narration, science):
    validate_units(narration)
    timeline = visual_timeline(plan)
    scene, namespace = symbolic_run(source, scene_name, plan)
    validate_events(timeline, {"duration": scene.time, "events": scene.events})
    assert scene.time == plan["duration"] == sum(namespace["CUE_DURATIONS"])
    assert not scene._open_focus and not scene._drivers
    intended = {r["id"]: r["cue"] for r in plan["focus_intents"]}
    assert {row["id"] for row in scene.closed} == set(intended)
    assert {r["focus"] for u in narration["units"] for r in u["references"]} == set(intended)
    for window in scene.closed:
        cue = next(c for c in timeline["cues"] if c["id"] == intended[window["id"]])
        assert cue["start"] <= window["start"] < window["end"] <= cue["start"]+cue["duration"]
    assert all(intended[ref["focus"]] == unit["cue"] for unit in narration["units"] for ref in unit["references"])
    assert "examples/derivative_chapter_shared.py" in plan["sources"]
    assert plan["fps"] == 30 and plan["resolution"] == [1920, 1080]
    for artifact in (plan, narration, science):
        assert all(artifact.get(k) for k in ("writer", "consumers", "lifecycle", "invalidation"))
    assert plan["author_agent"] == plan["author_context"] == narration["author_agent"] == plan["writer"]
    assert narration["audio_status"] == "not_generated"
    assert not any("start" in ref or "end" in ref for u in narration["units"] for ref in u["references"])
    return scene


def test_draft_control_flow_and_versioned_contracts():
    scene = assert_contracts(SOURCE, "DerivativeBasicsLesson", read_fixture("plan.json"),
                             read_fixture("narration.json"), read_fixture("science.json"))
    assert {s["function"] for s in scene.samples} == {
        "square", "constant", "identity", "cube", "reciprocal", "root", "exp", "log", "sin", "cos"}
    assert all(s["slope"] == pytest.approx(pure_module(SOURCE).basic_state(s["function"], s["x"], s["base"])["slope"])
               for s in scene.samples)


def test_cue_durations_are_parameterized_not_fixed():
    plan = read_fixture("plan.json")
    for cue in plan["cues"]:
        cue["duration"] *= 1.2
    scene, _ = symbolic_run(SOURCE, "DerivativeBasicsLesson", plan)
    assert scene.time == pytest.approx(sum(c["duration"] for c in plan["cues"]))


@pytest.mark.parametrize("x", [Fraction(-3), Fraction(0), Fraction(5, 2)])
@pytest.mark.parametrize("h", [Fraction(-1, 100), Fraction(1, 100)])
def test_identity_definition_quotient(model, x, h):
    assert model.identity_quotient(x, h) == ((x+h)-x)/h == 1
    assert model.identity_state(x) == {"x": x, "value": x, "slope": 1}
    with pytest.raises(ValueError):
        model.identity_quotient(x, 0)


@pytest.mark.parametrize("x", [Fraction(-3), Fraction(0), Fraction(5, 2)])
@pytest.mark.parametrize("h", [Fraction(-1, 100), Fraction(1, 100)])
def test_constant_and_cubic_definition_steps(model, x, h):
    assert model.constant_quotient(x, h) == (x-x)/h == 0
    expanded = (3*x*x*h+3*x*h*h+h**3)/h
    assert model.cubic_quotient(x, h) == ((x+h)**3-x**3)/h == expanded
    assert model.cubic_quotient(x, h)-3*x*x == 3*x*h+h*h
    for fn in (model.constant_quotient, model.cubic_quotient):
        with pytest.raises(ValueError):
            fn(x, 0)


def test_declares_all_six_definition_bridges():
    plan = read_fixture("plan.json")
    ids = {row["id"] for row in plan["focus_intents"]}
    assert {"constant_increment", "identity_quotient", "general_quotient", "general_limit",
            "power_cubic_expansion", "power_cubic_limit", "reciprocal_common_denominator",
            "reciprocal_limit", "root_conjugate", "root_domain"} <= ids


def test_no_old_course_inheritance_or_per_frame_tex():
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lesson = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    assert [n.id for n in lesson.bases] == ["ChapterScene"]
    assert "always_redraw" not in source and "derivative_intro" not in source
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "update":
            assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                           and n.func.attr in {"sf", "put", "formula", "cn", "label"} for n in ast.walk(node))
