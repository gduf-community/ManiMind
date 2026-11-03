"""Preparatory process windows: actual native clock, never measured audio."""

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_intro_refined import narration, plan
from test_derivative_intro_visual import forbid_production_project_reads


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/derivative_intro_audio_aligned.py"


def delivery_narration():
    value = narration()
    edits = {
        ("approaching", "setup"): "现在让P留在原处，用h记录Q相对P的横坐标增量。",
        ("algebra_reason", "factor"): "提取公因式h，分子就成了h乘以括号里的四加h。",
    }
    for unit in value["units"]:
        for ref in unit["references"]:
            ref["text"] = edits.get((unit["id"], ref["id"]), ref["text"])
        unit["text"] = "".join(ref["text"] for ref in unit["references"])
    return value


@pytest.fixture(scope="module")
def lesson():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        return load_lesson(SOURCE)


@contextmanager
def run(lesson, *, baseline=False, real_tex=False, value=None):
    import derivative_intro_refined as refined
    import manimind.components.formula_motion as motion
    real_formula = refined.SemanticFormula
    scene_class = lesson.DerivativeIntroDeliveryLesson if baseline else lesson.DerivativeIntroAudioAlignedLesson
    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            if real_tex:
                refined.SemanticFormula = real_formula
                motion.SemanticFormula = real_formula
            patcher.setattr(refined.base, "SemanticFormula", refined.SemanticFormula)

        with native_run(refined, scene_class, plan() if value is None else value, initialize=initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def native(lesson):
    with run(lesson) as scene:
        return scene


@pytest.fixture
def state_scene(lesson):
    scene = lesson.DerivativeIntroAudioAlignedLesson.__new__(lesson.DerivativeIntroAudioAlignedLesson)
    scene.clock = 0.
    scene.get_time = lambda: scene.clock
    scene._open_focus, scene._closed_focus = {}, []
    scene._cue = {"id": "algebra"}
    scene.visual_events, scene.motion_samples, scene.symbol_transitions, scene.mobjects = [], [], [], []
    scene._initialize_formula_windows()
    return scene


def test_inherits_frozen_delivery_without_visual_or_stage_time_overrides(lesson):
    cls = lesson.DerivativeIntroAudioAlignedLesson
    assert cls.__bases__ == (lesson.DerivativeIntroDeliveryLesson,)
    for name in ("opening", "average", "approach", "algebra", "both_sides", "definition",
                 "tangent_prediction", "closing", "stage_time", "beat", "until", "play", "wait"):
        assert getattr(cls, name) is getattr(lesson.DerivativeIntroDeliveryLesson, name)


def test_exact_reference_ids_and_text_are_validated_without_rewriting(lesson):
    value = delivery_narration()
    original = deepcopy(value)
    assert lesson.validate_reference_bindings(value) == lesson.FORMULA_REFERENTS
    assert value == original
    for intent in lesson.FORMULA_REFERENTS:
        changed = deepcopy(value)
        unit = next(row for row in changed["units"] if row["id"] == intent.unit)
        ref = next(row for row in unit["references"] if row["id"] == intent.reference)
        ref["text"] += "改"
        unit["text"] = "".join(row["text"] for row in unit["references"])
        with pytest.raises(ValueError, match="meaning changed"):
            lesson.validate_reference_bindings(changed)


def test_static_result_wording_does_not_gain_a_process_window(lesson, native):
    states = {row.focus for row in lesson.FORMULA_REFERENTS if row.mode == "state"}
    assert states == {"expanded_terms", "simplified_rate"}
    windows = {row["id"]: row for row in native._closed_focus}
    marks = {row["id"]: row["time"] for row in native.visual_events}
    for intent in lesson.FORMULA_REFERENTS:
        if intent.mode == "state":
            assert windows[intent.focus]["start"] == marks[intent.ready]


def test_process_windows_begin_at_real_action_and_ready_stays_after_completion(lesson, native):
    events = native._formula_window_events
    windows = {row["id"]: row for row in native._closed_focus}
    marks = {row["id"]: row["time"] for row in native.visual_events}
    transitions = {row["stage"]: row for row in native.symbol_transitions}
    for intent in lesson.FORMULA_REFERENTS:
        rows = {row["phase"]: row for row in events if row["focus"] == intent.focus}
        assert rows["action_started"]["time"] == transitions[intent.stage]["start"]
        assert rows["action_completed"]["time"] == transitions[intent.stage]["end"]
        assert rows["ready_marked"]["time"] == marks[intent.ready]
        assert rows["action_started"]["time"] < rows["action_completed"]["time"] <= marks[intent.ready]
        assert rows["focus_closed"]["time"] == windows[intent.focus]["end"]
        if intent.mode == "process_result":
            assert windows[intent.focus]["start"] == rows["action_started"]["time"]
            assert rows["process_focus_opened"]["time"] == windows[intent.focus]["start"]
            assert rows["result_available"]["time"] == marks[intent.ready]
    assert sum(row["phase"] == "process_focus_opened" for row in events) == 3


def test_condition_relocation_is_not_backdated_as_formula_action(native):
    rows = [row for row in native._formula_window_events if row["stage"] == "simplified"]
    times = {row["phase"]: row["time"] for row in rows}
    assert times["transition_requested"] < times["condition_relocated"] == times["action_started"]
    assert times["condition_relocated"] - times["transition_requested"] == pytest.approx(.6)


def test_visual_clock_marks_geometry_and_unmanaged_focus_are_unchanged(lesson, native):
    with run(lesson, baseline=True) as baseline:
        assert native.time == baseline.time == 338
        assert native.frame == baseline.frame == 10140
        assert native.visual_events == baseline.visual_events
        assert native.motion_samples == baseline.motion_samples
        assert native.symbol_transitions == baseline.symbol_transitions
        changed = {row.focus for row in lesson.FORMULA_REFERENTS if row.mode == "process_result"}
        windows = {row["id"]: row for row in native._closed_focus}
        for old in baseline._closed_focus:
            current = windows[old["id"]]
            assert current["end"] == old["end"]
            if old["id"] in changed:
                assert current["start"] < old["start"]
            else:
                assert current == old


def test_schema3_and_lifecycle_report_do_not_claim_audio_alignment(lesson, native):
    from manimind.review.meaning_units import validate_narration
    focus = json.loads(native.out.files["focus-events.json"])
    draft = delivery_narration()
    validate_narration(draft, native.timeline, focus)
    report = json.loads(native.out.files["formula-focus-events.json"])
    assert report["status"] == "preparatory_not_audio_aligned"
    assert report["audio_measurements"] == "not_provided"
    assert report["audio_schedule"] == "not_created"
    assert report["events"] == native._formula_window_events
    assert all(left["time"] <= right["time"] for left, right in zip(report["events"], report["events"][1:]))
    assert report["references"] == [row._asdict() for row in lesson.FORMULA_REFERENTS]
    assert all(report[key] for key in ("writer", "consumers", "lifecycle", "invalidation", "limitation"))
    for row in report["state_contracts"]:
        assert all(row[key] for key in ("writer", "consumers", "lifecycle", "invalidation"))
    assert len(focus["windows"]) == len(plan()["focus_intents"]) == 28
    assert all(row["status"] == "closed" for row in native._formula_window_states.values())


def test_local_future_hold_override_preserves_native_formula_start_records(lesson, native):
    value = deepcopy(plan())
    cue = next(row for row in value["cues"] if row["id"] == "algebra")
    cue["duration"] += 2
    cue["stage_times"] = {"0.36": 28.64, "0.42": 33.08, "0.51": 39.74,
                          "0.58": 44.92, "0.68": 52.32, "0.73": 56.02, "0.83": 63.42, "0.89": 67.86}
    with run(lesson, value=value) as adjusted:
        assert adjusted.time == 340
        original = next(row for row in native._formula_window_events
                        if row["stage"] == "combined" and row["phase"] == "action_started")
        changed = next(row for row in adjusted._formula_window_events
                       if row["stage"] == "combined" and row["phase"] == "action_started")
        assert changed["time"] - original["time"] == pytest.approx(2)
        assert not adjusted._open_focus


def test_missing_or_unfulfilled_intents_cannot_finish(state_scene):
    with pytest.raises(ValueError, match="fulfilled and closed"):
        state_scene._finish_formula_windows()
    with pytest.raises(ValueError, match="one construct"):
        state_scene._initialize_formula_windows()
    with pytest.raises(ValueError, match="completed, ready"):
        state_scene.focus_begin("combined_terms")


def test_ready_before_action_completion_and_premature_close_are_rejected(state_scene):
    state = state_scene._formula_window_states["combined_terms"]
    state_scene._start_formula_action(state)
    with pytest.raises(ValueError, match="completed formula"):
        state_scene.mark("combined_ready")
    with pytest.raises(ValueError, match="unfulfilled"):
        state_scene.focus_end("combined_terms")
    with pytest.raises(ValueError, match="exactly once"):
        state_scene._start_formula_action(state)
    assert not state_scene.visual_events


def test_duplicate_result_handoff_ready_and_close_are_rejected(state_scene):
    state = state_scene._formula_window_states["combined_terms"]
    state_scene._start_formula_action(state)
    state_scene.clock = 1
    state["status"] = "completed"
    state_scene.mark("combined_ready")
    state_scene.focus_begin("combined_terms")
    with pytest.raises(ValueError, match="one completed"):
        state_scene.focus_begin("combined_terms")
    with pytest.raises(ValueError, match="exactly once"):
        state_scene.mark("combined_ready")
    state_scene.clock = 2
    state_scene.focus_end("combined_terms")
    with pytest.raises(ValueError, match="unfulfilled"):
        state_scene.focus_end("combined_terms")


def test_fake_parent_without_real_staged_samples_cannot_fulfill_intent(lesson, state_scene, monkeypatch):
    source = SimpleNamespace(get_family=lambda: [source], get_tex=lambda: "source")
    target = SimpleNamespace(get_family=lambda: [target], get_tex=lambda: "target")
    state_scene.mobjects = [source]

    def no_transition(scene, left, right, end, stage):
        scene.clock += 1
        return right

    monkeypatch.setattr(lesson.DerivativeIntroDeliveryLesson, "readable_matching", no_transition)
    with pytest.raises(ValueError, match="not fulfilled"):
        state_scene.readable_matching(source, target, .42, "combined")
    with pytest.raises(ValueError, match="fulfilled and closed"):
        state_scene._finish_formula_windows()
    assert not any(row["phase"] == "action_completed" for row in state_scene._formula_window_events)


def test_wrong_cue_unknown_stage_and_missing_source_are_rejected(state_scene):
    source = SimpleNamespace(get_family=lambda: [source])
    target = SimpleNamespace()
    with pytest.raises(ValueError, match="actual visible source"):
        state_scene.readable_matching(source, target, .42, "combined")
    state_scene.mobjects = [source]
    state_scene._cue = {"id": "opening"}
    with pytest.raises(ValueError, match="outside"):
        state_scene.readable_matching(source, target, .42, "combined")
    with pytest.raises(ValueError, match="Unexpected"):
        state_scene.readable_matching(source, target, .42, "unknown")


def test_real_tex_process_records_follow_the_native_animation(lesson, monkeypatch):
    from manimind.render.manim_renderer import _render_environment
    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    with run(lesson, real_tex=True) as scene:
        assert scene.time == 338
        assert len(scene._closed_focus) == 28
        for row in scene._formula_window_states.values():
            assert row["status"] == "closed"
            assert row["samples"]["tokens"] > 0 and row["samples"]["syntax"] > 0
        transitions = {row["stage"]: row for row in scene.symbol_transitions}
        for event in scene._formula_window_events:
            if event["phase"] == "action_started":
                assert event["time"] == transitions[event["stage"]]["start"]
