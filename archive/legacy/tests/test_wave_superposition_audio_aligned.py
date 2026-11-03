"""Clock/model tests for the intact V01 retiming case, not independent review."""

import ast
import importlib.util
import json
from pathlib import Path

import pytest

from manimind.experiments.visual_first_data import validate_events
from manimind.review.meaning_units import schedule


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wave_clocks", ROOT / "tests/test_wave_voiced_clocks.py")
clocks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clocks)
SESSION = ROOT / "runtime/sessions/wave-alignment-20261031/author-superposition"
PROJECT = ROOT / "runtime/projects/wave-superposition-20261028"
OUTPUT = ROOT / "outputs/wave-superposition-20261028"


class CaseClock(clocks.FrameClock):
    def __init__(self, plan):
        super().__init__(plan)
        self.advances = []

    def play(self, *actions, run_time=1, **kwargs):
        for kind, obj, target in actions:
            if kind == "tracker":
                self.advances.append({"start": self.now, "end": self.now + run_time,
                                      "from": obj.value, "to": target})
        super().play(*actions, run_time=run_time, **kwargs)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def run_scene(plan, aligned=True):
    h = clocks.helpers
    namespace = {"UnderstandingScene": CaseClock, "model": h.MODEL, "np": h.np,
                 "INK": "white", "WAVE": "green", "PARTICLE": "yellow", "SECOND": "pink",
                 "MUTED": "grey", "GUIDE": "grey", "linear": "linear", "ValueTracker": h.Tracker}
    for name in ("Arrow", "Circle", "DashedVMobject", "Dot", "Group", "Line", "VMobject", "VGroup"):
        namespace[name] = clocks.ClockShape
    for name, kind in (("FadeIn", "in"), ("FadeOut", "out"), ("ShowCreation", "in")):
        namespace[name] = lambda obj, kind=kind: (kind, obj, None)
    names = ["wave_unit_shared.py", "wave_superposition_visual.py", "wave_positive_visual.py", "wave_plain_visual.py"]
    if aligned:
        names.append("wave_superposition_audio_aligned.py")
    for name in names:
        path = ROOT / "examples" / name
        nodes = [node for node in ast.parse(path.read_text()).body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                 and "Formation" not in node.name and "Reading" not in node.name]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    scene = namespace[plan["scene_class"]](plan)
    scene.construct()
    return scene


def placements(scene):
    return schedule(scene.timeline, read(PROJECT / "narration-positive-draft-v002.json"),
                    {"duration": scene.now, "windows": scene.windows},
                    read(OUTPUT / "phrase-timings-positive-v002.json"))


def test_all_references_and_physics():
    plan = read(PROJECT / "plan-audio-aligned-v001.json")
    scene = run_scene(plan)
    assert scene.now == pytest.approx(plan["duration"])
    assert not scene.open_focus
    validate_events(scene.timeline, {"duration": scene.now, "events": scene.events})
    rows = placements(scene)
    assert len(rows) == 5
    assert sum(len(row["phrases"]) for row in rows) == 17
    assert [row["duration_seconds"] for row in rows] == [18.88, 39.52, 32.96, 45.44, 31.68]
    for screen, physical, rate in scene.physics_intervals:
        assert screen == pytest.approx(physical)
        assert rate == "linear"
    baseline = run_scene(read(PROJECT / "plan-positive-v002.json"), aligned=False)
    assert [row[1:] for row in scene.physics_intervals] == [row[1:] for row in baseline.physics_intervals]
    assert [row["id"] for row in scene.events] == [row["id"] for row in baseline.events]
    assert {obj.text for obj in scene.labels} == {obj.text for obj in baseline.labels}
    assert set(plan["sources"]) >= {"examples/wave_plain_visual.py", "examples/wave_positive_visual.py",
                                    "examples/wave_superposition_visual.py", "examples/wave_unit_shared.py",
                                    "examples/wave_unit_model.py"}
    assert not any("audio_aligned" in source for source in plan["sources"])


