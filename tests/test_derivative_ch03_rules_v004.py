"""not_reviewed: native chapter-03 timing/state tests, no GL, TeX or audio edits."""

import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import revision_required, validate_contract
from manimind.review.meaning_units import schedule, transport_segments, validate_narration


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT/"tests/fixtures/derivative-ch03-rules-v004"
SOURCE = ROOT/"examples/derivative_ch03_rules_v004.py"


def read(name):
    return json.loads((FIXTURES/name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def forbid_production_runtime_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT/"runtime"):
            raise AssertionError("Tests consume versioned ch03 fixtures, not production runtime")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT/"examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    import derivative_ch03_rules as original
    import derivative_chapter_shared as shared

    class Probe(lesson.DerivativeRulesLessonV004):
        def beat(self, fraction, *animations, **kwargs):
            super().beat(fraction, *animations, **kwargs)
            self.stage_trace.append({"cue": self._cue["id"], "key": f"{fraction:.2f}", "time": self.get_time()})

        def focus_begin(self, identity):
            super().focus_begin(identity)
            self.formula_states[identity] = {n.get_tex() for m in self.mobjects for n in m.get_family()
                if hasattr(n, "get_tex") and float(n.get_opacity()) > .9}
            self.live_referents[identity] = [m for m in self.mobjects]

        def area(self, initial=.6):
            objects = super().area(initial)
            self.area_objects.append((self._cue["id"], objects))
            return objects

        def sample(self, kind, **values):
            if kind == "product_area" and self.area_objects:
                cue, (_, right, top, corner, _) = self.area_objects[-1]
                if cue == self._cue["id"]:
                    values.update(right_box=[right.get_left().tolist(), right.get_right().tolist(), right.get_top().tolist(), right.get_bottom().tolist()],
                        top_box=[top.get_left().tolist(), top.get_right().tolist(), top.get_top().tolist(), top.get_bottom().tolist()],
                        corner_box=[corner.get_left().tolist(), corner.get_right().tolist(), corner.get_top().tolist(), corner.get_bottom().tolist()])
            super().sample(kind, **values)

    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            scene.motion_samples, scene.stage_trace, scene.formula_states = [], [], {}
            scene.area_objects, scene.live_referents = [], {}
            patcher.setattr(original, "SemanticFormula", lesson.SemanticFormula)
            patcher.setattr(shared, "SemanticFormula", lesson.SemanticFormula)

        with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
                    {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def at(native, placement, unit, local, kind):
    row = next(r for r in placement if r["id"] == unit)
    time = row["start"]+local
    choices = [s for s in native.motion_samples if s["kind"] == kind]
    sample = min(choices, key=lambda s: abs(s["time"]-time))
    assert abs(sample["time"]-time) <= 1/30+.001
    return sample


def test_full_native_clock_all_references_and_nine_intact_original_wavs(native, placement):
    plan, narration, timings = read("plan.json"), read("narration.json"), read("timings.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-8)
    assert native.time > 402.24 > 378
    assert len(placement) == len(timings["units"]) == 9
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(402.24)
    assert not native._open_focus and not native._drivers
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


def test_semantic_increment_transfer_prepares_next_clause_in_real_recorded_pause(native, placement):
    row = next(r for r in placement if r["id"] == "linearity_unit")
    timing = next(r for r in read("timings.json")["units"] if r["id"] == row["id"])
    first, second = timing["phrases"][:2]
    copied = next(s for s in native.motion_samples if s["kind"] == "formula_copy")
    complete = next(s for s in native.motion_samples if s["kind"] == "formula_complete")
    assert row["start"]+first["end"] <= copied["time"] < complete["time"] <= row["start"]+second["start"]+.04
    assert copied["stage"] == complete["stage"] == "linear_divide_h"
    assert r"\Delta u" in copied["source"] and r"\Delta v" in copied["source"]
    assert r"\frac{\Delta u}h" in complete["target"] and r"\frac{\Delta v}h" in complete["target"]


def test_linearity_motion_occurs_during_shared_h_clause_then_holds(native, placement):
    assert at(native, placement, "linearity_unit", 39, "linear_increments")["h"] == pytest.approx(.5)
    mid = at(native, placement, "linearity_unit", 44.1, "linear_increments")
    assert .05 < mid["h"] < .5
    assert at(native, placement, "linearity_unit", 48, "linear_increments")["h"] == pytest.approx(.05)
    for s in [s for s in native.motion_samples if s["kind"] == "linear_increments"][::43]:
        assert s["x"] == 1
        assert s["du"] == pytest.approx(2*s["h"]+s["h"]**2)
        assert s["dv"] == pytest.approx(s["h"])
        assert s["sum_increment"] == pytest.approx(s["du"]+s["dv"])
        assert s["difference_increment"] == pytest.approx(s["du"]-s["dv"])


def test_all_original_area_values_and_polygon_geometry_are_unchanged(native):
    samples = [s for s in native.motion_samples if s["kind"] == "product_area" and "corner_box" in s]
    assert samples
    for s in samples[::41]:
        assert s["u"] == 3 and s["v"] == 2
        assert s["du"] == s["h"]
        assert s["dv"] == pytest.approx(2*s["h"]+s["h"]**2)
        assert s["increment"] == pytest.approx(s["right"]+s["top"]+s["corner"])
        for key, width, height in [("right_box", s["du"], s["v"]), ("top_box", s["u"], s["dv"]), ("corner_box", s["du"], s["dv"])]:
            left, right, top, bottom = map(np.array, s[key])
            assert right[0]-left[0] == pytest.approx(.85*width, abs=2e-6)
            assert top[1]-bottom[1] == pytest.approx(.85*height, abs=2e-6)


def test_product_strips_and_corner_remain_distinct_visible_referents(native):
    formulas = native.formula_states
    assert any(r"v\,\Delta u" in t for t in formulas["product_right"])
    assert not any(r"u\,\Delta v" in t for t in formulas["product_right"])
    assert any(r"u\,\Delta v" in t for t in formulas["product_top"])
    assert not any(r"\Delta u\,\Delta v" in t for t in formulas["product_top"])
    assert any(r"\Delta u\,\Delta v" in t for t in formulas["product_corner"])
    assert any(r"v\Delta u+u\Delta v+\Delta u\Delta v" in t for t in formulas["product_exact_increment"])
    windows = {w["id"]: w for w in native._closed_focus}
    assert windows["product_right"]["start"] < windows["product_top"]["start"] < windows["product_corner"]["start"]


def test_normalized_corner_changes_with_real_h_phrase_not_an_empty_wait(native, placement):
    assert at(native, placement, "product_limit_unit", 25.6, "product_area")["h"] == pytest.approx(.6)
    mid = at(native, placement, "product_limit_unit", 30, "product_area")
    assert .025 < mid["h"] < .6
    final = at(native, placement, "product_limit_unit", 40, "product_area")
    assert final["h"] == pytest.approx(.025)
    assert final["corner"]/final["h"] == pytest.approx(.050625)
    assert final["corner"]/final["h"] != 0
    assert any(r"\Delta u\Delta v/h\approx" in t for t in native.formula_states["product_corner_shrink"])
    assert any(r"(uv)'=u'v+uv'" in t for t in native.formula_states["product_rule"])


def test_quotient_preserves_both_denominators_cancellation_and_negative_term(native):
    states = native.formula_states
    assert any(r"\frac{u+\Delta u}{v+\Delta v}-\frac uv" in t for t in states["quotient_difference"])
    assert any(r"v\ne0,\qquad v+\Delta v\ne0" in t for t in states["quotient_difference"])
    assert any(r"v(u+\Delta u)-u(v+\Delta v)" in t for t in states["quotient_common_denominator"])
    assert any(r"v\Delta u-u\Delta v" in t and r"v(v+\Delta v)" in t for t in states["quotient_cancel"])
    assert any(r"v(u+\Delta u)-u(v+\Delta v)" in t for t in states["quotient_cancel"])
    assert any(r"v(\Delta u/h)-u(\Delta v/h)" in t for t in states["quotient_divide_h"])
    assert any(r"\Delta v\to0" in t for t in states["quotient_take_limit"])
    assert any(r"\frac{u'v-uv'}{v^2}" in t and r"v\ne0" in t for t in states["quotient_rule"])


def test_product_example_keeps_both_factor_derivatives_and_both_result_terms(native):
    assert any(r"u=x^2,\quad u'=2x;" in t and r"v=\sin x,\quad v'=\cos x" in t
               for t in native.formula_states["product_example_derivatives"])
    assert any(r"2x\sin x+x^2\cos x" in t for t in native.formula_states["product_example_result"])
    assert any(r"\mathrm{rad}" in t for t in native.formula_states["product_example_factors"])


def test_cost_true_motion_matches_negative_zero_hold_positive_phrases(native, placement):
    before = at(native, placement, "cost_example_unit", 44.2, "average_cost")
    assert before["x"] == pytest.approx(1)
    moving = at(native, placement, "cost_example_unit", 47.8, "average_cost")
    assert 1 < moving["x"] < 2 and moving["derivative"] < 0
    for local in [49.3, 53.5, 56.5, 58.9, 59.5]:
        s = at(native, placement, "cost_example_unit", local, "average_cost")
        assert s["x"] == pytest.approx(2)
        assert s["average_cost"] == pytest.approx(4)
        assert s["derivative"] == pytest.approx(0)
    rising = at(native, placement, "cost_example_unit", 61.5, "average_cost")
    assert rising["x"] > 2 and rising["derivative"] > 0
    final = at(native, placement, "cost_example_unit", 65.5, "average_cost")
    assert final["x"] == pytest.approx(4)
    assert final["average_cost"] == pytest.approx(5)


def test_cost_coordinate_mapping_and_units_come_from_original_model(native):
    for s in [s for s in native.motion_samples if s["kind"] == "average_cost"][::37]:
        assert s["total_cost"] == pytest.approx(s["x"]**2+4)
        assert s["average_cost"] == pytest.approx(s["x"]+4/s["x"])
        assert s["derivative"] == pytest.approx(1-4/s["x"]**2)
        assert s["point"] == pytest.approx([-6+1.33*(s["x"]-.5), -1.7+.60*(s["average_cost"]-3.5), 0], abs=1e-6)
    assert any(r"x>0" in t for t in native.formula_states["cost_model"])
    assert "连续产量模型：x 百件，C(x) 百元，A(x) 元/件" in native.labels


def test_no_focus_is_extended_past_its_original_actual_process_objects(native):
    windows = {w["id"]: w for w in native._closed_focus}
    assert windows["product_corner_shrink"]["end"] < windows["product_rule"]["start"]
    assert windows["cost_decreasing"]["end"] < windows["cost_stationary"]["start"]
    assert windows["cost_stationary"]["end"] < windows["cost_increasing"]["start"]


def test_full_v002_baseline_inventory_has_real_feature_intervals_and_process_triples():
    contract = read("contract.json")
    validate_contract(contract)
    assert set(contract["assets"]) == {"visual_v002"}
    asset = contract["assets"]["visual_v002"]
    assert asset["duration"] == 378
    assert asset["sha256"] == "8f457f542a058e7707b5779e92479b477c323f7666b5c16dfd906102d6909706"
    assert "/visual-v002/" in asset["path"]
    assert sum(len(u["features"]) for u in contract["units"]) == 30
    ids = {f["id"] for f in read("plan.json")["focus_intents"]}
    for unit in contract["units"]:
        for feature in unit["features"]:
            lo, hi = feature["baseline_interval"]
            assert unit["baseline_interval"][0] <= lo < hi <= unit["baseline_interval"][1]
            assert set(feature["candidate_focus_ids"]) <= ids
            assert all(lo-.000001 <= e["time"] <= hi+.000001 and len(e["frame_sha256"]) == 64 for e in feature["baseline_samples"])
            if feature["kind"] == "process":
                samples = feature["baseline_samples"]
                assert [e["phase"] for e in samples] == ["before", "during", "after"]
                assert samples[0]["time"] < samples[1]["time"] < samples[2]["time"]


def test_native_methods_numpy_endpoint_fix_and_frozen_files_are_unchanged(lesson):
    import derivative_ch03_rules as original
    for cue in read("plan.json")["cues"]:
        assert getattr(lesson.DerivativeRulesLessonV004, cue["id"]) is getattr(original.DerivativeRulesLesson, cue["id"])
    for item in read("baseline-lock.json")["sources"]:
        assert hashlib.sha256((ROOT/item["path"]).read_bytes()).hexdigest() == item["sha256"]
    tree = ast.parse((ROOT/"examples/derivative_ch03_rules.py").read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "put_start_and_end_on"]
    assert all(not isinstance(a, ast.List) for n in calls for a in n.args[:2])
    wrapper = ast.parse(SOURCE.read_text())
    cls = next(n for n in wrapper.body if isinstance(n, ast.ClassDef))
    assert {n.name for n in cls.body if isinstance(n, ast.FunctionDef)} == {"beat", "safe_formula"}


def test_authorship_revision_narration_reuse_and_no_02_source_dependency():
    plan = read("plan.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19ab5-b2d3-7003-a784-edeeaecdbc23"
    assert {r["author_agent"] for r in plan["contributors"]} == {"01a199e9-7383-7a03-b45c-97d3d21bd9dd", "019eaf8b-9151-75e2-9db4-5ff834335577"}
    assert revision_required(plan, profile_version="understanding-first-v3")
    assert plan["revision_mode"] == "revision"
    assert plan["narration_draft"].endswith("narration-draft-v003.json")
    assert plan["revision_review"].endswith("math-derivative-ch03-rules-20261102/review/regression-v004.json")
    assert all(read(n)["status"] == "not_reviewed" for n in ["plan.json", "contract.json", "narration.json", "timings.json", "baseline-lock.json"])
    assert len(transport_segments(read("narration.json"))) == 9
    assert not any("ch02" in p or "audio-retime-author/" in p for p in plan["sources"])


def test_old_18_second_opening_cannot_contain_untouched_full_wav(native):
    plan = read("plan.json")
    reduction = plan["cues"][0]["duration"]-18
    plan["cues"][0]["duration"] = 18
    plan["cues"][-1]["duration"] += reduction
    with pytest.raises(ValueError, match="opening_unit: no intersection"):
        schedule(visual_timeline(plan), read("narration.json"),
                 {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))
