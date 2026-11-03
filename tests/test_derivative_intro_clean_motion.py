"""v006-only native phase/lifecycle checks; no pixel or audio approval."""

from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_intro_visual import forbid_production_project_reads
from test_derivative_intro_voiced import placement_diagnostic, word_span


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-intro-clean-motion"
VOICE_FIXTURE = ROOT / "tests/fixtures/derivative-intro-voiced"
STAGES = ("expanded", "combined", "factored", "simplified", "general_position")
PHASES = ("complete_copy", "syntax_out", "tokens", "syntax")


def read(name):
    directory = FIXTURE if name in {"plan.json", "design.json"} else VOICE_FIXTURE
    return json.loads((directory / name).read_text(encoding="utf-8"))


def load():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        return load_lesson(ROOT / "examples/derivative_intro_clean_motion.py")


def opacity_range(obj):
    values = [float(g.get_opacity()) for g in obj.family_members_with_points()]
    return [min(values), max(values)] if values else [1., 1.]


@contextmanager
def run(lesson, real_tex=False):
    import derivative_intro_refined as refined
    import manimind.components.formula_motion as motion
    real_formula = refined.SemanticFormula
    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            if real_tex:
                refined.SemanticFormula = real_formula
                motion.SemanticFormula = real_formula
                patcher.setattr(scene, "formula", refined.base.DerivativeIntroLesson.formula.__get__(scene))
            patcher.setattr(refined.base, "SemanticFormula", refined.SemanticFormula)
            patcher.setattr(scene, "assemble_render_groups", lambda: None)
            actual_remove = lesson.DerivativeIntroCleanMotionLesson.remove.__get__(scene)
            actual_play = scene.play
            actual_parts, actual_record = scene.syntax_parts, scene._chain_record
            parts, contexts = [], {}
            scene.test_phase_witnesses, scene.test_removal_witnesses = [], []

            def syntax_parts(formula, common):
                result = actual_parts(formula, common)
                parts.append((formula, result, tuple(common)))
                return result

            def chain_record(phase, **details):
                actual_record(phase, **details)
                if phase == "before":
                    moving, old_syntax, common = parts[-2]
                    target, new_syntax, _ = parts[-1]
                    sources = [obj for obj in scene.mobjects if obj is not moving
                               and hasattr(obj, "get_tex") and obj.get_tex() == details["source"]
                               and refined.bounds(obj) == pytest.approx(details["source_bounds"])]
                    assert len(sources) == 1, "Actual complete source must be uniquely identifiable"
                    contexts[details["stage"]] = {
                        "source": sources[0], "moving": moving, "target": target,
                        "old_syntax": old_syntax, "new_syntax": new_syntax, "common": common,
                        "source_bounds": details["source_bounds"],
                        "wrappers": [],
                    }

            def play(*animations, **kwargs):
                focus = scene._active_formula_focus
                if focus is not None:
                    stage = scene._formula_window_states[focus]["intent"].stage
                    if stage in contexts:
                        contexts[stage]["wrappers"].extend(animation.mobject for animation in animations
                            if type(animation).__name__ == "Transform")
                return actual_play(*animations, **kwargs)

            def stage_glyphs():
                return {id(g) for obj in scene.mobjects for g in obj.family_members_with_points()}

            def remove(*objects):
                result = actual_remove(*objects)
                current = stage_glyphs()
                for stage, ctx in contexts.items():
                    if any(obj is ctx["moving"] for obj in objects):
                        moving_ids = {id(g) for obj in [ctx["moving"], *ctx["wrappers"]]
                                      for g in obj.family_members_with_points()}
                        scene.test_removal_witnesses.append({
                            "stage": stage, "time": float(scene.get_time()),
                            "copy_glyphs_remaining": len(moving_ids & current),
                            "source_present": all(id(g) in current for g in ctx["source"].family_members_with_points()),
                            "wrapper_count": len(ctx["wrappers"]), "common_count": len(ctx["common"]),
                            "explicit_wrapper_cleanup": all(any(wrapper is obj for obj in objects)
                                                            for wrapper in ctx["wrappers"]),
                        })
                return result

            class PhaseJournal(list):
                def append(self, row):
                    super().append(row)
                    ctx = contexts[row["stage"]]
                    current = stage_glyphs()
                    copy_ids = {id(g) for obj in [ctx["moving"], *ctx["wrappers"]]
                                for g in obj.family_members_with_points()}
                    target_ids = {id(g) for g in ctx["target"].family_members_with_points()}
                    source_ids = {id(g) for g in ctx["source"].family_members_with_points()}
                    scene.test_phase_witnesses.append({
                        "stage": row["stage"], "phase": row["phase"], "time": float(scene.get_time()),
                        "source_bounds": refined.bounds(ctx["source"]),
                        "source_opacity": opacity_range(ctx["source"]),
                        "source_present": bool(source_ids) and source_ids <= current,
                        "copy_present": bool(copy_ids & current),
                        "target_present": bool(target_ids) and target_ids <= current,
                        "old_syntax_opacity": opacity_range(ctx["old_syntax"]),
                        "target_syntax_opacity": opacity_range(ctx["new_syntax"]),
                        "common_bounds": {key: refined.bounds(ctx["moving"].tag(key)) for key in ctx["common"]},
                        "target_common_bounds": {key: refined.bounds(ctx["target"].tag(key)) for key in ctx["common"]},
                        "copy_bounds": refined.bounds(ctx["moving"]),
                        "target_bounds": refined.bounds(ctx["target"]),
                    })

            original_initialize = scene._initialize_formula_windows

            def initialize_windows():
                original_initialize()
                scene._clean_motion_events = PhaseJournal()

            patcher.setattr(scene, "_initialize_formula_windows", initialize_windows)
            patcher.setattr(scene, "syntax_parts", syntax_parts)
            patcher.setattr(scene, "_chain_record", chain_record)
            patcher.setattr(scene, "remove", remove)
            patcher.setattr(scene, "play", play)
        with native_run(refined, lesson.DerivativeIntroCleanMotionLesson, read("plan.json"),
                        initialize=initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def lesson():
    return load()


@pytest.fixture(scope="module")
def native(lesson):
    with run(lesson) as scene:
        return scene


def phases(scene, stage):
    return [row for row in scene._clean_motion_events if row["stage"] == stage]


def test_native_full_original_wavs_have_one_global_placement(native):
    result = placement_diagnostic(native, read("narration.json"), read("measured-timings.json"))
    assert result["globally_feasible"], result
    assert len(result["full_placement"]) == 9
    assert all(row["individually_feasible"] for row in result["units"])
    assert sum(row["duration_seconds"] for row in result["full_placement"]) == pytest.approx(184.64)
    assert sum(len(row["phrases"]) for row in result["full_placement"]) == 28
    end = 0
    for row in result["full_placement"]:
        assert row["start"] >= end
        for phrase in row["phrases"]:
            assert phrase["focus_start"] - 1e-10 <= phrase["visual_start"] <= phrase["visual_end"] <= phrase["focus_end"] + 1e-10
        end = row["end"]


def test_four_phases_are_ordered_nonconcurrent_and_syntax_waits_for_motion(native):
    for stage in STAGES:
        rows = phases(native, stage)
        sequence = [row["phase"] for i, row in enumerate(rows) if i == 0 or row["phase"] != rows[i-1]["phase"]]
        assert tuple(sequence) == PHASES
        assert all(a["time"] <= b["time"] for a, b in zip(rows, rows[1:]))
        assert all(row["target_syntax_opacity"] == pytest.approx(0)
                   for row in rows if row["phase"] != "syntax")
        syntax = [row["target_syntax_opacity"] for row in rows if row["phase"] == "syntax"]
        assert syntax[-1] == pytest.approx(1)
        assert all(a <= b + 1e-10 for a, b in zip(syntax, syntax[1:]))
        before = [row for row in rows if row["phase"] == "complete_copy"]
        assert before[-1]["copy_minimum_opacity"] == pytest.approx(1)


def test_actual_objects_match_phase_names_and_source_stays_complete(native):
    assert len(native.test_phase_witnesses) == len(native._clean_motion_events)
    for row in native.test_phase_witnesses:
        before = next(x for x in native._chain_events if x.get("stage") == row["stage"] and x["phase"] == "before")
        assert row["source_present"] and row["source_opacity"] == pytest.approx([1, 1])
        assert row["source_bounds"] == pytest.approx(before["source_bounds"])
        if row["phase"] in {"complete_copy", "syntax_out", "tokens"}:
            assert row["copy_present"] and not row["target_present"]
        if row["phase"] == "complete_copy":
            assert row["copy_bounds"][0] == pytest.approx(row["target_bounds"][0])
        if row["phase"] == "tokens":
            assert row["old_syntax_opacity"] == pytest.approx([0, 0])
            assert row["target_syntax_opacity"] == pytest.approx([0, 0])
        if row["phase"] == "syntax":
            assert not row["copy_present"] and row["target_present"]
    assert len(native.test_removal_witnesses) == 5
    assert all(row["copy_glyphs_remaining"] == 0 and row["source_present"]
               and row["wrapper_count"] == row["common_count"] and row["explicit_wrapper_cleanup"]
               for row in native.test_removal_witnesses)


def test_completed_semantic_tokens_reach_the_actual_target_before_syntax(native):
    for stage in STAGES:
        rows = [row for row in native.test_phase_witnesses if row["stage"] == stage and row["phase"] == "tokens"]
        assert rows
        final = rows[-1]
        assert final["common_bounds"]
        for key, box in final["common_bounds"].items():
            assert box == pytest.approx(final["target_common_bounds"][key], abs=1e-6)
        after = next(row for row in native._chain_events if row.get("stage") == stage and row["phase"] == "after")
        assert after["minimum_opacity"] >= .999
        assert after["target_bounds"][3] < after["source_bounds"][2]


def test_original_formula_rows_close_only_at_actual_removal(native):
    assert native.time == 228 and native.frame == 6840
    assert len(native.visual_events) == 31 and len(native._closed_focus) == 28
    assert not native._chain_deferred_ends and not native._deferred_visibility_ends
    assert not native._open_focus and native._general_comparison is None
    assert all(row["status"] == "closed" for row in native._formula_window_states.values())
    windows = {row["id"]: row for row in native._closed_focus}
    removed = [row for row in native._visibility_events if row["phase"] == "history_removed"]
    assert len(removed) == 5
    assert all(row["time"] == windows[row["focus"]]["end"] == 105 and row["minimum_opacity"] >= .999
               for row in removed)
    for stage in STAGES:
        focus = native._formula_stage_to_focus[stage]
        done = next(row for row in native._formula_window_events if row["focus"] == focus and row["phase"] == "action_completed")
        ready = next(row for row in native._formula_window_events if row["focus"] == focus and row["phase"] == "ready_marked")
        assert done["time"] <= ready["time"]
    with pytest.raises(ValueError):
        native.mark("expanded_ready")


def test_general_position_preserves_full_source_copy_and_complete_comparison(native):
    copy = next(row for row in native._visibility_events if row["phase"] == "complete_specific_copy_before_promotion")
    assert copy["minimum_opacity"] >= .999 and "f'(2)" in copy["latex"]
    rows = phases(native, "general_position")
    assert all(row["source_minimum_opacity"] == pytest.approx(1) for row in rows)
    compare = [row for row in native._visibility_events if row["phase"].startswith("promotion_")]
    assert len(compare) == 2
    assert all(row["time"] == 182 and row["minimum_opacity"] >= .999 for row in compare)
    assert "f'(2)" in compare[0]["latex"] and "f'(a)" in compare[1]["latex"]
    token = next(row for row in native.test_phase_witnesses if row["stage"] == "general_position" and row["phase"] == "tokens")
    assert {"position", "position_q", "position_p", "h_limit", "h_num", "h_den"} <= token["common_bounds"].keys()
    placed = placement_diagnostic(native, read("narration.json"), read("measured-timings.json"))["full_placement"]
    _, a_end = word_span(placed, "name_derivative", "pattern", ["成", "a"])
    after = next(row for row in native._chain_events if row.get("stage") == "general_position" and row["phase"] == "after")
    assert copy["time"] < after["time"] <= a_end + 1e-10


def test_fixture_keeps_v003_baseline_and_every_original_text_reference(lesson):
    plan, design = read("plan.json"), read("design.json")
    assert plan["scene"] == "examples/derivative_intro_clean_motion.py"
    assert plan["scene_class"] == "DerivativeIntroCleanMotionLesson" and plan["revision_mode"] == "revision"
    assert "examples/derivative_intro_final.py" in plan["sources"]
    assert plan["narration_draft"].endswith("narration-draft-v003.json")
    assert len(design["units"]) == 9 and sum(len(row["features"]) for row in design["units"]) == 14
    assert design["assets"]["intro_v003"]["sha256"] == "61637ddbb0141d2cbd83c944d5238fc6671a2b39892f807053fa0e157df812fe"
    assert design["timing"]["voice_plan_sha256"] == lesson.VOICE_PLAN_SHA256
    assert design["timing"]["timings_sha256"] == lesson.TIMINGS_SHA256
    from derivative_intro_audio_aligned import validate_reference_bindings
    assert len(validate_reference_bindings(read("narration.json"))) == 5


def test_spoken_numeric_words_still_match_actual_h_states(native):
    placed = placement_diagnostic(native, read("narration.json"), read("measured-timings.json"))["full_placement"]
    for tokens, h in ((["四", "点", "一"], .1), (["四", "点", "零", "二"], .02)):
        start, end = word_span(placed, "approaching", "motion", tokens)
        rows = [r for r in native.motion_samples if r["kind"] == "approach" and start <= r["time"] <= end]
        assert rows and all(r["h"] == pytest.approx(h) and r["slope"] == pytest.approx(4+h) for r in rows)
    for tokens, h in ((["零", "点", "四"], .4), (["一"], .1)):
        start, end = word_span(placed, "use_nearby", "prediction", tokens)
        rows = [r for r in native.motion_samples if r["kind"] == "prediction" and start <= r["time"] <= end]
        assert rows and all(r["h"] == pytest.approx(h) for r in rows)


def test_real_tex_actual_sources_opacity_phase_isolation_and_full_wav_schedule(lesson, monkeypatch):
    from manimind.render.manim_renderer import _render_environment
    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    with run(lesson, real_tex=True) as scene:
        result = placement_diagnostic(scene, read("narration.json"), read("measured-timings.json"))
        assert result["globally_feasible"], result
        test_four_phases_are_ordered_nonconcurrent_and_syntax_waits_for_motion(scene)
        test_actual_objects_match_phase_names_and_source_stays_complete(scene)
        test_completed_semantic_tokens_reach_the_actual_target_before_syntax(scene)
        test_general_position_preserves_full_source_copy_and_complete_comparison(scene)
        completed = [row for row in scene._visibility_events if row["phase"] == "chain_row_completed"]
        assert len(completed) == 6
        assert all(row["minimum_opacity"] >= .999 and row["bounds"][0][1] > -3.05 for row in completed)
