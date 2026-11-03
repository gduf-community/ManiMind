"""Fixture-only additive revision tests, not a pixel or content approval."""

import ast
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib
import json
from pathlib import Path
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_ch05_monotonicity_v002.py"
BASE = ROOT / "examples/derivative_ch05_monotonicity.py"
FIXTURE = ROOT / "tests/fixtures/derivative-ch05-monotonicity"


def read(name, revised=True):
    return json.loads((FIXTURE / "v002" / name if revised else FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def model():
    old = ast.parse(BASE.read_text(encoding="utf-8"))
    new = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [n for n in old.body if isinstance(n, ast.Import) and any(a.name == "math" for a in n.names)
             or isinstance(n, ast.ImportFrom) and n.module == "numbers"
             or isinstance(n, ast.FunctionDef) and n.name == "finite_real"]
    nodes += [n for n in new.body if isinstance(n, ast.FunctionDef)]
    module = types.ModuleType("reciprocal_revision_pure_v002")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), module.__dict__)
    return module


def test_versioned_exact_inputs_outputs_and_positive_derivatives(model):
    for row in read("mathematics.json")["samples"]:
        x = Fraction(row["x"])
        assert model.reciprocal(x) == Fraction(row["q"])
        assert model.reciprocal_derivative(x) == Fraction(row["dq"]) > 0


@pytest.mark.parametrize("a,b", [(Fraction(-4), Fraction(-1)), (Fraction(-1), Fraction(-1, 10)),
                               (Fraction(1, 10), Fraction(1)), (Fraction(1), Fraction(4))])
def test_same_branch_order_is_exact_not_just_an_animation_sample(model, a, b):
    assert model.reciprocal(b)-model.reciprocal(a) == (b-a)/(a*b) > 0


def test_cross_gap_pair_reverses_outputs_despite_positive_derivatives(model):
    row = read("mathematics.json")["cross_pair"]
    pair = model.disconnected_pair(Fraction(row["a"]), Fraction(row["b"]))
    for name in ("a", "b", "qa", "qb", "output_difference"):
        assert pair[name] == Fraction(row[name])
    assert pair["a"] < 0 < pair["b"]
    assert pair["derivative_a"] > 0 and pair["derivative_b"] > 0
    assert pair["output_difference"] < 0
    assert pair["whole_interval_defined"] is False


@pytest.mark.parametrize("x", [0, -0.0, Fraction(0)])
def test_zero_is_excluded_from_value_derivative_and_geometry(model, x):
    for fn in (model.reciprocal, model.reciprocal_derivative, model.reciprocal_point):
        with pytest.raises(ValueError, match="x != 0"):
            fn(x)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_inputs_are_rejected(model, bad):
    with pytest.raises(ValueError, match="finite"):
        model.reciprocal(bad)


@pytest.mark.parametrize("bad", [True, "1", None, 1j])
def test_nonreal_inputs_are_rejected(model, bad):
    with pytest.raises(TypeError, match="real"):
        model.reciprocal(bad)


@pytest.mark.parametrize("a,b", [(-2, -1), (1, 2), (0, 1), (-1, 0), (1, -1)])
def test_cross_gap_comparison_requires_two_valid_opposite_sides(model, a, b):
    with pytest.raises(ValueError, match="a < 0 < b"):
        model.disconnected_pair(a, b)


def test_frozen_baseline_scene_and_shared_are_byte_unchanged():
    fixture = read("mathematics.json")
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == fixture["baseline_source_sha256"]
    assert hashlib.sha256((ROOT / "examples/derivative_chapter_shared.py").read_bytes()).hexdigest() == fixture["shared_sha256"]


def test_schema3_keeps_seven_existing_meaning_units_and_adds_one():
    plan, narration = read("plan.json"), read("narration.json")
    previous = read("narration-v001.json", revised=False)
    assert [u for u in narration["units"] if u["cue"] != "disconnected-domain"] == previous["units"]
    assert len(narration["units"]) == len(previous["units"])+1
    assert narration["schema_version"] == 3
    focuses = {r["id"]: r["cue"] for r in plan["focus_intents"]}
    for unit in narration["units"]:
        assert set(unit) == {"id", "cue", "text", "references"}
        assert "".join(r["text"] for r in unit["references"]) == unit["text"]
        assert all(focuses[r["focus"]] == unit["cue"] for r in unit["references"])
    assert narration["audio_status"] == "not_generated"
    assert narration["alignment_status"] == "not_performed_no_acoustic_times"
    assert plan["revision_mode"] == "revision"
    for state in plan["state_contracts"]:
        assert all(state[k] for k in ("writer", "consumers", "lifecycle", "invalidation"))


def test_existing_cue_design_is_not_replaced_by_the_new_counterexample():
    current, previous = read("plan.json"), read("plan-v001.json", revised=False)
    assert [c for c in current["cues"] if c["id"] != "disconnected-domain"] == previous["cues"]
    assert current["duration"]-previous["duration"] == 72
    assert "sources" not in current and "lesson_context" not in current


