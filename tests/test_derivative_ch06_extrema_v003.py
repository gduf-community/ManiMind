"""06 v003 native/fixture checks, never pixels, listening or approval.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main/CI.
Lifecycle: this candidate fixture; input, source and native API changes invalidate.
"""

import ast
import hashlib
import json
from pathlib import Path
import sys

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, transport_segments


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/derivative-ch06-extrema-v003"
SOURCE = ROOT / "examples/derivative_ch06_extrema_v003.py"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        if any(path.resolve().is_relative_to(ROOT / name) for name in ("runtime", "outputs")):
            raise AssertionError("Use frozen fixtures, not live production state")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    class Probe(lesson.DerivativeCh06ExtremaV003):
        def focus_begin(self, identity):
            super().focus_begin(identity)
            self.formula_states[identity] = {node.get_tex() for mob in self.mobjects for node in mob.get_family()
                if hasattr(node, "get_tex") and float(node.get_opacity()) > .9}

    def initialize(scene):
        scene.formula_states = {}

    with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
        yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
                    {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def at(native, placement, cue, local, kind):
    unit = next(p for p in placement if p["cue"] == cue)
    rows = [s for s in native.motion_samples if s["kind"] == kind]
    row = min(rows, key=lambda s: abs(s["time"]-unit["start"]-local))
    assert abs(row["time"]-unit["start"]-local) <= 1/30+.001
    return row


def test_complete_native_construct_and_all_intact_original_wavs(native, placement):
    plan, timings = read("plan.json"), read("timings.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-8)
    assert native.time > 335.04 > 292
    assert len(placement) == 7
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(335.04)
    assert sum(len(r["references"]) for r in placement) == 20
    assert {w["id"] for w in native._closed_focus} == {f["id"] for f in plan["focus_intents"]}
    assert not native._open_focus
    previous = 0
    for row, timing, intended in zip(placement, timings["units"], plan["intended_full_wav_placement"], strict=True):
        assert row["start"] >= previous
        assert row["end"]-row["start"] == pytest.approx(timing["duration_seconds"])
        assert abs(row["start"]-intended["intended_start"]) < .04
        assert timing["wav_sha256"] == intended["wav_sha256"]
        assert all(p["focus_start"] <= p["visual_start"]+1e-8 and p["visual_end"] <= p["focus_end"]+1e-8 for p in row["phrases"])
        previous = row["end"]


def test_neighborhood_actually_moves_only_in_its_original_motion_clause(native, placement):
    get = lambda t: at(native, placement, "neighborhood", t, "local_window")
    assert get(20)["center"] == -1
    assert -1 < get(26.5)["center"] < 1
    assert get(28.3)["center"] == pytest.approx(1)
    assert get(40)["center"] == pytest.approx(1)
    for row in [get(20), get(26.5), get(28.3), get(40)]:
        x = row["center"]
        assert row["point"] == pytest.approx([-3.15+1.25*x, .15+.48*(x**3-3*x), 0])
        assert row["radius"] == .42
    assert get(20)["left"] < get(20)["center_value"] > get(20)["right"]
    assert get(40)["left"] > get(40)["center_value"] < get(40)["right"]


def test_maximum_traverse_crosses_at_the_spoken_location_and_then_holds(native, placement):
    get = lambda t: at(native, placement, "turns", t, "cubic_traverse")
    assert get(3.8)["x"] == pytest.approx(-1.8)
    assert -1.8 < get(4.8)["x"] < -1
    assert get(5.9)["x"] == pytest.approx(-1)
    assert get(5.9)["y"] == pytest.approx(2)
    assert get(5.9)["derivative"] == pytest.approx(0)
    assert -1 < get(7.1)["x"] < -.2
    assert get(15)["x"] == pytest.approx(-.2)
    assert get(4.8)["derivative"] > 0 > get(7.1)["derivative"]


def test_minimum_traverse_preserves_same_curve_and_sign_transition(native, placement):
    get = lambda t: at(native, placement, "turns", t, "cubic_traverse")
    assert get(25.9)["x"] == pytest.approx(-.2)
    assert -.2 < get(26.9)["x"] < 1
    assert get(27.9)["x"] == pytest.approx(1)
    assert get(27.9)["y"] == pytest.approx(-2)
    assert get(27.9)["derivative"] == pytest.approx(0)
    assert 1 < get(28.9)["x"] < 1.8
    assert get(36)["x"] == pytest.approx(1.8)
    assert get(26.9)["derivative"] < 0 < get(28.9)["derivative"]


def test_stationary_origin_hold_and_continuing_ascent_follow_the_spoken_words(native, placement):
    get = lambda t: at(native, placement, "stationary", t, "stationary_pass")
    assert get(18.7)["x"] < 0 and get(18.7)["y"] < 0
    for time in (20.5, 21.1, 21.4):
        assert get(time)["x"] == pytest.approx(0)
        assert get(time)["y"] == pytest.approx(0)
    assert 0 < get(23.4)["x"] < get(29.9)["x"] < 1.2
    assert get(30.9)["x"] == pytest.approx(1.2)
    for row in (get(18.7), get(21.1), get(23.4), get(29.9)):
        assert row["derivative"] == pytest.approx(3*row["x"]**2)
        assert row["point"] == pytest.approx([-3.15+1.25*row["x"], .15+.48*row["x"]**3, 0])
    start = next(r["start"] for r in placement if r["cue"] == "stationary")
    mark = next(r["time"] for r in native.visual_events if r["id"] == "stationary_tangent_ready")
    assert start+12.4 < mark < start+12.7


def test_persistent_sign_focus_tracks_real_persistent_formula_not_empty_time(native):
    windows = {w["id"]: w for w in native._closed_focus}
    assert windows["critical_positions"]["end"] == windows["three_sign_intervals"]["end"] == windows["sign_to_monotonicity"]["end"]
    assert windows["three_sign_intervals"]["start"] < windows["sign_to_monotonicity"]["start"]
    assert any("3(x-1)(x+1)" in tex for tex in native.formula_states["sign_to_monotonicity"])
    assert {"+", "-", "0"} <= native.formula_states["sign_to_monotonicity"]


def test_necessity_is_one_way_and_left_right_quotients_remain_visible(native):
    conditions = native.formula_states["conditional_necessity"]
    assert any(r"\Longrightarrow\quad f'(a)=0" in tex for tex in conditions)
    common = native.formula_states["common_zero_necessity"]
    assert any(r"h<0:" in tex and r"\geq0" in tex for tex in common)
    assert any(r"h>0:" in tex and r"\leq0" in tex for tex in common)
    assert "可导的内点 a" in native.labels
    assert "双侧导数相同，只能为 0；极小同理" in native.labels
    assert "0 是尖点极小，导数不存在" in native.labels
    assert any(r"y=|x|" in tex for tex in native.formula_states["cusp_condition"])


def test_boundary_note_is_new_support_not_a_fictional_baseline_example(native, placement):
    assert "端点不套用“可导内点”的必要条件" in native.labels
    start = next(r["start"] for r in placement if r["cue"] == "closing")
    mark = next(r["time"] for r in native.visual_events if r["id"] == "boundary_scope_ready")
    assert start+25.3 < mark < start+27.82
    assert not read("plan.json")["new_visual_support"]["narration_changed"]
    assert "New explicit" in read("contract.json")["additional_candidate_requirements"]["boundary_scope"]


def test_original_native_methods_and_pure_mathematics_are_inherited(lesson):
    original = sys.modules["derivative_ch06_extrema"]
    for name in ("construct", "graph", "opening", "neighborhood", "signs", "turns", "necessary"):
        assert getattr(lesson.DerivativeCh06ExtremaV003, name) is getattr(original.DerivativeCh06Extrema, name)
    for row in read("baseline-lock.json")["protected_inputs"]:
        if row["path"].startswith("examples/"):
            assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    assert len(read("baseline-lock.json")["external_no_write_guards"]) == 20


def test_actual_292_second_baseline_and_process_triplets():
    contract = read("contract.json")
    validate_contract(contract)
    assert contract["assets"]["visual_v001"]["duration"] == 292
    assert contract["assets"]["visual_v001"]["sha256"] == "b4e7d506a2119e336e6e6acec55489b0771107067b2fa9d67a58a75fda4ae404"
    assert len(contract["units"]) == 7
    for unit in contract["units"]:
        for f in unit["features"]:
            lo, hi = f["baseline_interval"]
            assert unit["baseline_interval"][0] <= lo < hi <= unit["baseline_interval"][1]
            if f["kind"] == "process":
                assert [r["phase"] for r in f["baseline_samples"]] == ["before", "during", "after"]
                a, b, c = [r["time"] for r in f["baseline_samples"]]
                assert a < b < c


def test_original_narration_bytes_transport_and_author_identity():
    plan = read("plan.json")
    assert transport_segments(read("narration.json")) == read("transport.json")["segments"]
    assert hashlib.sha256((FIXTURES / "narration.json").read_bytes()).hexdigest() == plan["narration_draft_sha256"]
    assert plan["narration_draft"].endswith("narration-draft-v002.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19acd-e149-74d0-8a5d-975a3adf45f4"
    assert plan["contributors"][0]["author_agent"] == "01a199e9-7432-7052-96f7-6bd6eb2e63bb"
    assert plan["contributors"][1]["author_agent"] == "019eaf8b-9151-75e2-9db4-5ff834335577"
    assert plan["revision_mode"] == "revision"
    assert plan["status"] == read("contract.json")["status"] == "not_reviewed"
    assert read("timings.json")["fixture_only"] is True
    assert not plan["production_boundary"]["rendered"]
    assert not plan["production_boundary"]["published"]
    for key in ("writer", "consumers", "lifecycle", "invalidation"):
        assert plan[key] and read("contract.json")[key]


def test_old_opening_cannot_fit_original_intact_wav():
    plan = read("plan.json")
    plan["cues"][0]["duration"] = 24
    for cue in plan["cues"][1:]:
        cue["duration"] = 80
    plan["duration"] = sum(c["duration"] for c in plan["cues"])
    focuses = {"duration": plan["duration"], "windows": [
        {"id": f["id"], "start": .1, "end": plan["duration"]} for f in plan["focus_intents"]]}
    with pytest.raises(ValueError, match="ch06-opening: no intersection"):
        schedule(visual_timeline(plan), read("narration.json"), focuses, read("timings.json"))


def test_missing_native_key_has_no_ratio_fallback(lesson):
    scene = object.__new__(lesson.DerivativeCh06ExtremaV003)
    scene._cue = {"stage_times": {}}
    with pytest.raises(KeyError, match="0.16"):
        scene.beat(.16)


def test_candidate_has_no_media_or_audio_production_actions():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"render", "add_sound", "sound", "publish", "align_plan"}