def test_flat_result_and_frozen_local_probe():
    scene = run_scene(read(PROJECT / "plan-audio-aligned-v001.json"))
    windows = {row["id"]: row for row in scene.windows}
    assert windows["flat_result"]["end"] < windows["zero_not_rest"]["start"]
    assert "箭头：这一刻质点的速度方向" not in scene.focus_start_labels["flat_result"]
    assert "箭头：这一刻质点的速度方向" not in scene.focus_start_labels["opposite_pass"]
    events = {row["id"]: row["time"] for row in scene.events}
    for name, start, end in (("local_probe", events["addition_local_probe_ready"], events["addition_local_sum_ready"]),
                             ("flat", windows["flat_result"]["start"], windows["flat_result"]["end"])):
        samples = [row for row in scene.motion_samples if start < row["render_s"] < end and row["kind"] == "pulses"]
        assert samples, name
        assert all(row["physical_s"] == pytest.approx(3) for row in samples)
        if name == "flat":
            assert all(p["y_cm"] == pytest.approx(0) for row in samples for p in row["probes"])


def word_span(unit, quote):
    for phrase in unit["phrases"]:
        chars = [(c, w) for w in phrase["words"] for c in w["word"].strip()]
        text = "".join(c for c, _ in chars)
        if quote in text:
            begin = text.index(quote)
            words = [w for _, w in chars[begin:begin + len(quote)]]
            assert all(w["start"] < w["end"] for w in words)
            return unit["start"] + words[0]["start"], unit["start"] + words[-1]["end"]
    raise AssertionError(quote)


def test_assertions_follow_visible_results_and_process_clauses_cover_movement():
    scene = run_scene(read(PROJECT / "plan-audio-aligned-v001.json"))
    units = {u["id"]: u for u in placements(scene)}
    events = {e["id"]: e["time"] for e in scene.events}
    for unit, quote, event in (
        ("S02", "重合后", "positive_collision"),
        ("S02", "得到向上两厘米", "addition_numeric_ready"),
        ("S02", "四点五米处", "addition_local_probe_ready"),
        ("S02", "相加约一点二四厘米", "addition_local_sum_ready"),
        ("S03", "虚线放在一起比", "through_compare_second"),
        ("S03", "峰顶还是一厘米高", "through_height_second"),
        ("S04", "重合时", "flat_result_ready"),
        ("S04", "黄色箭头", "cancellation_velocity_ready"),
        ("S05", "先算五米处的峰顶", "unequal_collision"),
    ):
        assert events[event] <= word_span(units[unit], quote)[0], (unit, quote, event)
    assert events["unequal_collision"] <= word_span(units["S05"], "到三秒完全重合")[1]
    assert len(scene.advances) == 13
    assert sum(a["to"] - a["from"] for a in scene.advances) == pytest.approx(16.5)
    # Long clauses contain frozen before/after observations and native-speed motion.
    for unit, quote, indices in (("S01", "随着它们靠近", [0]),
                                 ("S03", "第一列继续向右", [3]),
                                 ("S03", "第二列继续向左", [4]),
                                 ("S03", "一起改变", [5]),
                                 ("S04", "同一个时钟继续走", [9]),
                                 ("S05", "时钟接着走", [12])):
        start, end = word_span(units[unit], quote)
        assert any(scene.advances[i]["start"] < end and scene.advances[i]["end"] > start for i in indices), (unit, quote)


def test_every_original_drawing_and_advance_call_is_preserved():
    baseline = ast.parse((ROOT / "examples/wave_superposition_visual.py").read_text()).body[-1]
    candidate = ast.parse((ROOT / "examples/wave_superposition_audio_aligned.py").read_text()).body[-1]
    methods = {"encounter", "addition", "through", "cancellation", "exit_task"}
    assert {node.name for node in candidate.body if isinstance(node, ast.FunctionDef)} == methods
    assert ast.unparse(candidate.bases[0]) == "WaveSuperpositionPlainLesson"
    drawings = {"put", "label", "title", "pulse_world", "driver", "play", "advance", "point",
                "Line", "Arrow", "Group", "VGroup", "DashedVMobject", "ValueTracker", "polyline", "pulse_state"}

    def calls(method):
        return sorted(ast.dump(node, include_attributes=False) for node in ast.walk(method)
                      if isinstance(node, ast.Call)
                      and (getattr(node.func, "id", None) or getattr(node.func, "attr", None)) in drawings)

    originals = {node.name: node for node in baseline.body if isinstance(node, ast.FunctionDef)}
    for method in candidate.body:
        if isinstance(method, ast.FunctionDef):
            assert calls(method) == calls(originals[method.name]), method.name
