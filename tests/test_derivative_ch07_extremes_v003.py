"""not_reviewed: real native chapter-07 timing, math and original-WAV bounds."""

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract, revision_required
from manimind.review.meaning_units import schedule, transport_segments, validate_narration


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"examples/derivative_ch07_extremes_v003.py"
FIXTURES = ROOT/"tests/fixtures/derivative-ch07-extremes-v003"


def read(name):
    return json.loads((FIXTURES/name).read_text(encoding="utf-8"))


def initialize_probe(scene):
    scene.stage_trace, scene.formula_states, scene.focus_points = [], {}, {}


def probe_class(parent):
    import derivative_ch07_extremes as base

    class Probe(parent):
        def label(self, text, *args, **kwargs):
            obj = super().label(text, *args, **kwargs)
            obj._native_label = text
            return obj

        def snapshot(self):
            family = {id(n): n for m in self.mobjects for n in m.get_family()}
            observable = [n for n in family.values() if isinstance(n, base.Dot)
                          or hasattr(n, "get_tex") or hasattr(n, "_native_label") or type(n).__name__ == "Number"]
            visible = [n for n in observable if float(n.get_opacity()) > .9]
            return {"text": [{"text": n.get_tex() if hasattr(n, "get_tex") else n._native_label,
                              "center": n.get_center().tolist()} for n in visible
                             if hasattr(n, "get_tex") or hasattr(n, "_native_label")],
                    "dots": sorted(tuple(float(x) for x in n.get_center()) for n in visible if isinstance(n, base.Dot)),
                    "numbers": [{"value": n.get_value(), "center": n.get_center().tolist()}
                                for n in visible if type(n).__name__ == "Number"]}

        def beat(self, fraction, *animations, **kwargs):
            start, plays = self.get_time(), len(self.plays)
            super().beat(fraction, *animations, **kwargs)
            self.stage_trace.append({"cue": self._cue["id"], "key": f"{fraction:.2f}",
                "before": start, "after": self.get_time(), "plays": self.plays[plays:],
                "native_objects_after": self.snapshot()})

        def focus_begin(self, identity):
            super().focus_begin(identity)
            self.formula_states[identity] = self.snapshot()["text"]
            self.focus_points[identity] = {"start": self.snapshot()}

        def focus_end(self, identity):
            self.focus_points[identity]["end"] = self.snapshot()
            super().focus_end(identity)

    return Probe


