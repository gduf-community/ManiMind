"""Author native checks with vector placeholders; no GL/pixel approval."""

import ast
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from manimind.experiments.visual_first_data import visual_timeline
from manimind.review.content_regression import validate_contract
from manimind.review.meaning_units import schedule, validate_narration


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-ch02-traceable"
SOURCE = ROOT / "examples/derivative_ch02_traceable.py"


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        yield load_lesson(SOURCE)


@pytest.fixture(scope="module")
def native(lesson):
    import derivative_ch02_basics as original
    import derivative_chapter_shared as shared
    import manimind.components.formula_transfer as transfer

    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            scene.motion_samples = []
            patcher.setattr(original, "SemanticFormula", lesson.SemanticFormula)
            patcher.setattr(shared, "SemanticFormula", lesson.SemanticFormula)
            patcher.setattr(transfer, "SemanticFormula", lesson.SemanticFormula)

        with native_run(lesson, lesson.DerivativeCh02Traceable, read("plan-draft.json"), initialize) as scene:
            yield scene


def test_complete_native_construct_retains_duration_focus_and_cue_exit(native):
    plan = read("plan-draft.json")
    assert native.time == pytest.approx(plan["duration"], abs=1e-7)
    assert not native._open_focus and not native._drivers
    assert {r["id"] for r in native._closed_focus} == {r["id"] for r in plan["focus_intents"]}


def test_every_selected_operation_really_executes_with_measured_duration(native):
    transitions = read("plan-draft.json")["formula_transitions"]
    complete = [s for s in native.motion_samples if s["kind"] == "traceable_complete"]
    assert {s["transition"] for s in complete} == {s["id"] for s in transitions}
    for row in transitions:
        samples = [s for s in native.motion_samples if s.get("transition") == row["id"] and s["kind"] != "traceable_complete"]
        assert len(samples) >= 30
        assert samples[-1]["time"] - samples[0]["time"] >= 1


def test_visible_origin_is_not_pretranslated_into_target_row(native):
    rows = [s for s in native.motion_samples if s.get("transition") == "square_expand" and s["kind"] == "traceable_formula"]
    start = rows[0]
    assert start["moving"]["square"][1] > start["target"]["square"][1] + .5
    assert rows[-1]["moving"]["square"][1] < start["moving"]["square"][1] - .5


def test_travel_preserves_source_shapes_before_operation_and_new_syntax(native):
    rows = [s for s in native.motion_samples if s["kind"] == "traceable_formula"]
    for identity in {r["transition"] for r in rows}:
        selected = [r for r in rows if r["transition"] == identity]
        phases = list(dict.fromkeys(r["phase"] for r in selected))
        assert phases.index("travel_unchanged") < phases.index("resolve_operation") < phases.index("new_syntax")
        source_counts = selected[0]["glyph_counts"]
        assert all(r["glyph_counts"] == source_counts for r in selected if r["phase"] == "travel_unchanged")
    gathered = [s for s in native.motion_samples if s["kind"] == "traceable_gather"]
    assert all(s["active_role"] is not None for s in gathered if s["phase"] == "travel_unchanged")
    assert {r["active_role"] for r in gathered if r["transition"] == "log_base_example"} >= {"input", "base"}


def test_all_original_full_meaning_units_still_fit_without_changing_words(native):
    plan = read("plan-draft.json")
    focus = {"duration": native.time, "windows": native._closed_focus}
    narration, timings = read("narration.json"), read("timings.json")
    validate_narration(narration, visual_timeline(plan), focus)
    placement = schedule(visual_timeline(plan), narration, focus, timings)
    assert len(placement) == 14
    assert sum(r["duration_seconds"] for r in placement) == pytest.approx(609.28)
    for actual, intended in zip(placement, plan["intended_full_wav_placement"], strict=True):
        assert abs(actual["start"] - intended["intended_start"]) <= .07


def test_original_graph_models_and_nonzero_conditions_are_not_removed(native):
    motions = [s for s in native.motion_samples if s["kind"] == "slope_map"]
    assert {s["function"] for s in motions} == {"square", "constant", "identity", "cube", "reciprocal", "root", "exp", "log", "sin", "cos"}
    reciprocal = [s["x"] for s in motions if s["function"] == "reciprocal"]
    assert any(x < 0 for x in reciprocal) and any(x > 0 for x in reciprocal)
    assert all(abs(x) >= .65 - 1e-8 for x in reciprocal)
    log = [s for s in native.motion_samples if s["kind"] == "log_increment_bridge"]
    assert min(s["dx"] for s in log) == pytest.approx(.08)
    assert max(s["dx"] for s in log) == pytest.approx(.8)


def test_current_selected_baseline_and_v431_gate_are_explicit():
    plan, contract = read("plan-draft.json"), read("contract-draft.json")
    validate_contract(contract)
    assert set(contract["assets"]) == {"selected_visual_v005"}
    assert sum(len(u["features"]) for u in contract["units"]) == 38
    assert contract["new_improvement_goals"] == plan["formula_transitions"]
    assert plan["workflow_profile"].endswith("v4.3.1-unit.json")
    assert plan["author_agent"] == plan["author_context"] == "01a19f5e-8733-71c0-ac2d-d507423acd13"
    for path in ["src/manimind/postproduce/traceable_film.py", "src/manimind/postproduce/traceable_film_v2.py",
                 "docs/formula-continuity.md", "docs/formula-continuity-v2.md", "src/manimind/components/formula_transfer.py"]:
        assert path in plan["sources"]
    assert plan["status"] == "author_draft_not_frozen_no_GL_slot"
    assert len(plan["review_times"]) > 300


def test_no_hidden_safe_formula_fallback_or_target_row_pretranslation():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    assert not any(isinstance(n, ast.Attribute) and n.attr == "safe_formula" for n in ast.walk(tree))
    assert not any(isinstance(n, ast.Attribute) and n.attr == "shift" for n in ast.walk(tree))