def test_contract_uses_existing_real_gate_schema_and_covers_entire_baseline():
    from manimind.review.content_regression import revision_required, validate_contract
    contract = read("content-regression-contract.json")
    assert validate_contract(contract) is contract
    assert revision_required(read("plan.json"), profile_version="understanding-first-v3")
    assert list(contract["assets"]) == ["visual-v001"]
    assert contract["assets"]["visual-v001"]["duration"] == 324
    intervals = [unit["baseline_interval"] for unit in contract["units"]]
    assert intervals[0][0] == 0 and intervals[-1][1] == 324
    assert all(a[1] == b[0] for a, b in zip(intervals, intervals[1:]))
    assert {unit["id"] for unit in contract["units"]} == {
        "opening", "shared-input", "first-sign-turn", "second-sign-turn", "factor-sign-reasons",
        "secant-to-tangent", "interval-theorem", "isolated-zero", "closing-handoff"}
    assert sum(f["kind"] == "process" for u in contract["units"] for f in u["features"]) >= 9
    assert contract["revision_addition"]["author_comparison_status"] == "not_performed"
    invalid = deepcopy(contract)
    invalid["units"][0]["baseline_interval"] = [0, 325]
    with pytest.raises(ValueError, match="in-range"):
        validate_contract(invalid)


@pytest.fixture(scope="module")
def native():
    from lesson_native_harness import load_lesson, native_run
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        lesson = load_lesson(SOURCE)
        base = importlib.import_module("derivative_ch05_monotonicity")
        old_plan = read("plan-v001.json", revised=False)
        with native_run(base, base.DerivativeMonotonicityLesson, old_plan) as previous:
            pass
        def initialize(_):
            patcher.setattr(base, "SemanticFormula", lesson.SemanticFormula)
        with native_run(lesson, lesson.DerivativeMonotonicityLessonV002, read("plan.json"), initialize=initialize) as current:
            yield lesson, base, previous, current


def test_existing_methods_are_inherited_without_changes(native):
    lesson, base, _, _ = native
    for name in ("opening", "same_x", "plots", "sweep", "signs", "interval", "zero_point", "handoff"):
        assert getattr(lesson.DerivativeMonotonicityLessonV002, name) is getattr(base.DerivativeMonotonicityLesson, name)


def test_original_native_motion_journal_is_preserved_exactly(native):
    _, _, previous, current = native
    kinds = {"linked_graphs", "cube_motion"}
    assert [r for r in current.motion_samples if r["kind"] in kinds] == [r for r in previous.motion_samples if r["kind"] in kinds]
    assert previous.time == 324 and current.time == 396
    marks = {r["id"]: r["time"] for r in current.visual_events}
    for old in previous.visual_events:
        assert marks[old["id"]] == pytest.approx(old["time"]+(72 if old["time"] >= 294 else 0))
    windows = {r["id"]: r for r in current._closed_focus}
    for old in previous._closed_focus:
        delta = 72 if old["start"] >= 294 else 0
        assert windows[old["id"]]["start"] == pytest.approx(old["start"]+delta)
        assert windows[old["id"]]["end"] == pytest.approx(old["end"]+delta)


def test_new_actual_motion_never_crosses_or_evaluates_gap(native, model):
    _, _, _, current = native
    rows = [r for r in current.motion_samples if r["kind"] == "reciprocal_branch"]
    for phase, lo, hi in (("left", -2, -1), ("right", .5, 1)):
        samples = [r for r in rows if r["phase"] == phase]
        assert len(samples) > 250
        assert samples[0]["x"] == lo and samples[-1]["x"] == hi
        assert all(lo <= r["x"] <= hi and r["dq"] > 0 for r in samples)
        assert all(r["q"] == pytest.approx(model.reciprocal(r["x"])) for r in samples)
        assert all(r["point"] == pytest.approx(model.reciprocal_point(r["x"])) for r in samples)
        assert all(b["q"] >= a["q"] for a, b in zip(samples, samples[1:]))
        assert min(r["point"][1] for r in samples) > -3.1
    pair = next(r for r in current.motion_samples if r["kind"] == "disconnected_comparison")
    assert (pair["a"], pair["qa"], pair["b"], pair["qb"]) == (-1, 1, 1, -1)
    assert pair["whole_interval_defined"] is False


def test_all_focuses_and_events_are_measured_after_available_states(native):
    _, _, _, current = native
    plan = read("plan.json")
    assert not current._open_focus
    windows = {r["id"]: r for r in current._closed_focus}
    assert set(windows) == {r["id"] for r in plan["focus_intents"]}
    from manimind.review.semantic_focus import focus_windows
    focus_windows({"duration": current.time, "windows": current._closed_focus}, current.time)
    marks = {r["id"]: r["time"] for r in current.visual_events}
    for focus, event in (("disconnected_domain", "disconnected_branches_ready"),
                         ("branch_left_motion", "branch_left_start_ready"),
                         ("branch_right_motion", "branch_right_start_ready"),
                         ("cross_gap_comparison", "cross_gap_comparison_ready"),
                         ("gap_interval_condition", "gap_interval_condition_ready"),
                         ("separate_intervals", "separate_intervals_ready")):
        assert windows[focus]["start"] >= marks[event]
    assert marks["branch_left_complete"] < marks["branch_right_start_ready"]
    assert marks["branch_right_complete"] < marks["cross_gap_comparison_ready"]
    assert marks["cross_gap_comparison_ready"] < marks["gap_interval_condition_ready"]


def test_author_scene_has_no_render_audio_publication_or_review_actions():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"render", "sound", "add_sound", "publish", "require_review", "validate_comparison"}
