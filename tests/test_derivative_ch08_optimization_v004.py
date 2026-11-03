"""Closing binding repair with native placeholders, never pixel approval.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main/CI.
Lifecycle: this v004 fixture/source; bound input or native API invalidates.
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
FIXTURES = ROOT / "tests/fixtures/derivative-ch08-optimization-v004"
SOURCE = ROOT / "examples/derivative_ch08_optimization_v004.py"


def read(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        if any(path.resolve().is_relative_to(ROOT / name) for name in ("runtime", "outputs")):
            raise AssertionError("Tests consume frozen fixtures, not live production/review state")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    class Probe(lesson.DerivativeCh08OptimizationV004):
        def label(self, text, *args, **kwargs):
            result = super().label(text, *args, **kwargs)
            result.lesson_text = text
            return result

        def mark(self, identity):
            super().mark(identity)
            nodes = [node for mob in self.mobjects for node in mob.get_family()
                if (hasattr(node, "get_tex") or hasattr(node, "lesson_text")) and float(node.get_opacity()) > .9]
            self.formulas[identity] = {node.get_tex() for node in nodes if hasattr(node, "get_tex")}
            self.label_states[identity] = {node.lesson_text for node in nodes if hasattr(node, "lesson_text")}

    def initialize(scene):
        scene.formulas, scene.label_states = {}, {}

    with native_run(lesson, Probe, read("plan.json"), initialize) as scene:
        yield scene


@pytest.fixture(scope="module")
def placement(native):
    return schedule(visual_timeline(read("plan.json")), read("narration.json"),
                    {"duration": native.time, "windows": native._closed_focus}, read("timings.json"))


def local_mark(native, placement, identity):
    start = next(p["start"] for p in placement if p["cue"] == "closing")
    return next(e["time"] for e in native.visual_events if e["id"] == identity)-start


def test_full_construct_preserves_clock_and_places_all_original_wavs(native, placement):
    assert native.time == pytest.approx(381.366666667, abs=1e-8)
    assert len(placement) == 8 and sum(len(p["references"]) for p in placement) == 22
    assert sum(p["duration_seconds"] for p in placement) == pytest.approx(358.88)
    assert not native._open_focus
    previous = 0
    for row, timing, intended in zip(placement, read("timings.json")["units"], read("plan.json")["intended_full_wav_placement"], strict=True):
        assert row["start"] >= previous
        assert row["end"]-row["start"] == pytest.approx(timing["duration_seconds"])
        assert abs(row["start"]-intended["intended_start"]) < .04
        assert intended["wav_sha256"] == timing["wav_sha256"]
        assert not intended["audio_trimmed"] and not intended["speed_changed"] and not intended["regenerated"]
        assert all(p["focus_start"] <= p["visual_start"]+1e-8 and p["visual_end"] <= p["focus_end"]+1e-8 for p in row["phrases"])
        previous = row["end"]


def test_only_closing_is_overridden_and_all_cue_durations_are_identical(lesson):
    old = sys.modules["derivative_ch08_optimization_v003"].DerivativeCh08OptimizationV003
    for name in ("construct", "opening", "cut", "fold", "objective", "optimize", "boundary", "constraint", "panels", "net", "beat"):
        assert getattr(lesson.DerivativeCh08OptimizationV004, name) is getattr(old, name)
    plan, previous = read("plan.json"), read("previous-plan.json")
    assert plan["duration"] == previous["duration"]
    assert plan["intended_full_wav_placement"] == previous["intended_full_wav_placement"]
    for cue, prior in zip(plan["cues"], previous["cues"], strict=True):
        assert cue["duration"] == prior["duration"]
        if cue["id"] != "closing":
            assert cue == prior


def test_original_answer_has_explicit_original_condition_before_new_requirements(native):
    assert "原条件：无额外高度下限" in native.label_states["chapter_chain_ready"]
    assert r"x=2\ \mathrm{cm},\quad V=128\ \mathrm{cm}^3" in native.formulas["chapter_chain_ready"]
    assert r"8\times8\times2\ \mathrm{cm}" in native.formulas["chapter_chain_ready"]
    assert not any("108" in tex for tex in native.formulas["chapter_chain_ready"])
    assert "原条件：无额外高度下限" in native.label_states["feasibility_transfer_ready"]


def test_height_clause_already_has_new_domain_and_explicit_old_solution_rejection(native, placement):
    mark = "closing_old_solution_excluded"
    assert 27.4 < local_mark(native, placement, mark) < 27.7
    labels = native.label_states[mark]
    assert "当前条件：盒高至少 3 cm" in labels
    assert "旧解 x = 2：高度不足，排除" in labels
    assert "原条件：无额外高度下限" not in labels
    formulas = native.formulas[mark]
    assert r"3\leq x<6\quad(\mathrm{cm})" in formulas
    assert not any("128" in tex or r"8\times8\times2" in tex for tex in formulas)


def test_current_box_and_its_answer_are_ready_before_boundary_three_words(native, placement):
    assert 30.6 < local_mark(native, placement, "closing_current_box_ready") < 31.08
    assert 30.9 < local_mark(native, placement, "closing_current_optimum_ready") < 31.08
    formulas = native.formulas["closing_current_optimum_ready"]
    assert {r"x=3\ \mathrm{cm},\quad V=108\ \mathrm{cm}^3", r"6\times6\times3\ \mathrm{cm}",
            r"3\leq x<6\quad(\mathrm{cm})"} <= formulas
    assert not any("128" in tex or r"8\times8\times2" in tex for tex in formulas)
    assert "当前条件：盒高至少 3 cm" in native.label_states["closing_current_optimum_ready"]
    assert "旧解 x = 2：高度不足，排除" in native.label_states["closing_current_optimum_ready"]


@pytest.mark.parametrize("time", [29.6, 30.2, 30.6, 31.2, 32.32, 36.5, 39.2])
def test_actual_box_tracker_and_feasibility_match_new_condition_during_relevant_words(native, placement, time):
    audio = next(p["start"] for p in placement if p["cue"] == "closing")
    rows = [r for r in native.motion_samples if r["kind"] == "closing_binding" and r["min_height_cm"] == 3]
    row = min(rows, key=lambda r: abs(r["time"]-audio-time))
    assert abs(row["time"]-audio-time) <= 1/30+.001
    x = row["x_cm"]
    if time < 30.4:
        assert x == 2 and not row["feasible"]
    elif time < 30.8:
        assert 2 < x < 3 and not row["feasible"]
    else:
        assert x == pytest.approx(3) and row["feasible"]
        assert row["volume_cm3"] == pytest.approx(108)
    assert row["dimensions_cm"] == pytest.approx([12-2*x, 12-2*x, x])
    assert row["volume_cm3"] == pytest.approx(x*(12-2*x)**2)


def test_model_chain_and_transfer_remain_when_current_answer_changes(native):
    labels = native.label_states["closing_current_optimum_ready"]
    assert {"尺寸 → 同一变量 → 目标与可行域", "变化率 → 单调性 → 全范围比较", "约束改变，沿同一模型重新判断"} <= labels


def test_narration_v004_only_changes_metadata_not_any_original_unit_or_transport():
    plan, narration = read("plan.json"), read("narration.json")
    assert narration["units"] == read("original-narration.json")["units"]
    assert transport_segments(narration) == read("transport.json")["segments"]
    assert hashlib.sha256((FIXTURES / "narration.json").read_bytes()).hexdigest() == plan["narration_draft_sha256"]
    assert plan["narration_draft"].endswith("narration-draft-v004.json")
    assert plan["original_narration_draft"].endswith("narration-draft-v002.json")
    assert narration["original_draft_sha256"] == plan["original_narration_draft_sha256"]
    assert narration["av_revision"]["units_and_transport_unchanged"]
    assert not narration["av_revision"]["speech_plan_regenerated"]
    assert read("timings.json")["production_input_sha256"] == "34a6e44f5ceba10d031bb98fcedcabede14d90fa2c90f4bfb8bc832642c8aee8"


def test_actual_current_v003_contract_keeps_27_functions_and_11_process_triplets():
    contract = read("contract.json")
    validate_contract(contract)
    assert list(contract["assets"]) == ["visual_v003"]
    asset = contract["assets"]["visual_v003"]
    assert "/visual-v003/" in asset["path"] and asset["duration"] == pytest.approx(381.366666667)
    assert asset["sha256"] == "fdc2581360151e401c44605bf56a001117888acfabf97c4135018267ebed101a"
    features = [f for u in contract["units"] for f in u["features"]]
    assert len(features) == 27
    assert {"root_screening", "net_projection", "product_chain_derivative", "hinged_folding", "original_answer_restored", "chapter_model_chain"} <= {f["id"] for f in features}
    processes = [f for f in features if f["kind"] == "process"]
    assert len(processes) == 11
    for feature in processes:
        assert [s["phase"] for s in feature["baseline_samples"]] == ["before", "during", "after"]
        times = [s["time"] for s in feature["baseline_samples"]]
        assert times[0] < times[1] < times[2]
    assert contract["repair_issue"]["id"] == "av08-closing-constraint-object-mismatch"


def test_old_closing_negative_control_still_exposes_the_reported_binding_gap(lesson):
    old = sys.modules["derivative_ch08_optimization_v003"]
    with native_run(old, old.DerivativeCh08OptimizationV003, read("previous-plan.json")) as scene:
        assert "旧解 x = 2：高度不足，排除" not in scene.labels
        final = {node.get_tex() for mob in scene.mobjects for node in mob.get_family() if hasattr(node, "get_tex")}
        assert r"x=2\ \mathrm{cm},\quad V=128\ \mathrm{cm}^3" in final
        assert not any("108" in tex for tex in final)


def test_real_author_contributors_boundary_and_old_source_hashes():
    plan = read("plan.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19acd-e149-74d0-8a5d-975a3adf45f4"
    assert plan["contributors"][:2] == read("previous-plan.json")["contributors"][:2]
    assert plan["revision_mode"] == "revision" and plan["version"] == "v004"
    assert "ch08-av-revision/feedback-baseline-study" in plan["baseline_study"]
    assert plan["status"] == read("narration.json")["status"] == read("contract.json")["status"] == "not_reviewed"
    assert not plan["production_boundary"]["rendered"] and not plan["production_boundary"]["published"]
    assert len(read("baseline-lock.json")["external_no_write_guards"]) == 83
    for row in read("baseline-lock.json")["protected_inputs"]:
        if row["path"].startswith(("examples/", "src/")):
            assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_candidate_has_no_production_actions_and_explicit_state_lifetimes():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"render", "add_sound", "publish", "align_plan", "urlopen"}
    for data in (read("plan.json"), read("contract.json"), read("narration.json"), read("baseline-lock.json")):
        assert all(data[k] for k in ("writer", "consumers", "lifecycle", "invalidation"))
