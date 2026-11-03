"""04 v003 author checks: native clock/fixtures, never media or approval.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main/CI.
Lifetime: this fixture revision; source, input or native API changes invalidate.
"""

import ast
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, transport_segments, validate_narration


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/derivative-ch04-chain-v003"
SOURCE = ROOT / "examples/derivative_ch04_chain_v003.py"
AUTHOR = "01a19acd-e149-74d0-8a5d-975a3adf45f4"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_live_production_reads(monkeypatch):
    original = Path.open

    def checked(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT / "runtime") or path.resolve().is_relative_to(ROOT / "outputs"):
            raise AssertionError("Offline tests must use v003 fixtures, not production files")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", checked)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    import derivative_ch04_chain as original

    class Probe(lesson.DerivativeChainLessonV003):
        def beat(self, fraction, *animations, **kwargs):
            before = self.get_time()
            super().beat(fraction, *animations, **kwargs)
            self.stage_trace.append({"cue": self._cue["id"], "key": f"{fraction:.2f}",
                                     "before": before, "after": self.get_time()})

        def formula_states(self):
            return {node.get_tex() for mob in self.mobjects for node in mob.get_family()
                    if hasattr(node, "get_tex") and float(node.get_opacity()) > .9}

        def focus_begin(self, identity):
            super().focus_begin(identity)
            self.formulas_at_begin[identity] = self.formula_states()

        def focus_end(self, identity):
            self.formulas_at_end[identity] = self.formula_states()
            super().focus_end(identity)

    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            scene.stage_trace, scene.formulas_at_begin, scene.formulas_at_end = [], {}, {}
            patcher.setattr(original, "SemanticFormula", lesson.SemanticFormula)

        with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
                    {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def at(native, placement, local):
    start = next(row["start"] for row in placement if row["id"] == "chain-u03")
    samples = [s for s in native.motion_samples if s["kind"] == "chain_transfer"]
    sample = min(samples, key=lambda s: abs(s["time"]-start-local))
    assert abs(sample["time"]-start-local) <= 1/30+.001
    return sample


def test_all_eight_intact_wavs_fit_all_26_original_references(native, placement):
    plan, timings, draft = read("plan.json"), read("timings.json"), read("narration.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-8)
    assert native.time > 336
    assert sum(row["duration_seconds"] for row in placement) == pytest.approx(324.48)
    assert len(placement) == 8
    assert sum(len(row["references"]) for row in placement) == 26
    assert not native._open_focus
    validate_narration(draft, visual_timeline(plan), {"duration": native.time, "windows": native._closed_focus})
    assert {w["id"] for w in native._closed_focus} == {f["id"] for f in plan["focus_intents"]}
    previous = 0
    for row, timing, intended in zip(placement, timings["units"], plan["intended_full_wav_placement"], strict=True):
        assert row["start"] >= previous
        assert row["end"]-row["start"] == pytest.approx(timing["duration_seconds"])
        assert row["duration_seconds"] == intended["duration_seconds"]
        assert abs(row["start"]-intended["intended_start"]) < .04
        assert timing["wav_sha256"] == intended["wav_sha256"]
        for phrase in row["phrases"]:
            assert phrase["focus_start"] <= phrase["visual_start"]+1e-8
            assert phrase["visual_end"] <= phrase["focus_end"]+1e-8
        previous = row["end"]


def test_each_spoken_change_has_initial_motion_and_terminal_states(native, placement):
    assert at(native, placement, 1.0)["x"] == 1
    assert 1 < at(native, placement, 2.4)["x"] < 1.1
    assert at(native, placement, 3.4)["x"] == pytest.approx(1.1)
    assert at(native, placement, 9.9)["u"] == 2
    assert 2 < at(native, placement, 10.9)["u"] < 2.21
    assert at(native, placement, 11.9)["u"] == pytest.approx(2.21)
    assert at(native, placement, 17.9)["y"] == 8
    assert 8 < at(native, placement, 18.5)["y"] < 10.793861
    assert at(native, placement, 19.3)["y"] == pytest.approx(10.793861)
    assert at(native, placement, 20.7)["y"] == pytest.approx(10.793861)


def test_same_variables_remain_frozen_until_their_own_stage(native, placement):
    samples = [s for s in native.motion_samples if s["kind"] == "chain_transfer"]
    for s in samples:
        if s["phase"] == "input":
            assert s["u"] == 2 and s["y"] == 8
        elif s["phase"] == "inner":
            assert s["x"] == pytest.approx(1.1) and s["y"] == 8
        else:
            assert s["x"] == pytest.approx(1.1) and s["u"] == pytest.approx(2.21)
    start = next(r["start"] for r in placement if r["id"] == "chain-u03")
    phrases = next(r["phrases"] for r in placement if r["id"] == "chain-u03")
    for index, key in enumerate(("x", "u", "y")):
        changing = [b for a, b in zip(samples, samples[1:]) if abs(b[key]-a[key]) > 1e-12]
        assert len(changing) >= 20
        assert changing[0]["time"] >= phrases[index]["visual_start"]
        assert changing[-1]["time"] <= phrases[index]["visual_end"]+.001
    assert samples[-1]["time"] < start+21


def test_process_focus_has_real_deltas_then_closes_before_next_phase(native):
    windows = {row["id"]: row for row in native._closed_focus}
    for focus, literal in (("input_change", r"\Delta x=0.1"),
                           ("inner_change", r"\Delta u=0.21")):
        assert literal in native.formulas_at_end[focus]
    assert windows["input_change"]["end"] < windows["inner_change"]["start"]
    assert windows["inner_change"]["end"] < windows["outer_change"]["start"]
    assert windows["outer_change"]["end"] < windows["transfer_complete"]["start"]
    assert r"\Delta y=2.793861" in native.formulas_at_begin["transfer_complete"]


def test_three_ratio_rows_appear_during_the_actual_shrinking_clause(native, placement):
    start = next(r["start"] for r in placement if r["id"] == "chain-u04")
    marks = {r["id"]: r["time"] for r in native.visual_events}
    windows = {r["id"]: r for r in native._closed_focus}
    rows = [r for r in native.motion_samples if r["kind"] == "ratio_row"]
    assert [r["h"] for r in rows] == [.1, .01, .001]
    assert windows["ratio_limit"]["start"] < rows[0]["time"] < rows[1]["time"] < rows[2]["time"]
    for row, local in zip(rows, (36.0, 38.94, 40.84), strict=True):
        assert abs(row["time"]-start-local) < .04
        assert row["total_ratio"] == pytest.approx(row["inner_ratio"]*row["outer_ratio"])
    assert abs(marks["ratio_limit_ready"]-start-46.68) < .04
    assert rows[2]["time"] < marks["ratio_limit_ready"]


def test_all_original_formula_reasons_and_conditions_are_real_native_states(native):
    required = {"inner_named": r"u=x^2+1", "two_levels": r"y=u^3",
        "ratio_identity": r"\frac{\Delta y}{\Delta x}", "nonzero_increment": r"h(2+h)\ne0",
        "chain_rule": r"y'=f'(u)\,g'(x)", "small_change_reason": r"12\Delta u+6(\Delta u)^2+(\Delta u)^3",
        "chain_example_result": r"y'(1)=24", "linear_increment": r"\Delta u=a\,\Delta x",
        "linear_chain": r"f'(ax+b)\cdot a", "zero_linear_constant": r"a=0:\quad u=b,\quad y=f(b)",
        "affine_inner": r"u'=3", "affine_outer": r"f'(u)=4u^3", "affine_product": r"12(3x-1)^3",
        "chain_summary": r"y'=f'(u)u'"}
    for focus, literal in required.items():
        assert any(literal in tex for tex in native.formulas_at_begin[focus]), (focus, literal)
    assert "f(b) 有定义时，这是常数函数，导数为 0" in native.labels
    assert "这两个多项式复合，对所有实数 x 都可导" in native.labels


def test_new_root_and_log_support_distinguishes_boundary_and_domains(native, placement):
    formulas = native.formulas_at_end["chain_domain_examples"]
    assert any(r"\sqrt{2x+1}" in tex and r"x\ge-\frac12" in tex and r"x>-\frac12" in tex for tex in formulas)
    assert any(r"\ln(2x+1)" in tex and r"\frac2{2x+1}" in tex and r"x>-\frac12" in tex for tex in formulas)
    row = next(r for r in placement if r["id"] == "chain-u06")
    marks = {r["id"]: r["time"] for r in native.visual_events}
    assert row["start"]+33.48 < marks["chain_root_domain_ready"] < row["start"]+35.44
    assert marks["chain_root_domain_ready"] < marks["chain_log_domain_ready"] < row["end"]
    assert not read("plan.json")["new_visual_support"]["narration_changed"]


def test_existing_nonlocal_math_and_geometry_are_inherited_not_rewritten(lesson):
    original = sys.modules["derivative_ch04_chain"]
    for name in ("opening", "two_stages", "rule", "linear_inner", "handoff", "semantic"):
        assert getattr(lesson.DerivativeChainLessonV003, name) is getattr(original.DerivativeChainLesson, name)
    for item in read("baseline-lock.json")["protected_inputs"]:
        if item["path"].startswith("examples/"):
            assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]


def test_actual_v001_contract_has_every_process_before_during_after():
    contract = read("contract.json")
    validate_contract(contract)
    asset = contract["assets"]["visual_v001"]
    assert asset["duration"] == 336
    assert asset["sha256"] == "e62de08fa4fa6c9b1af8933c57cdf2419a469b774e6a3a817012bd1aba74bcec"
    assert "/visual-v001/" in asset["path"]
    assert len(contract["units"]) == 8
    units = {unit["id"]: unit for unit in contract["units"]}
    features = {f["id"]: f for unit in contract["units"] for f in unit["features"]}
    assert features["extract_inner"]["baseline_samples"][0]["time"] < 29.03
    assert "preceding opening cue" in features["extract_inner"]["baseline_samples"][0]["source"]
    assert units["two-stages"]["baseline_interval"][0] == 22.368
    assert features["base_values"]["baseline_samples"][0]["time"] < 44.16
    assert features["three_ratios_converge"]["baseline_samples"][0]["time"] < 139.76
    for unit in contract["units"]:
        for feature in unit["features"]:
            samples = feature["baseline_samples"]
            lo, hi = feature["baseline_interval"]
            assert unit["baseline_interval"][0] <= lo < hi <= unit["baseline_interval"][1]
            assert all(lo <= r["time"] <= hi for r in samples)
            assert all(len(r["frame_sha256"]) == 64 for r in samples)
            if feature["kind"] == "process":
                assert [r["phase"] for r in samples] == ["before", "during", "after"]
                assert samples[0]["time"] < samples[1]["time"] < samples[2]["time"]


def test_transport_narration_identity_and_no_approval_claims():
    assert transport_segments(read("narration.json")) == read("transport.json")["segments"]
    draft_bytes = (FIXTURES / "narration.json").read_bytes()
    plan = read("plan.json")
    assert hashlib.sha256(draft_bytes).hexdigest() == plan["narration_draft_sha256"]
    assert plan["narration_draft"].endswith("narration-draft-v002.json")
    assert plan["author_agent"] == plan["author_context"] == AUTHOR
    assert plan["contributors"][0]["author_agent"] == "01a199e9-73ab-7700-8a9f-cd7b5541b0ad"
    assert plan["revision_mode"] == "revision"
    assert plan["revision_review"].endswith("regression-v003.json")
    assert plan["status"] == read("contract.json")["status"] == "not_reviewed"
    assert read("timings.json")["fixture_only"] is True
    assert not plan["production_boundary"]["rendered"]
    assert not plan["production_boundary"]["published"]
    for key in ("writer", "consumers", "lifecycle", "invalidation"):
        assert plan[key] and read("contract.json")[key]


def test_original_short_opening_is_a_real_full_wav_negative_control():
    plan = read("plan.json")
    plan["cues"][0]["duration"] = 24
    for cue in plan["cues"][1:]:
        cue["duration"] = 80
    plan["duration"] = sum(c["duration"] for c in plan["cues"])
    focuses = {"duration": plan["duration"], "windows": [
        {"id": f["id"], "start": 3.6 if f["id"] == "chain_opening" else .1, "end": 24 if f["id"] == "chain_opening" else plan["duration"]}
        for f in plan["focus_intents"]]}
    with pytest.raises(ValueError, match="chain-u01: no intersection"):
        schedule(visual_timeline(plan), read("narration.json"), focuses, read("timings.json"))


def test_missing_native_endpoint_never_falls_back_to_old_proportions(lesson):
    plan = read("plan.json")
    del plan["cues"][0]["stage_times"]["0.15"]
    scene = object.__new__(lesson.DerivativeChainLessonV003)
    scene._cue = plan["cues"][0]
    with pytest.raises(KeyError, match="0.15"):
        scene.beat(.15)


def test_no_production_or_audio_runtime_actions_in_candidate():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"sound", "render", "publish", "add_sound", "align_plan"}
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name and ("speech" in name or "phrase_alignment" in name) for name in imports)