@pytest.fixture(autouse=True)
def forbid_production_runtime_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT/"runtime"):
            raise AssertionError("Use isolated 07 v003 fixtures, not production runtime")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    with native_run(lesson, probe_class(lesson.DerivativeCh07ExtremesV003), read("plan.json"), initialize_probe) as scene:
        yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
        {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def at(native, placement, unit, local, kind):
    row = next(r for r in placement if r["id"] == unit)
    target = row["start"]+local
    samples = [s for s in native.motion_samples if s["kind"] == kind]
    sample = min(samples, key=lambda s: abs(s["time"]-target))
    assert abs(sample["time"]-target) <= 1/30+.001
    return sample


def stage(native, cue, key):
    return next(s for s in native.stage_trace if s["cue"] == cue and s["key"] == key)


def texts(snapshot):
    return {n["text"] for n in snapshot["text"]}


def test_full_clock_focus_lifecycle_and_all_seven_original_wavs(native, placement):
    plan, narration, timings = read("plan.json"), read("narration.json"), read("timings.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-8)
    assert len(placement) == len(timings["units"]) == 7
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(297.44)
    assert not native._open_focus
    assert {w["id"] for w in native._closed_focus} == {f["id"] for f in plan["focus_intents"]}
    assert len(native._closed_focus) == 19
    validate_narration(narration, visual_timeline(plan), {"duration": native.time, "windows": native._closed_focus})
    previous = 0
    for row, timing, intended in zip(placement, timings["units"], plan["intended_full_wav_placement"], strict=True):
        assert row["start"] >= previous
        assert row["end"]-row["start"] == pytest.approx(timing["duration_seconds"])
        assert abs(row["start"]-intended["intended_start"]) <= .04
        cue = next(c for c in visual_timeline(plan)["cues"] if c["id"] == row["cue"])
        assert cue["start"] <= row["start"] < row["end"] <= cue["start"]+cue["duration"]
        for phrase in row["phrases"]:
            assert phrase["focus_start"] <= phrase["visual_start"]+.000001
            assert phrase["visual_end"] <= phrase["focus_end"]+.000001
        previous = row["end"]


def test_original_276_second_baseline_cannot_fit_current_full_wavs():
    with pytest.raises(ValueError, match="no intersection of phrase focus/cue/full-WAV bounds"):
        schedule(visual_timeline(read("baseline-plan.json")), read("narration.json"), read("baseline-focus.json"), read("timings.json"))


@pytest.mark.parametrize("index,x,y,key_x,key_y", [(0, 0, 1, "0.21", "0.23"), (1, 1, 0, "0.32", "0.34"), (2, 3, 4, "0.43", "0.45")])
def test_real_row_and_curve_reveals_follow_spoken_substitutions(native, placement, index, x, y, key_x, key_y):
    import derivative_ch07_extremes as base
    row = next(r for r in placement if r["id"] == "ch07-compare")
    first = stage(native, "compare", key_x)
    second = stage(native, "compare", key_y)
    y_pos = 1.25-.9*index
    assert any(n["text"] == str(x) and n["center"] == pytest.approx([2.25, y_pos, 0]) for n in first["native_objects_after"]["text"])
    assert any(p == pytest.approx(base.graph_point(x, y)) for p in first["native_objects_after"]["dots"])
    assert not any(n["center"] == pytest.approx([4.65, y_pos, 0]) for n in first["native_objects_after"]["text"])
    assert any(n["text"] == str(y) and n["center"] == pytest.approx([4.65, y_pos, 0]) for n in second["native_objects_after"]["text"])
    # The source word estimates are nonzero at each spoken result numeral.
    spoken_x = [3.1, 5.84, 8.38][index]
    spoken_y = [5.16, 7.58, 10.18][index]
    assert abs(first["after"]-(row["start"]+spoken_x)) < .12
    assert abs(second["after"]-(row["start"]+spoken_y)) < .12


def test_table_focus_names_actual_building_then_min_and_max_are_separate(native, placement):
    start = native.focus_points["candidate_values"]["start"]
    assert {"x", "f(x)"} <= texts(start)
    assert not any(n["center"][0] == pytest.approx(4.65) and n["center"][1] < 2 for n in start["text"])
    minimum = stage(native, "compare", "0.72")["native_objects_after"]
    maximum = stage(native, "compare", "0.79")["native_objects_after"]
    assert r"\min f=0\quad(x=1)" in texts(minimum)
    assert r"\max f=4\quad(x=3)" not in texts(minimum)
    assert {r"\min f=0\quad(x=1)", r"\max f=4\quad(x=3)"} <= texts(maximum)
    assert stage(native, "compare", "0.45")["after"] < stage(native, "compare", "0.72")["after"] < stage(native, "compare", "0.79")["after"]


def test_parameter_motion_starts_with_actual_move_words_and_preserves_fixed_function(native, placement):
    first = at(native, placement, "ch07-parameter", 9.8, "moving_endpoint")
    moving = at(native, placement, "ch07-parameter", 15, "moving_endpoint")
    last_left = at(native, placement, "ch07-parameter", 22, "moving_endpoint")
    assert first["b"] == pytest.approx(1.25)
    assert 1.25 < moving["b"] < 1.8
    assert last_left["b"] == pytest.approx(1.8)
    assert last_left["argmax"] == (0,)
    samples = [r for r in native.motion_samples if r["kind"] == "moving_endpoint"]
    for s in samples[::31]:
        fb = (s["b"]-1)**2
        assert s["candidates"] == pytest.approx([1, 0, fb])
        assert s["endpoint"] == pytest.approx([-5.7+1.9*s["b"], -1.75+.8*fb, 0])
        assert s["minimum"] == 0 and s["argmin"] == (1,)
        assert 1.25 <= s["b"] <= 3


@pytest.mark.parametrize("local", [29.2, 32.56, 38.46, 42.5])
def test_b_equals_two_really_holds_during_two_positions_explanation(native, placement, local):
    s = at(native, placement, "ch07-parameter", local, "moving_endpoint")
    assert s["b"] == pytest.approx(2)
    assert s["maximum"] == 1 and s["argmax"] == (0, 2)
    assert s["minimum"] == 0 and s["argmin"] == (1,)
    assert native.focus_points["parameter_tie"]["start"] == native.focus_points["parameter_tie"]["end"]


def test_real_tie_approach_then_overtake_then_true_final_hold(native, placement):
    assert 1.8 < at(native, placement, "ch07-parameter", 26, "moving_endpoint")["b"] < 2
    assert 2 < at(native, placement, "ch07-parameter", 46, "moving_endpoint")["b"] < 3
    import derivative_ch07_extremes as base
    start, end = native.focus_points["parameter_right_wins"]["start"], native.focus_points["parameter_right_wins"]["end"]
    assert start == end
    assert any(p == pytest.approx(base.graph_point(3, 4)) for p in end["dots"])
    assert any(n["value"] == pytest.approx(3) for n in end["numbers"])
    assert any(n["value"] == pytest.approx(4) for n in end["numbers"])


def test_existential_guarantee_and_nondifferentiable_candidate_are_timed_visible_labels(native, placement):
    guarantee = "保证最大值、最小值都能取到"
    search = "本例：比较端点与内部驻点的值"
    nondiff = "若内部不可导，还需检查那些位置"
    assert {"连续", "有限闭区间"} <= texts(native.focus_points["existence_conditions"]["start"])
    assert guarantee in texts(stage(native, "conditions", "0.31")["native_objects_after"])
    assert search in texts(stage(native, "conditions", "0.58")["native_objects_after"])
    assert nondiff not in texts(stage(native, "conditions", "0.58")["native_objects_after"])
    assert nondiff in texts(stage(native, "conditions", "0.72")["native_objects_after"])
    row = next(r for r in placement if r["id"] == "ch07-conditions")
    for key, word in [("0.31", 4.7), ("0.58", 25.84), ("0.72", 29.74)]:
        assert -.2 < stage(native, "conditions", key)["after"]-(row["start"]+word) < .01


def test_open_point_moves_with_narration_but_never_reaches_excluded_endpoint(native, placement):
    early = at(native, placement, "ch07-open_interval", 18.8, "open_approach")
    middle = at(native, placement, "ch07-open_interval", 25, "open_approach")
    near = at(native, placement, "ch07-open_interval", 30.2, "open_approach")
    assert early["x"] == pytest.approx(2.2)
    assert 2.2 < middle["x"] < 2.99
    assert near["x"] == pytest.approx(2.99)
    for s in [s for s in native.motion_samples if s["kind"] == "open_approach"][::19]:
        assert s["x"] < 3 and s["endpoint_included"] is False
        assert s["value"] == pytest.approx((s["x"]-1)**2)
        assert s["value"] < 4
        assert s["gap"] == pytest.approx(4-s["value"])
        assert s["gap"] > 0
    state = native.focus_points["unattained_supremum"]
    assert state["start"] == state["end"]
    assert r"x\to3^-:\ f(x)\to4" in texts(state["start"])
    assert any(n["value"] == pytest.approx(3.9601) for n in state["end"]["numbers"])
    assert "上确界为 4，无最大值；最小值仍为 0" in texts(state["end"])
    assert r"\min f=0\quad(x=1)" in texts(state["end"])


def test_original_math_geometry_and_all_actual_baseline_objects_are_unchanged(lesson):
    import derivative_ch07_extremes as original
    for method in ["construct", "opening", "candidates", "parameter", "open_interval", "closing", "graph"]:
        assert getattr(lesson.DerivativeCh07ExtremesV003, method) is getattr(original.DerivativeCh07Extremes, method)
    for row in read("baseline-lock.json")["sources"]:
        assert hashlib.sha256((ROOT/row["path"]).read_bytes()).hexdigest() == row["sha256"]
    old_tree = ast.parse((ROOT/"examples/derivative_ch07_extremes.py").read_text())
    new_tree = ast.parse(SOURCE.read_text())
    for name in ["compare", "conditions"]:
        def calls(tree):
            method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
            return Counter(ast.dump(n, include_attributes=False) for n in ast.walk(method)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {"put", "label", "graph"})
        assert calls(old_tree) == calls(new_tree)
    cls = next(n for n in new_tree.body if isinstance(n, ast.ClassDef))
    assert {n.name for n in cls.body if isinstance(n, ast.FunctionDef)} == {"beat", "compare", "conditions"}


def test_original_baseline_native_clock_and_focuses_match_real_render(lesson):
    import derivative_ch07_extremes as original
    with native_run(original, original.DerivativeCh07Extremes, read("baseline-plan.json")) as scene:
        assert scene.time == 276
        actual = {w["id"]: w for w in read("baseline-focus.json")["windows"]}
        for w in scene._closed_focus:
            assert w["start"] == pytest.approx(actual[w["id"]]["start"], abs=1/30)
            assert w["end"] == pytest.approx(actual[w["id"]]["end"], abs=1/30)


def test_inventory_binds_actual_v001_pixels_not_hidden_numeric_precision():
    contract = read("contract.json")
    validate_contract(contract)
    assert set(contract["assets"]) == {"visual_v001"}
    assert contract["assets"]["visual_v001"]["duration"] == 276
    assert contract["assets"]["visual_v001"]["sha256"] == "cc18b7041cc3cbb16a1ae6ec7ba99f94456ca6fa9bc496563ab92adc4dfe2349"
    assert sum(len(u["features"]) for u in contract["units"]) == 23
    for u in contract["units"]:
        for f in u["features"]:
            lo, hi = f["baseline_interval"]
            assert u["baseline_interval"][0] <= lo < hi <= u["baseline_interval"][1]
            for p in f["baseline_samples"]:
                assert lo-.000001 <= p["time"] <= hi+.000001
                assert hashlib.sha256((ROOT/p["frame"]).read_bytes()).hexdigest() == p["frame_sha256"]
            if f["kind"] == "process":
                assert [p["phase"] for p in f["baseline_samples"]] == ["before", "during", "after"]
                assert f["baseline_samples"][0]["time"] < f["baseline_samples"][1]["time"] < f["baseline_samples"][2]["time"]
    features = {f["id"]: f for u in contract["units"] for f in u["features"]}
    assert "未显示移动点的精确x读数" in features["approach-without-attainment"]["claim"]
    assert "未展示尖点曲线" in features["nondifferentiable-candidates-caption"]["claim"]
    assert "不声称基线已展示纸盒几何" in features["next-modeling-feasible-dimensions"]["claim"]
    assert not any("outcome" in f for u in contract["units"] for f in u["features"])


def test_revision_identity_original_transport_and_no_other_lesson_dependency():
    plan = read("plan.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19ab5-b2d3-7003-a784-edeeaecdbc23"
    assert {r["author_agent"] for r in plan["contributors"]} == {"01a199e9-7432-7052-96f7-6bd6eb2e63bb", "019eaf8b-9151-75e2-9db4-5ff834335577"}
    assert revision_required(plan, profile_version="understanding-first-v3")
    assert plan["narration_draft"].endswith("narration-draft-v002.json")
    assert plan["revision_review"].endswith("math-derivative-ch07-extremes-20261102/review/regression-v003.json")
    assert transport_segments(read("narration.json")) == read("speech-plan.json")["segments"]
    for filename in FIXTURES.glob("*.json"):
        assert json.loads(filename.read_text())["status"] == "not_reviewed"
    assert read("baseline-lock.json")["timings_sha256"] == "81c219336dc9da96f511267c0509cdc8c00213bbb296728d2f8792eb768e4ebd"
    assert not any(f"derivative_ch{n:02}" in p for p in plan["sources"] for n in range(1, 9) if n != 7)
    old = read("baseline-plan.json")
    assert len({round(c["duration"]/p["duration"], 3) for c, p in zip(plan["cues"], old["cues"], strict=True)}) > 4


def test_missing_authored_stage_is_rejected(native):
    cue, time = native._cue, native.time
    native._cue = {"id": "closing", "start": time, "duration": 2, "stage_times": {}}
    try:
        with pytest.raises(ValueError, match="explicit authored stage time"):
            native.beat(.17)
    finally:
        native._cue = cue
