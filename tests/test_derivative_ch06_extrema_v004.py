"""CH06-B1 native proof checks; no raster, listening or review authority.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main/CI.
Lifecycle: this candidate; bound input/source/native API changes invalidate.
"""

import ast
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, transport_segments

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/derivative-ch06-extrema-v004"
SOURCE = ROOT / "examples/derivative_ch06_extrema_v004.py"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        if any(path.resolve().is_relative_to(ROOT / name) for name in ("runtime", "outputs")):
            raise AssertionError("Tests consume fixtures, not live inputs or review reports")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    class Probe(lesson.DerivativeCh06ExtremaV004):
        def snapshot(self):
            return {node.get_tex() for mob in self.mobjects for node in mob.get_family()
                if hasattr(node, "get_tex") and float(node.get_opacity()) > .9}

        def mark(self, identity):
            super().mark(identity)
            self.formulas[identity] = self.snapshot()

    def initialize(scene):
        scene.formulas = {}

    with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
        yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
                    {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def mark_local(native, placement, identity):
    audio = next(p["start"] for p in placement if p["cue"] == "necessary")
    return next(e["time"] for e in native.visual_events if e["id"] == identity)-audio


def test_entire_construct_keeps_the_original_seven_wavs_and_twenty_references(native, placement):
    plan = read("plan.json")
    assert native.time == pytest.approx(plan["duration"]) == pytest.approx(354.7)
    assert len(placement) == 7 and sum(len(r["references"]) for r in placement) == 20
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(335.04)
    assert not native._open_focus
    assert {w["id"] for w in native._closed_focus} == {f["id"] for f in plan["focus_intents"]}
    previous = 0
    for row, timing, intended in zip(placement, read("timings.json")["units"], plan["intended_full_wav_placement"], strict=True):
        assert row["start"] >= previous
        assert row["end"]-row["start"] == pytest.approx(timing["duration_seconds"])
        assert abs(row["start"]-intended["intended_start"]) < .04
        assert timing["wav_sha256"] == intended["wav_sha256"]
        assert all(p["focus_start"] <= p["visual_start"]+1e-8 and p["visual_end"] <= p["focus_end"]+1e-8 for p in row["phrases"])
        previous = row["end"]


def test_only_necessary_changes_and_no_other_lesson_clock_changes(lesson):
    previous = sys.modules["derivative_ch06_extrema_v003"].DerivativeCh06ExtremaV003
    for method in ("construct", "opening", "neighborhood", "signs", "turns", "stationary", "closing", "graph", "beat", "focus_end"):
        assert getattr(lesson.DerivativeCh06ExtremaV004, method) is getattr(previous, method)
    current, old = read("plan.json"), read("previous-plan.json")
    assert current["duration"] == old["duration"]
    assert current["intended_full_wav_placement"] == old["intended_full_wav_placement"]
    for new, prior in zip(current["cues"], old["cues"], strict=True):
        assert new["duration"] == prior["duration"]
        if new["id"] != "necessary":
            assert new == prior
    assert current["repair_constraints"]["nonblocking_M1_M2_not_changed"]


def test_interior_domain_and_nonzero_small_h_are_visible_before_the_comparison(native, placement):
    assert 10.9 < mark_local(native, placement, "interior_neighborhood_ready") < 11.3
    assert r"(a-\delta,a+\delta)\subset\mathrm{Dom}(f)" in native.formulas["interior_neighborhood_ready"]
    assert r"0<|h|<\delta" in native.formulas["interior_neighborhood_ready"]
    rows = [r for r in native.motion_samples if r["kind"] == "proof_neighborhood"]
    assert rows[0]["abs_h_over_delta"] == .75
    assert rows[-1]["abs_h_over_delta"] == pytest.approx(.16)
    assert any(.16 < r["abs_h_over_delta"] < .75 for r in rows)
    assert all(0 < r["abs_h_over_delta"] < 1 for r in rows)
    for row in rows:
        assert -3 < row["left"][0] < 0 < row["right"][0] < 3
        assert row["left"][0] == pytest.approx(-row["right"][0])
    assert "可导：左右得到同一个有限导数" in native.labels


def test_local_comparison_is_not_a_global_inequality_and_precedes_quotients(native, placement):
    state = native.formulas["local_comparison_ready"]
    assert r"0<|h|<\delta" in state and r"f(a+h)\leq f(a)" in state
    assert "局部极大：取足够小的邻域" in native.labels
    assert 18.3 < mark_local(native, placement, "local_comparison_ready") < 18.5
    assert 23.3 < mark_local(native, placement, "common_numerator_ready") < 23.6
    assert r"f(a+h)-f(a)\leq0" in native.formulas["common_numerator_ready"]


@pytest.mark.parametrize("stage", ["comparison_to_numerator", "negative_h_quotient", "positive_h_quotient"])
def test_real_semantic_value_moves_have_native_before_during_after_geometry(native, stage):
    rows = [r for r in native.motion_samples if r["kind"] == "proof_transfer" and r["stage"] == stage]
    assert len(rows) > 20
    assert all(r["copy_preserves_source"] for r in rows)
    assert rows[0]["time"] < rows[len(rows)//2]["time"] < rows[-1]["time"]
    for key in ("near", "center"):
        start = np.array(rows[0]["moving_centers"][key])
        target = np.array(rows[-1]["target_centers"][key])
        finish = np.array(rows[-1]["moving_centers"][key])
        assert np.linalg.norm(start-target) > .25
        np.testing.assert_allclose(finish, target, atol=1e-5)
        assert any(np.linalg.norm(np.array(r["moving_centers"][key])-start) > .05
                   and np.linalg.norm(np.array(r["moving_centers"][key])-target) > .05 for r in rows)
    assert rows[0]["pairs"] == [("near", "near"), ("center", "center")]


def test_same_nonpositive_numerator_with_signed_denominators_gives_both_quotients(native, placement):
    state = native.formulas["one_sided_quotients_ready"]
    assert {r"f(a+h)-f(a)\leq0", "h<0", "h>0",
            r"\frac{f(a+h)-f(a)}h\geq0", r"\frac{f(a+h)-f(a)}h\leq0"} <= state
    assert 27.6 < mark_local(native, placement, "left_quotient_ready") < 27.9
    assert 31.9 < mark_local(native, placement, "one_sided_quotients_ready") < 32.17


@pytest.mark.parametrize("numerator", [Fraction(0), Fraction(-1, 100), Fraction(-3, 2)])
@pytest.mark.parametrize("h", [Fraction(-1, 100), Fraction(-1, 5), Fraction(1, 100), Fraction(1, 5)])
def test_non_strict_quotient_sign_reason_includes_flat_local_values(numerator, h):
    quotient = numerator/h
    assert (quotient >= 0) if h < 0 else (quotient <= 0)
    minimum_quotient = (-numerator)/h
    assert (minimum_quotient <= 0) if h < 0 else (minimum_quotient >= 0)


def test_quotients_really_move_into_explicit_correct_one_sided_limits(native, placement):
    state = native.formulas["one_sided_limits_ready"]
    assert r"L=\lim_{h\to0^-}\frac{f(a+h)-f(a)}h\geq0" in state
    assert r"R=\lim_{h\to0^+}\frac{f(a+h)-f(a)}h\leq0" in state
    assert 34.6 < mark_local(native, placement, "one_sided_limits_ready") < 34.91
    rows = [r for r in native.motion_samples if r["kind"] == "proof_limit_transfer"]
    assert len(rows) > 40
    for side in ("left", "right"):
        for tag in ("near", "center", "bound"):
            assert np.linalg.norm(np.array(rows[0][side][tag])-rows[0]["target_"+side][tag]) > .3
            np.testing.assert_allclose(rows[-1][side][tag], rows[-1]["target_"+side][tag], atol=1e-5)
    assert all(r["left"]["near"][0] < 0 < r["right"]["near"][0] for r in rows)


def test_differentiability_equality_and_two_bounds_actually_precede_zero(native, placement):
    equal = native.formulas["equal_derivative_ready"]
    assert r"L=f'(a)=R" in equal and "可导" in native.labels
    state = native.formulas["common_zero_proved"]
    assert {r"L=f'(a)=R", r"f'(a)\geq0", r"f'(a)\leq0", r"\Longrightarrow\quad f'(a)=0"} <= state
    assert mark_local(native, placement, "one_sided_limits_ready") < mark_local(native, placement, "equal_derivative_ready") < mark_local(native, placement, "common_zero_proved")
    assert 35.4 < mark_local(native, placement, "equal_derivative_ready") < 35.74
    assert 40.2 < mark_local(native, placement, "common_zero_proved") < 40.47


def test_minimum_reverses_numerator_and_both_limit_bounds_without_changing_zero(native, placement):
    state = native.formulas["minimum_same_zero_ready"]
    assert r"0<|h|<\delta:\ f(a+h)-f(a)\geq0" in state
    assert r"L=\lim_{h\to0^-}\frac{f(a+h)-f(a)}h\leq0" in state
    assert r"R=\lim_{h\to0^+}\frac{f(a+h)-f(a)}h\geq0" in state
    assert r"L=f'(a)=R" in state and r"\Longrightarrow\quad f'(a)=0" in state
    assert 43.4 < mark_local(native, placement, "minimum_same_zero_ready") < 43.69


def test_proof_rows_are_removed_before_cusp_and_original_scope_handoff_remains(native):
    cusp = native.formulas["cusp_condition_ready"]
    assert "y=|x|" in cusp
    assert not any("lim_" in tex or "L=" in tex or "h|" in tex for tex in cusp)
    assert "可导的内点 a" in native.labels
    assert "0 是尖点极小，导数不存在" in native.labels
    assert "端点不套用“可导内点”的必要条件" in native.labels
    assert "如果和整个区间比较，端点怎么办？" in native.labels


def test_all_original_21_baseline_features_and_eight_triplets_remain_not_v003_baseline():
    contract, prior = read("contract.json"), read("previous-contract.json")
    validate_contract(contract)
    assert contract["units"] == prior["units"]
    assert contract["assets"] == prior["assets"]
    asset = contract["assets"]["visual_v001"]
    assert asset["duration"] == 292 and "/visual-v001/" in asset["path"]
    assert sum(len(u["features"]) for u in contract["units"]) == 21
    processes = [f for u in contract["units"] for f in u["features"] if f["kind"] == "process"]
    assert len(processes) == 8
    assert all([r["phase"] for r in f["baseline_samples"]] == ["before", "during", "after"] for f in processes)
    assert contract["repair_issue"]["id"] == "CH06-B1"
    assert not contract["repair_issue"]["author_resolution_approved"]
    assert "New explicit" in contract["additional_candidate_requirements"]["proof_gap_repair"]


def test_source_contributors_real_author_and_original_bytes_transport_are_fixed():
    plan = read("plan.json")
    assert plan["version"] == "v004" and plan["revision_mode"] == "revision"
    assert plan["author_agent"] == plan["author_context"] == "01a19acd-e149-74d0-8a5d-975a3adf45f4"
    assert plan["contributors"][:2] == read("previous-plan.json")["contributors"][:2]
    assert plan["revision_contract"].endswith("contract-v004.json")
    assert plan["revision_review"].endswith("regression-v004.json")
    assert plan["narration_draft"].endswith("narration-draft-v002.json")
    assert hashlib.sha256((FIXTURES / "narration.json").read_bytes()).hexdigest() == plan["narration_draft_sha256"]
    assert transport_segments(read("narration.json")) == read("transport.json")["segments"]
    assert read("timings.json")["production_input_sha256"] == "412d61d0bdaaf82d24ae8798cac66abc6e11a9ab44f9b2adef3d47d225ac734c"
    assert plan["status"] == read("contract.json")["status"] == "not_reviewed"
    assert not plan["production_boundary"]["rendered"] and not plan["production_boundary"]["published"]
    assert len(read("baseline-lock.json")["external_no_write_guards"]) == 61
    for row in read("baseline-lock.json")["protected_inputs"]:
        if row["path"].startswith("examples/"):
            assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_no_render_audio_network_or_approval_actions_and_all_state_has_lifecycle():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"render", "add_sound", "publish", "align_plan", "urlopen", "request"}
    for data in (read("plan.json"), read("contract.json"), read("baseline-lock.json"), read("timings.json")):
        assert all(data[key] for key in ("writer", "consumers", "lifecycle", "invalidation"))
