"""not_reviewed: chapter-05 native states, full-WAV bounds and baseline inventory."""

import ast
import hashlib
import json
import math
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract, revision_required
from manimind.review.meaning_units import schedule, transport_segments, validate_narration


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"examples/derivative_ch05_monotonicity_v004.py"
FIXTURES = ROOT/"tests/fixtures/derivative-ch05-monotonicity-v004"


def read(name):
    return json.loads((FIXTURES/name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def forbid_production_runtime_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT/"runtime"):
            raise AssertionError("Use versioned 05 v004 fixtures, never production runtime")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    import derivative_ch05_monotonicity as base

    class Probe(lesson.DerivativeMonotonicityLessonV004):
        def dot_positions(self):
            return sorted(tuple(float(x) for x in n.get_center()) for m in self.mobjects for n in m.get_family()
                if isinstance(n, base.Dot))

        def beat(self, fraction, *animations, **kwargs):
            super().beat(fraction, *animations, **kwargs)
            self.stage_trace.append({"cue": self._cue["id"], "key": f"{fraction:.2f}", "time": self.get_time()})

        def focus_begin(self, identity):
            super().focus_begin(identity)
            self.formula_states[identity] = {n.get_tex() for m in self.mobjects for n in m.get_family()
                if hasattr(n, "get_tex") and float(n.get_opacity()) > .9}
            self.dots_at_focus_start[identity] = self.dot_positions()

        def focus_end(self, identity):
            self.dots_at_focus_end[identity] = self.dot_positions()
            super().focus_end(identity)

    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            scene.motion_samples, scene.stage_trace, scene.formula_states = [], [], {}
            scene.dots_at_focus_start, scene.dots_at_focus_end = {}, {}
            patcher.setattr(base, "SemanticFormula", lesson.SemanticFormula)
        with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
        {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def at(native, placement, unit, local, kind, phase=None):
    row = next(r for r in placement if r["id"] == unit)
    target = row["start"]+local
    samples = [s for s in native.motion_samples if s["kind"] == kind and (phase is None or s.get("phase") == phase)]
    sample = min(samples, key=lambda s: abs(s["time"]-target))
    assert abs(sample["time"]-target) <= 1/30+.001
    return sample


def test_complete_native_scene_all_focuses_and_eight_original_wav_schedule(native, placement):
    plan, narration, timings = read("plan.json"), read("narration.json"), read("timings.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-8)
    assert native.time > 343.2
    assert len(placement) == len(timings["units"]) == 8
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(343.2)
    assert not native._open_focus
    assert {w["id"] for w in native._closed_focus} == {f["id"] for f in plan["focus_intents"]}
    validate_narration(narration, visual_timeline(plan), {"duration": native.time, "windows": native._closed_focus})
    previous = 0
    for row, timing, intended in zip(placement, timings["units"], plan["intended_full_wav_placement"], strict=True):
        assert row["start"] >= previous
        assert row["end"]-row["start"] == pytest.approx(timing["duration_seconds"])
        assert abs(row["start"]-intended["intended_start"]) <= .04
        for phrase in row["phrases"]:
            assert phrase["focus_start"] <= phrase["visual_start"]+.000001
            assert phrase["visual_end"] <= phrase["focus_end"]+.000001
        previous = row["end"]


def test_same_x_true_tracker_motion_and_linked_geometry(native, placement):
    first = at(native, placement, "monotonicity-u2", 13.7, "linked_graphs")
    middle = at(native, placement, "monotonicity-u2", 20, "linked_graphs")
    last = at(native, placement, "monotonicity-u2", 27.5, "linked_graphs")
    assert first["x"] == pytest.approx(-1.7)
    assert -1.7 < middle["x"] < -1.3
    assert last["x"] == pytest.approx(-1.3)
    assert native.dots_at_focus_start["same_x_result"] == native.dots_at_focus_end["same_x_result"]
    assert any(point == pytest.approx(last["curve_point"]) for point in native.dots_at_focus_end["same_x_result"])
    for s in [s for s in native.motion_samples if s["kind"] == "linked_graphs"][::43]:
        assert s["f"] == pytest.approx(s["x"]**3-3*s["x"])
        assert s["df"] == pytest.approx(3*(s["x"]**2-1))
        assert s["curve_point"] == pytest.approx([-.8+2*s["x"], 1.65+.30*s["f"], 0])
        assert s["derivative_point"] == pytest.approx([-.8+2*s["x"], -1.35+.14*s["df"], 0])
        left, right = s["tangent"]
        assert (right[1]-left[1])/(right[0]-left[0]) == pytest.approx(.15*s["df"])


def test_three_interval_sweep_reaches_and_holds_actual_minus_one_and_plus_one(native, placement):
    for t in [3, 9]:
        s = at(native, placement, "monotonicity-u3", t, "linked_graphs")
        assert s["x"] < -1 and s["df"] > 0
    for t in [14.8, 16.5, 18.2]:
        s = at(native, placement, "monotonicity-u3", t, "linked_graphs")
        assert s["x"] == pytest.approx(-1)
        assert s["df"] == pytest.approx(0)
        assert s["f"] == pytest.approx(2)
    for t in [21.5, 27.8]:
        s = at(native, placement, "monotonicity-u3", t, "linked_graphs")
        assert -1 < s["x"] < 1 and s["df"] < 0
    for t in [31.8, 34, 35.5]:
        s = at(native, placement, "monotonicity-u3", t, "linked_graphs")
        assert s["x"] == pytest.approx(1) and s["df"] == pytest.approx(0)
        assert s["f"] == pytest.approx(-2)
    assert at(native, placement, "monotonicity-u3", 40, "linked_graphs")["df"] > 0
    terminal = at(native, placement, "monotonicity-u3", 43.25, "linked_graphs")
    assert terminal["x"] == pytest.approx(2)
    assert native.dots_at_focus_start["sweep_result"] == native.dots_at_focus_end["sweep_result"]
    assert any(point == pytest.approx(terminal["curve_point"]) for point in native.dots_at_focus_end["sweep_result"])


def test_sign_chart_real_rows_keep_factor_identity_and_all_three_open_intervals(native):
    assert any(r"3(x-1)(x+1)" in t for t in native.formula_states["sign_boundaries"])
    assert any(r"x=-1" in t and r"x=1" in t for t in native.formula_states["sign_boundaries"])
    assert any(r"(-\infty,-1):+" in text and r"(-1,1):-" in text and r"(1,+\infty):+" in text for text in native.labels)
    windows = {w["id"]: w for w in native._closed_focus}
    assert windows["left_sign"]["start"] < windows["middle_sign"]["start"] < windows["right_sign"]["start"]


def test_interval_fixed_a_moving_b_and_frozen_secant_with_actual_witness(native, placement):
    a, b = -2, -1.15
    early = at(native, placement, "monotonicity-u5", 7.1, "linked_graphs")
    moving = at(native, placement, "monotonicity-u5", 11, "linked_graphs")
    endpoint = at(native, placement, "monotonicity-u5", 15, "linked_graphs")
    assert early["x"] == pytest.approx(-1.85)
    assert -1.85 < moving["x"] < b
    assert endpoint["x"] == pytest.approx(b)
    witness = at(native, placement, "monotonicity-u5", 23.3, "linked_graphs")
    f = lambda x: x**3-3*x
    secant = (f(b)-f(a))/(b-a)
    assert a < witness["x"] < b
    assert witness["x"] == pytest.approx(-math.sqrt((secant+3)/3))
    assert witness["df"] == pytest.approx(secant)
    assert native.dots_at_focus_start["secant_witness_result"] == native.dots_at_focus_end["secant_witness_result"]
    assert any(point == pytest.approx(witness["curve_point"]) for point in native.dots_at_focus_end["secant_witness_result"])
    assert any(r"f(b)-f(a)=f'(c)(b-a)>0" in t and r"a<c<b" in t for t in native.formula_states["interval_theorem"])
    assert any(r"f(a)>f(b)" in t for t in native.formula_states["interval_decreasing"])


def test_cube_zero_pause_is_real_then_motion_continues_and_reason_is_retained(native, placement):
    assert at(native, placement, "monotonicity-u6", 3.5, "cube_motion")["x"] < 0
    for t in [7.1, 9.5, 11.5]:
        s = at(native, placement, "monotonicity-u6", t, "cube_motion")
        assert s["x"] == pytest.approx(0) and s["f"] == pytest.approx(0) and s["df"] == pytest.approx(0)
    assert at(native, placement, "monotonicity-u6", 14.5, "cube_motion")["x"] > 0
    assert any(r"f'(0)=0" in t for t in native.formula_states["cube_zero_state"])
    assert any(r"b^3-a^3=(b-a)(a^2+ab+b^2)>0" in t for t in native.formula_states["cube_interval_reason"])
    for s in [s for s in native.motion_samples if s["kind"] == "cube_motion"][::29]:
        assert s["f"] == pytest.approx(s["x"]**3)
        assert s["df"] == pytest.approx(3*s["x"]**2)
        assert s["point"] == pytest.approx([2.6*s["x"], .45+.42*s["x"]**3, 0])


def test_both_disconnected_branch_motions_use_full_ranges_and_never_touch_zero(native, placement):
    rows = [s for s in native.motion_samples if s["kind"] == "reciprocal_branch"]
    for phase, lo, hi in [("left", -2, -1), ("right", .5, 1)]:
        samples = [s for s in rows if s["phase"] == phase]
        assert samples[0]["x"] == pytest.approx(lo) and samples[-1]["x"] == pytest.approx(hi)
        assert all(lo <= s["x"] <= hi and s["x"] != 0 for s in samples)
        assert all(a["x"] <= b["x"]+.000000001 and a["q"] <= b["q"]+.000000001 for a, b in zip(samples, samples[1:]))
        for s in samples[::17]:
            assert s["q"] == pytest.approx(-1/s["x"])
            assert s["dq"] == pytest.approx(1/s["x"]**2) and s["dq"] > 0
            assert s["point"] == pytest.approx([-2.25+1.15*s["x"], .1-.75/s["x"], 0])
    left = at(native, placement, "monotonicity-disconnected-u-v002", 10, "reciprocal_branch", "left")
    right = at(native, placement, "monotonicity-disconnected-u-v002", 16, "reciprocal_branch", "right")
    assert -2 < left["x"] < -1 and .5 < left["q"] < 1
    assert .5 < right["x"] < 1 and -2 < right["q"] < -1


def test_cross_gap_order_and_interval_condition_follow_two_completed_branches(native):
    pair = next(s for s in native.motion_samples if s["kind"] == "disconnected_comparison")
    assert (pair["a"], pair["qa"], pair["b"], pair["qb"]) == (-1, 1, 1, -1)
    assert pair["output_difference"] == -2 and pair["whole_interval_defined"] is False
    assert any(r"q(-1)=1>q(1)=-1" in t for t in native.formula_states["cross_gap_comparison"])
    assert any(r"q(0)" in t and "undefined" in t for t in native.formula_states["gap_interval_condition"])
    assert any("分别在 (-∞,0)、(0,+∞) 递增；跨过 0 不能合并" in t for t in native.labels)
    windows = {w["id"]: w for w in native._closed_focus}
    assert windows["branch_left_motion"]["end"] < windows["branch_right_motion"]["start"]
    assert windows["branch_right_motion"]["end"] < windows["cross_gap_comparison"]["start"]
    assert windows["cross_gap_comparison"]["start"] < windows["gap_interval_condition"]["start"] < windows["separate_intervals"]["start"]


def test_all_fourteen_old_functions_and_six_actual_v002_bridge_features_are_bound():
    contract = read("contract.json")
    validate_contract(contract)
    assert set(contract["assets"]) == {"visual_v002"}
    asset = contract["assets"]["visual_v002"]
    assert asset["duration"] == 396
    assert asset["sha256"] == "133c162efefff0fb94f5111547144129be6c6573b8b973510faa47ea18a7a2ec"
    assert "/visual-v002/" in asset["path"]
    assert contract["legacy_feature_count"] == 14 and contract["added_v002_feature_count"] == 6
    assert sum(len(u["features"]) for u in contract["units"]) == 20
    old = json.loads((ROOT/"tests/fixtures/derivative-ch05-monotonicity/v002/content-regression-contract.json").read_text())
    prior = {f["id"]: f for u in old["units"] for f in u["features"]}
    current = {f["id"]: f for u in contract["units"] for f in u["features"]}
    for name, feature in prior.items():
        assert (current[name]["kind"], current[name]["claim"]) == (feature["kind"], feature["claim"])
    ids = {f["id"] for f in read("plan.json")["focus_intents"]}
    for unit in contract["units"]:
        for feature in unit["features"]:
            lo, hi = feature["baseline_interval"]
            assert unit["baseline_interval"][0] <= lo < hi <= unit["baseline_interval"][1]
            assert set(feature["candidate_focus_ids"]) <= ids
            assert all(lo-.000001 <= p["time"] <= hi+.000001 and len(p["frame_sha256"]) == 64 for p in feature["baseline_samples"])
            if feature["kind"] == "process":
                samples = feature["baseline_samples"]
                assert [s["phase"] for s in samples] == ["before", "during", "after"]
                assert samples[0]["time"] < samples[1]["time"] < samples[2]["time"]


def test_new_wrapper_inherits_all_math_semantics_geometry_and_frozen_source_bytes(lesson):
    import derivative_ch05_monotonicity_v002 as original
    for method in ["opening", "same_x", "plots", "sweep", "signs", "interval", "zero_point", "disconnected_domain", "branch_motion", "handoff"]:
        assert getattr(lesson.DerivativeMonotonicityLessonV004, method) is getattr(original.DerivativeMonotonicityLessonV002, method)
    for row in read("baseline-lock.json")["sources"]:
        assert hashlib.sha256((ROOT/row["path"]).read_bytes()).hexdigest() == row["sha256"]
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    assert {n.name for n in cls.body if isinstance(n, ast.FunctionDef)} == {"construct", "beat"}


def test_revision_identity_original_transport_and_no_other_lesson_dependency():
    plan = read("plan.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19ab5-b2d3-7003-a784-edeeaecdbc23"
    assert {r["author_agent"] for r in plan["contributors"]} == {"01a199e9-73ab-7700-8a9f-cd7b5541b0ad", "019eaf8b-9151-75e2-9db4-5ff834335577"}
    assert revision_required(plan, profile_version="understanding-first-v3")
    assert plan["narration_draft"].endswith("narration-draft-v003.json")
    assert plan["revision_review"].endswith("math-derivative-ch05-monotonicity-20261102/review/regression-v004.json")
    assert all(read(n)["status"] == "not_reviewed" for n in ["plan.json", "contract.json", "narration.json", "timings.json", "baseline-lock.json"])
    assert read("baseline-lock.json")["timings_sha256"] == "020be85bf6364d3d0c1cff2701d4457c16c4e5db54d79e693c20697a7fffc20f"
    assert len(transport_segments(read("narration.json"))) == 8
    assert not any("derivative_ch02" in p or "derivative_ch03" in p or "derivative_ch04" in p for p in plan["sources"])
    old = json.loads((ROOT/"tests/fixtures/derivative-ch05-monotonicity/v002/plan.json").read_text())
    assert len({round(c["duration"]/p["duration"], 3) for c, p in zip(plan["cues"], old["cues"], strict=True)}) > 4


def test_missing_authored_stage_time_is_rejected_instead_of_using_visual_fraction(native):
    cue, time = native._cue, native.time
    native._cue = {"id": "handoff", "start": time, "duration": 2, "stage_times": {}}
    try:
        with pytest.raises(ValueError, match="explicit authored stage time"):
            native.beat(.17)
    finally:
        native._cue = cue
