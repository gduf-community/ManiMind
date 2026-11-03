"""Current wave scene clocks with matching tracked plans, not media approval."""

import ast
import importlib.util
import json
from pathlib import Path

import pytest

from manimind.experiments.visual_first_data import validate_events
from manimind.review.meaning_units import schedule, validate_narration
from manimind.review.semantic_focus import focus_windows


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests/fixtures/wave_unit"
SPEC = importlib.util.spec_from_file_location("wave_test_clock", ROOT / "tests/test_wave_unit_model.py")
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)
LESSONS = ("formation", "reading", "superposition")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class FrameClock(helpers.DryRuntime):
    def play(self, *actions, run_time=1, **kwargs):
        super().play(*actions, run_time=round(run_time * 30) / 30, **kwargs)

    def until(self, target):
        target = round(target * 30) / 30
        assert self.now <= target + 1e-7, (self.now, target)
        if target > self.now + 1e-7:
            self.wait(target - self.now)
        self.now = target


class ClockShape(helpers.Shape):
    def arrange(self, *args, **kwargs):
        return self

    def set_stroke(self, *args, **kwargs):
        return self


@pytest.fixture(scope="module")
def scenes():
    namespace = {"UnderstandingScene": FrameClock, "model": helpers.MODEL, "np": helpers.np,
                 "INK": "white", "WAVE": "green", "PARTICLE": "yellow", "SECOND": "pink",
                 "MUTED": "grey", "GUIDE": "grey", "linear": "linear", "ValueTracker": helpers.Tracker}
    for name in ("Arrow", "Circle", "DashedVMobject", "Dot", "Group", "Line", "VMobject", "VGroup"):
        namespace[name] = ClockShape
    for name, kind in (("FadeIn", "in"), ("FadeOut", "out"), ("ShowCreation", "in")):
        namespace[name] = lambda obj, kind=kind: (kind, obj, None)
    paths = [ROOT / "examples/wave_unit_shared.py"]
    paths += [ROOT / f"examples/wave_{name}_visual.py" for name in LESSONS]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        definitions = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), "exec"), namespace)
    result = {}
    for lesson in LESSONS:
        revision = "v006" if lesson == "formation" else "v005"
        plan = read(DATA / revision / (lesson + "-plan.json"))
        scene = namespace[plan["scene_class"]](plan)
        # Native text/curve bounds have separate render evidence. Do not invent
        # bounding boxes in this clock-only double.
        if hasattr(scene, "measure_layout"):
            scene.measure_layout = lambda *args, **kwargs: None
        scene.construct()
        result[lesson] = (plan, scene)
    return result


@pytest.mark.parametrize("lesson", LESSONS)
def test_complete_original_narration_has_current_finite_focuses(scenes, lesson):
    plan, scene = scenes[lesson]
    original = read(DATA / "v003" / f"wave-{lesson}-20261028/narration-draft-v002.json")
    assert not scene.open_focus
    assert scene.now == pytest.approx(plan["duration"])
    assert scene.now == pytest.approx(sum(scene.durations))
    validate_events(scene.timeline, {"duration": scene.now, "events": scene.events})
    focuses = {"duration": scene.now, "windows": scene.windows}
    validate_narration(original, scene.timeline, focuses)
    windows = focus_windows(focuses, scene.now)
    intents = {row["id"]: row["cue"] for row in plan["focus_intents"]}
    assert set(windows) == set(intents)
    cues = {row["id"]: row for row in scene.cues}
    for key, window in windows.items():
        cue = cues[intents[key]]
        assert cue["start"] <= window["start"] < window["end"] <= cue["start"] + cue["duration"] + 1e-7
    assert plan["revision_mode"] == "revision"
    assert plan["revision_contract"].endswith("revision-contract-voiced-v001.json")
    assert plan["author_agent"] == plan["author_context"]


@pytest.mark.parametrize("lesson", LESSONS)
def test_every_physical_advance_remains_one_to_one(scenes, lesson):
    _, scene = scenes[lesson]
    assert scene.physics_intervals
    for screen, physical, rate in scene.physics_intervals:
        assert screen == pytest.approx(physical, abs=1e-7)
        assert rate == "linear"


def test_flat_result_precedes_local_velocity_explanation(scenes):
    _, scene = scenes["superposition"]
    windows = {row["id"]: row for row in scene.windows}
    assert windows["flat_result"]["end"] <= windows["zero_not_rest"]["start"]
    caption = "箭头：这一刻质点的速度方向"
    assert caption not in scene.focus_start_labels["flat_result"]
    assert caption not in scene.focus_start_labels["opposite_pass"]
    samples = [row for row in scene.motion_samples if row["kind"] == "pulses"
               and windows["flat_result"]["start"] < row["render_s"] < windows["flat_result"]["end"]]
    assert samples
    assert all(row["physical_s"] == pytest.approx(3) for row in samples)
    assert all(probe["y_cm"] == pytest.approx(0) for row in samples for probe in row["probes"])


def test_cycle_process_occurs_during_its_original_spoken_clause(scenes):
    _, scene = scenes["formation"]
    narration = read(DATA / "v003/wave-formation-20261028/narration-draft-v002.json")
    timing = read(ROOT / "tests/fixtures/wave_formation_audio_v004/timings.json")
    rows = schedule(scene.timeline, narration, {"duration": scene.now, "windows": scene.windows}, timing)
    unit = next(row for row in rows if row["id"] == "F04")
    phrase = next(row for row in unit["phrases"] if row["id"] == "r2")
    characters = [(char, word) for word in phrase["words"] for char in word["word"].strip()]
    text = "".join(char for char, _ in characters)
    events = {row["id"]: row["time"] for row in scene.events}
    for quote, event in (("先到下面", "period_half"), ("完成一次振动", "period_finished")):
        begin = text.index(quote)
        words = [word for _, word in characters[begin:begin + len(quote)]]
        assert all(word["end"] > word["start"] for word in words)
        assert unit["start"] + words[0]["start"] <= events[event] <= unit["start"] + words[-1]["end"]
    assert phrase["visual_start"] < events["period_half"] < events["period_finished"] < phrase["visual_end"]
