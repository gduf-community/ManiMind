"""Formation v004-only data tests; no runtime, inference, video or font IO."""

import ast
import importlib.util
import json
from pathlib import Path

import pytest

from manimind.experiments.visual_first_data import validate_events, visual_timeline
from manimind.review.meaning_units import schedule


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests/fixtures/wave_formation_audio_v004"


def data(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("wave_clock_test_protocol", ROOT / "tests/test_wave_unit_model.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    ns = {"UnderstandingScene": helpers.DryRuntime, "model": helpers.MODEL, "np": helpers.np,
          "INK": "white", "WAVE": "green", "PARTICLE": "yellow", "SECOND": "pink",
          "MUTED": "grey", "GUIDE": "grey", "linear": "linear", "ValueTracker": helpers.Tracker}
    for name in ("Circle", "Dot", "Group", "Line", "VMobject", "VGroup"):
        ns[name] = helpers.Shape
    for name, kind in (("FadeIn", "in"), ("FadeOut", "out"), ("ShowCreation", "in")):
        ns[name] = lambda obj, kind=kind: (kind, obj, None)
    for name in ("shared_source.py", "scene.py"):
        tree = ast.parse((DATA / name).read_text(encoding="utf-8"))
        nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), name, "exec"), ns)
    scene = ns["WaveFormationLesson"](data("plan.json"))
    scene.construct()
    timeline = visual_timeline(data("plan.json"))
    focuses = {"duration": scene.now, "windows": scene.windows}
    rows = schedule(timeline, data("narration.json"), focuses, data("timings.json"))
    return scene, timeline, rows


def test_original_five_wavs_all_references_and_clock_fit(run):
    scene, timeline, rows = run
    assert scene.now == pytest.approx(146)
    assert not scene.open_focus
    validate_events(timeline, {"duration": scene.now, "events": scene.events})
    assert sum(u["duration_seconds"] for u in data("timings.json")["units"]) == pytest.approx(104.64)
    assert sum(len(u["references"]) for u in data("narration.json")["units"]) == 13
    for actual, expected, timing in zip(rows, data("expected.json")["schedule"], data("timings.json")["units"], strict=True):
        assert actual["id"] == expected["id"]
        assert actual["start"] == pytest.approx(expected["start"], abs=1 / 48000)
        assert actual["end"] - actual["start"] == pytest.approx(timing["duration_seconds"])
        assert actual["legal_start"][0] <= actual["legal_start"][1]
        for phrase in actual["phrases"]:
            assert phrase["focus_start"] - 1e-8 <= phrase["visual_start"] <= phrase["visual_end"] <= phrase["focus_end"] + 1e-8


def test_all_positive_word_landmarks_have_their_required_state(run):
    scene, _, rows = run
    starts = {r["id"]: r["start"] for r in rows}
    events = {e["id"]: e["time"] for e in scene.events}
    units = {u["id"]: u for u in data("timings.json")["units"]}
    checks = data("expected.json")["word_landmarks"]
    assert len(checks) == 16
    for check in checks:
        phrase = next(p for p in units[check["unit"]]["phrases"] if p["id"] == check["reference"])
        first, last = check["word_indices"]
        assert not set(range(first, last + 1)) & set(phrase.get("instantaneous_word_indices", []))
        words = phrase["words"][first:last + 1]
        assert all(w["end"] > w["start"] for w in words)
        moment = starts[check["unit"]] + words[0]["start"]
        assert events[check["required_event"]] <= moment + 1e-8
        assert moment == pytest.approx(check["start"])


def test_physics_not_speeded_or_skipped_and_historical_record_is_explicit(run):
    scene, _, _ = run
    assert sum(physical for _, physical, _ in scene.physics_intervals) == pytest.approx(19)
    assert all(render == pytest.approx(physical) and rate == "linear"
               for render, physical, rate in scene.physics_intervals)
    assert "半周期 t=14s 的记录" in (DATA / "scene.py").read_text(encoding="utf-8")
    windows = {w["id"]: w for w in scene.windows}
    assert windows["period_half_record"]["start"] < windows["one_period_motion"]["end"]
    assert windows["period_result"]["start"] < windows["one_period_motion"]["end"]
    assert data("plan.json")["revision_mode"] == "revision"
