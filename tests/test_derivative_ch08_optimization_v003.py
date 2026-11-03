"""08 v003 focused fixture/native checks, not pixels, listening or approval.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main/CI.
Lifecycle: this frozen candidate; inputs, source or native API changes invalidate.
"""

import ast
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, transport_segments


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/derivative-ch08-optimization-v003"
SOURCE = ROOT / "examples/derivative_ch08_optimization_v003.py"


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
    class Probe(lesson.DerivativeCh08OptimizationV003):
        def snapshot(self):
            return {node.get_tex() for mob in self.mobjects for node in mob.get_family()
                if hasattr(node, "get_tex") and float(node.get_opacity()) > .9}

        def focus_begin(self, identity):
            super().focus_begin(identity)
            self.formula_states[identity] = self.snapshot()

        def mark(self, identity):
            super().mark(identity)
            self.anchor_formulas[identity] = self.snapshot()

    def initialize(scene):
        scene.formula_states, scene.anchor_formulas = {}, {}

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


def test_complete_native_construct_places_all_eight_intact_original_wavs(native, placement):
    plan, timings = read("plan.json"), read("timings.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-8)
    assert native.time > 358.88 > 312
    assert len(placement) == 8
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(358.88)
    assert sum(len(r["references"]) for r in placement) == 22
    assert {w["id"] for w in native._closed_focus} == {f["id"] for f in plan["focus_intents"]}
    assert not native._open_focus
    previous = 0
    for row, timing, intended in zip(placement, timings["units"], plan["intended_full_wav_placement"], strict=True):
        assert row["start"] >= previous
        assert row["end"]-row["start"] == pytest.approx(timing["duration_seconds"])
        assert abs(row["start"]-intended["intended_start"]) < .04
        assert timing["wav_sha256"] == intended["wav_sha256"]
        assert not intended["audio_trimmed"] and not intended["speed_changed"] and not intended["regenerated"]
        assert all(p["focus_start"] <= p["visual_start"]+1e-8 and p["visual_end"] <= p["focus_end"]+1e-8 for p in row["phrases"])
        previous = row["end"]


def test_one_cut_length_moves_with_spoken_enlargement_then_returns_to_two(native, placement):
    get = lambda t: at(native, placement, "cut", t, "cut_size")
    assert get(4)["x_cm"] == 1
    assert 1 < get(12)["x_cm"] < get(15.9)["x_cm"] < 3
    assert get(16.7)["x_cm"] == pytest.approx(3)
    assert 2 < get(17.5)["x_cm"] < 3
    assert get(19.2)["x_cm"] == get(22)["x_cm"] == pytest.approx(2)
    for row in (get(4), get(12), get(16.7), get(17.5), get(22)):
        assert row["base_cm"] == pytest.approx(12-2*row["x_cm"])
        assert row["removed_area_cm2"] == pytest.approx(4*row["x_cm"]**2)
    assert "x       12 − 2x       x" in native.labels
    start = next(p["start"] for p in placement if p["cue"] == "cut")
    mark = next(e["time"] for e in native.visual_events if e["id"] == "net_without_corners_ready")
    assert mark >= start+49.76


def test_new_projection_transition_keeps_exact_face_identities_and_endpoints(native, placement, lesson):
    original = sys.modules["derivative_ch08_optimization"]
    rows = [at(native, placement, "fold", t, "net_view") for t in (.28, 1.5, 3)]
    centimeter = original.panel_vertices(2, 0)
    planar = np.array([[original.net_point(a+2, b+2) for a, b, _ in centimeter[name]] for name in original.FACE_ORDER])
    oblique = np.array([[original.projected(p, 2) for p in centimeter[name]] for name in original.FACE_ORDER])
    np.testing.assert_allclose(rows[0]["screen_vertices"], planar, atol=1e-6)
    np.testing.assert_allclose(rows[2]["screen_vertices"], oblique, atol=1e-6)
    mid = np.array(rows[1]["screen_vertices"])
    assert np.linalg.norm(mid-planar) > .1 and np.linalg.norm(mid-oblique) > .1
    delta = oblique-planar
    alpha = np.sum((mid-planar)*delta)/np.sum(delta*delta)
    assert 0 < alpha < 1
    np.testing.assert_allclose(mid, planar+alpha*delta, atol=2e-6)
    assert all(r["face_order"] == list(lesson.FACE_ORDER) for r in rows)
    assert "New continuous" in read("contract.json")["additional_candidate_requirements"]["net_view_transition"]


def test_hinges_stay_fixed_and_fold_during_the_actual_raise_clause(native, placement):
    get = lambda t: at(native, placement, "fold", t, "fold")
    assert get(14.8)["angle"] == pytest.approx(0)
    assert 0 < get(20)["angle"] < get(26)["angle"] < math.pi/2
    assert get(29)["angle"] == pytest.approx(math.pi/2)
    fixed = get(14.8)["panel_vertices_cm"]
    for row in (get(14.8), get(20), get(26), get(29)):
        assert row["x_cm"] == 2
        np.testing.assert_allclose(row["panel_vertices_cm"]["base"], fixed["base"])
        for face in ("front", "back", "left", "right"):
            vertices = np.array(row["panel_vertices_cm"][face])
            np.testing.assert_allclose(vertices[:2], np.array(fixed[face])[:2])
            assert np.linalg.norm(vertices[2]-vertices[1]) == pytest.approx(2)
    assert any(r"8\times8\times2" in x for x in native.formula_states["fold_dimensions"])


def test_geometry_model_units_and_positive_domain_remain_present(native):
    assert r"\ell=w=12-2x,\quad h=x" in native.formula_states["dimensions_to_volume"]
    assert r"V=\ell w h=x(12-2x)^2" in native.formula_states["volume_objective"]
    assert r"V:\ \mathrm{cm}^3" in native.formula_states["volume_objective"]
    assert r"x>0,\quad12-2x>0" in native.formula_states["physical_domain"]
    assert r"0<x<6\quad(\mathrm{cm})" in native.formula_states["physical_domain"]
    assert "长度统一用 cm" in native.labels


def test_all_three_derivative_rows_remain_before_the_new_candidate_screen(native, placement):
    first = r"V'=(12-2x)^2-4x(12-2x)"
    second, third = r"=(12-2x)(12-6x)", r"=12(x-2)(x-6)"
    assert first in native.formula_states["product_derivative"]
    assert {first, second, third} <= native.anchor_formulas["factor_derivative_ready"]
    assert {first, second, third, r"V'=0:\ x=2,6;\quad6\notin(0,6)"} <= native.anchor_formulas["root_candidates_ready"]
    assert "只保留内部候选 x = 2" in native.labels
    start = next(p["start"] for p in placement if p["cue"] == "optimize")
    mark = next(e["time"] for e in native.visual_events if e["id"] == "root_candidates_ready")
    assert start+37.38 < mark < start+38.16
    peak = native.formula_states["volume_peak"]
    assert third in peak and first not in peak and second not in peak
    assert not any("notin" in t for t in peak)
    assert r"0<x<2:\ V'>0\qquad2<x<6:\ V'<0" in peak
    assert r"V(2)=2\times8^2=128\ \mathrm{cm}^3" in peak


def test_actual_boundary_geometry_flattening_then_narrowing_is_not_globally_decreasing(native, placement):
    get = lambda t: at(native, placement, "boundary", t, "boundary_box")
    assert .08 < get(3)["x_cm"] < 2
    assert get(8.4)["x_cm"] == get(10.5)["x_cm"] == pytest.approx(.08)
    assert .08 < get(13)["x_cm"] < get(16)["x_cm"] < 5.92
    assert get(17.5)["x_cm"] == get(18.3)["x_cm"] == pytest.approx(5.92)
    assert get(13)["volume_cm3"] > get(10.5)["volume_cm3"] > get(18.3)["volume_cm3"]
    for row in (get(3), get(8.4), get(13), get(16), get(18.3)):
        x = row["x_cm"]
        assert row["dimensions_cm"] == pytest.approx([12-2*x, 12-2*x, x])
        assert row["volume_cm3"] == pytest.approx(x*(12-2*x)**2)
    assert {r"x\to0^+:\ V\to0", r"x\to6^-:\ V\to0"} <= native.formula_states["degenerate_limits"]
    assert "退化边界不是可做的盒子" in native.labels


def test_new_height_constraint_enters_then_traverses_and_returns_on_decreasing_branch(native, placement):
    get = lambda t: at(native, placement, "constraint", t, "constrained_box")
    assert get(17.2)["x_cm"] == 2 and not get(17.2)["feasible"]
    assert get(20)["x_cm"] == get(24.8)["x_cm"] == pytest.approx(3)
    assert 3 < get(27)["x_cm"] < 4.5
    assert get(29.2)["x_cm"] == pytest.approx(4.5)
    assert 3 < get(30.8)["x_cm"] < 4.5
    assert get(31.9)["x_cm"] == get(36.8)["x_cm"] == pytest.approx(3)
    assert get(20)["volume_cm3"] > get(27)["volume_cm3"] > get(29.2)["volume_cm3"]
    assert get(29.2)["volume_cm3"] < get(30.8)["volume_cm3"] < get(36.8)["volume_cm3"] == pytest.approx(108)
    assert all(get(t)["feasible"] for t in (20, 24.8, 27, 29.2, 30.8, 31.9, 36.8))
    assert r"3\leq x<6\quad(\mathrm{cm})" in native.formula_states["height_constraint"]
    assert r"6\times6\times3=108\ \mathrm{cm}^3" in native.formula_states["constrained_optimum"]
    assert "[3,6) 上递减，左边界 x = 3 最优" in native.labels


def test_original_answer_is_restored_without_confusing_the_constrained_answer(native):
    end = native.formula_states["chapter_chain"]
    assert r"x=2\ \mathrm{cm},\quad V=128\ \mathrm{cm}^3" in end
    assert r"8\times8\times2\ \mathrm{cm}" in end
    assert not any("108" in t for t in end)
    assert "尺寸 → 同一变量 → 目标与可行域" in native.labels
    assert "变化率 → 单调性 → 全范围比较" in native.labels
    assert "约束改变，沿同一模型重新判断" in native.labels


def test_original_mathematics_and_six_native_methods_are_inherited(lesson):
    original = sys.modules["derivative_ch08_optimization"]
    for name in ("construct", "net", "panels", "opening", "cut", "objective", "boundary", "constraint", "closing"):
        assert getattr(lesson.DerivativeCh08OptimizationV003, name) is getattr(original.DerivativeCh08Optimization, name)
    assert lesson.panel_vertices is original.panel_vertices
    assert lesson.net_point is original.net_point
    for row in read("baseline-lock.json")["protected_inputs"]:
        if row["path"].startswith("examples/"):
            assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    assert len(read("baseline-lock.json")["external_no_write_guards"]) == 40


def test_actual_312_second_baseline_has_ten_complete_process_triplets():
    contract = read("contract.json")
    validate_contract(contract)
    assert contract["assets"]["visual_v001"]["duration"] == 312
    assert contract["assets"]["visual_v001"]["sha256"] == "fd1cc9eb07bf46dd6f7b6a4a070adfe8e160b803566effe8a790a4a6819ae6bd"
    assert len(contract["units"]) == 8
    features = [f for u in contract["units"] for f in u["features"]]
    assert len(features) == 25
    assert sum(f["kind"] == "process" for f in features) == 10
    for unit in contract["units"]:
        for f in unit["features"]:
            lo, hi = f["baseline_interval"]
            assert unit["baseline_interval"][0] <= lo < hi <= unit["baseline_interval"][1]
            if f["kind"] == "process":
                assert [r["phase"] for r in f["baseline_samples"]] == ["before", "during", "after"]
                a, b, c = [r["time"] for r in f["baseline_samples"]]
                assert a < b < c
    assert "New explicit" in contract["additional_candidate_requirements"]["root_screening"]


def test_original_narration_bytes_transport_and_real_author_identity():
    plan = read("plan.json")
    assert transport_segments(read("narration.json")) == read("transport.json")["segments"]
    assert hashlib.sha256((FIXTURES / "narration.json").read_bytes()).hexdigest() == plan["narration_draft_sha256"]
    assert plan["narration_draft"].endswith("narration-draft-v002.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19acd-e149-74d0-8a5d-975a3adf45f4"
    assert plan["contributors"][0]["author_agent"] == "01a199e9-7432-7052-96f7-6bd6eb2e63bb"
    assert plan["contributors"][1]["author_agent"] == "019eaf8b-9151-75e2-9db4-5ff834335577"
    assert plan["revision_mode"] == "revision" and plan["version"] == "v003"
    assert plan["status"] == read("contract.json")["status"] == "not_reviewed"
    assert read("timings.json")["fixture_only"] is True
    assert not plan["production_boundary"]["rendered"] and not plan["production_boundary"]["published"]
    for key in ("writer", "consumers", "lifecycle", "invalidation"):
        assert plan[key] and read("contract.json")[key]


def test_uncertain_production_word_points_are_retained_not_fabricated():
    timings = read("timings.json")
    assert timings["production_input_sha256"] == "34a6e44f5ceba10d031bb98fcedcabede14d90fa2c90f4bfb8bc832642c8aee8"
    uncertain = [p for u in timings["units"] for p in u["phrases"] if p.get("instantaneous_word_indices")]
    assert uncertain
    for phrase in uncertain:
        for index in phrase["instantaneous_word_indices"]:
            assert phrase["words"][index]["start"] == phrase["words"][index]["end"]
        assert "uncertain" in phrase["word_timing_warning"]


def test_old_optimize_cue_cannot_fit_the_full_real_wav():
    plan = read("plan.json")
    for cue in plan["cues"]:
        cue["duration"] = 54 if cue["id"] == "optimize" else 80
    plan["duration"] = sum(c["duration"] for c in plan["cues"])
    focuses = {"duration": plan["duration"], "windows": [
        {"id": f["id"], "start": .1, "end": plan["duration"]} for f in plan["focus_intents"]]}
    with pytest.raises(ValueError, match="ch08-optimize: no intersection"):
        schedule(visual_timeline(plan), read("narration.json"), focuses, read("timings.json"))


def test_missing_native_key_cannot_fall_back_to_old_fraction_scaling(lesson):
    scene = object.__new__(lesson.DerivativeCh08OptimizationV003)
    scene._cue = {"stage_times": {}}
    with pytest.raises(KeyError, match="0.15"):
        scene.beat(.15)


def test_candidate_has_no_media_or_audio_production_actions():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"render", "add_sound", "sound", "publish", "align_plan"}
