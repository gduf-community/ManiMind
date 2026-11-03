"""Case-level display changes preserve the inherited model and scene methods."""

import ast
from pathlib import Path
import runpy
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("formation", "WaveFormationLesson", "WaveFormationPositiveLesson"),
    ("reading", "WaveReadingLesson", "WaveReadingPositiveLesson"),
    ("superposition", "WaveSuperpositionLesson", "WaveSuperpositionPositiveLesson"),
)


class DisplaySink:
    durations = (1, 2, 3)

    def label(self, text, *args, **kwargs):
        return text, args, kwargs

    def title(self, text):
        return self.label(text, 0, 3.35, 39)

    def advance(self, *args):
        raise AssertionError("A display-only test cannot animate")


@pytest.fixture
def wrapper(monkeypatch):
    for name, original, _ in CASES:
        module = types.ModuleType(f"wave_{name}_visual")
        setattr(module, original, type(original, (DisplaySink,), {}))
        monkeypatch.setitem(sys.modules, module.__name__, module)
    return runpy.run_path(str(ROOT / "examples/wave_positive_visual.py"))


@pytest.fixture
def plain_wrapper(wrapper, monkeypatch):
    module = types.ModuleType("wave_positive_visual")
    for name in ("PLAN_REQUIRED_SOURCES", *(case[2] for case in CASES)):
        setattr(module, name, wrapper[name])
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return runpy.run_path(str(ROOT / "examples/wave_plain_visual.py"))


@pytest.mark.parametrize("variant", ("wrapper", "plain_wrapper"))
@pytest.mark.parametrize("name,original,positive", CASES)
def test_exact_display_replacements_are_reachable_and_preserve_arguments(request, variant, name, original, positive):
    namespace = request.getfixturevalue(variant)
    scene_class = positive.replace("Positive", "Plain") if variant == "plain_wrapper" else positive
    scene = namespace[scene_class]()
    source = ast.parse((ROOT / f"examples/wave_{name}_visual.py").read_text())
    calls = {"label": set(), "title": set()}
    for node in ast.walk(source):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in calls and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            calls[node.func.attr].add(node.args[0].value)
    for kind in calls:
        replacements = getattr(scene, kind + "_replacements")
        assert set(replacements) <= calls[kind]
        for before in calls[kind]:
            assert getattr(scene, kind)(before)[0] == replacements.get(before, before)
    assert scene.label("-1 < 0; y_1+y_2=0", 1, 2, size=30, width=5) == (
        "-1 < 0; y_1+y_2=0", (1, 2), {"size": 30, "width": 5},
    )
    assert scene.durations is DisplaySink.durations
    assert scene.advance.__func__ is DisplaySink.advance
    assert set(namespace["PLAN_SOURCE_DEPENDENCIES"][scene_class]) == set(namespace["PLAN_REQUIRED_SOURCES"])
    assert all((ROOT / path).is_file() for path in namespace["PLAN_REQUIRED_SOURCES"])


@pytest.mark.parametrize("name", ("positive", "plain"))
def test_case_wrapper_overrides_display_methods_only(name):
    tree = ast.parse((ROOT / f"examples/wave_{name}_visual.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            assert {item.name for item in node.body if isinstance(item, ast.FunctionDef)} <= {"label", "title"}


@pytest.mark.parametrize("name,original,positive", CASES)
def test_plain_wrapper_retains_every_previous_replacement_key(wrapper, plain_wrapper, name, original, positive):
    previous = wrapper[positive]
    current = plain_wrapper[positive.replace("Positive", "Plain")]
    for kind in ("label_replacements", "title_replacements"):
        assert set(getattr(previous, kind)) <= set(getattr(current, kind))


def test_numeric_details_in_the_positive_script_follow_the_shared_model():
    model = runpy.run_path(str(ROOT / "examples/wave_unit_model.py"))
    for t in (6, 6.25, 6.5, 6.75, 7, 7.5, 8, 8.5):
        assert model["forming_wave"](2, t) == pytest.approx(model["forming_wave"](4, t + 2))
    assert model["forming_wave"](4, 8.5001) < model["forming_wave"](4, 8.5)
    pulse = model["pulse_state"]
    assert pulse(4.5, 3)["y1_cm"] == pytest.approx(.62, abs=.005)
    assert pulse(4.5, 3)["y_cm"] == pytest.approx(1.24, abs=.005)
    assert pulse(4.5, 3, -1)["vy_cm_s"] < 0 < pulse(5.5, 3, -1)["vy_cm_s"]
    assert pulse(5, 3, -1)["vy_cm_s"] == 0
    assert pulse(5, 3, -.5)["y_cm"] == .5


def test_opposite_overlap_can_grow_locally_before_complete_cancellation():
    model = runpy.run_path(str(ROOT / "examples/wave_unit_model.py"))
    pulse = model["pulse_state"]
    earlier = pulse(4.5, 2.21, -1)
    later = pulse(4.5, 2.4, -1)
    assert earlier["y1_cm"] > 0 > earlier["y2_cm"]
    assert later["y1_cm"] > 0 > later["y2_cm"]
    assert abs(later["y_cm"]) > abs(earlier["y_cm"])
    assert pulse(4.5, 3, -1)["y_cm"] == 0
