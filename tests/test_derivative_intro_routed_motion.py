"""Bounded v007 native routing and intact-audio checks, never pixel approval."""

from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from lesson_native_harness import load_lesson, native_run
from test_derivative_intro_visual import forbid_production_project_reads
from test_derivative_intro_voiced import placement_diagnostic


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/derivative-intro-routed-motion"
VOICE_FIXTURE = ROOT / "tests/fixtures/derivative-intro-voiced"


def read(name):
    directory = FIXTURE if name in {"plan.json", "design.json"} else VOICE_FIXTURE
    return json.loads((directory / name).read_text(encoding="utf-8"))


def load():
    with pytest.MonkeyPatch.context() as patcher:
        patcher.syspath_prepend(str(ROOT / "examples"))
        return load_lesson(ROOT / "examples/derivative_intro_routed_motion.py")


@contextmanager
def run(lesson, real_tex=False):
    import derivative_intro_refined as refined
    import manimind.components.formula_motion as motion
    real_formula = refined.SemanticFormula
    with pytest.MonkeyPatch.context() as patcher:
        def initialize(scene):
            import manimlib as gl
            if real_tex:
                refined.SemanticFormula = real_formula
                motion.SemanticFormula = real_formula
                patcher.setattr(scene, "formula", refined.base.DerivativeIntroLesson.formula.__get__(scene))
            patcher.setattr(refined.base, "SemanticFormula", refined.SemanticFormula)
            patcher.setattr(scene, "assemble_render_groups", lambda: None)
            patcher.setattr(scene, "remove", lesson.DerivativeIntroRoutedMotionLesson.remove.__get__(scene))
            actual_route, actual_native = scene.play, gl.Scene.play
            active = {"request": None}
            scene.test_route_requests, scene.test_native_legs = [], []

            def route(*animations, **kwargs):
                focus = scene._active_formula_focus
                if not focus or not animations or not all(isinstance(a, gl.Transform) for a in animations):
                    return actual_route(*animations, **kwargs)
                target = scene._formula_objects[focus]
                roles = {lesson.glyph_ids(target.tag(key)): key for key in target.semantic_ids}
                parts = {roles[lesson.glyph_ids(a.target_mobject)]: a.mobject for a in animations}
                request = {"stage": scene._formula_window_states[focus]["intent"].stage,
                           "start": float(scene.get_time()), "start_frame": scene.frame,
                           "duration": kwargs["run_time"], "roles": list(parts), "parts": parts}
                active["request"] = request
                try:
                    result = actual_route(*animations, **kwargs)
                finally:
                    active["request"] = None
                scene.test_route_requests.append({key: value for key, value in request.items() if key != "parts"})
                scene.test_route_requests[-1].update(end=float(scene.get_time()), end_frame=scene.frame)
                return result

            def native(current, *animations, **kwargs):
                request = active["request"]
                if request is None:
                    return actual_native(current, *animations, **kwargs)
                parts = request["parts"]
                names = []
                for animation in animations:
                    match = [role for role, obj in parts.items() if obj is animation.mobject]
                    assert len(match) == 1, "A routed native Transform must retain its explicit source identity"
                    names.append(match[0])
                row = {"stage": request["stage"], "start": float(scene.get_time()), "start_frame": scene.frame,
                       "roles": names, "requested_duration": kwargs["run_time"],
                       "path_arcs": [float(a.path_arc) for a in animations],
                       "before": {role: obj.get_center().tolist() for role, obj in parts.items()},
                       "destinations": {role: a.target_mobject.get_center().tolist()
                                        for role, a in zip(names, animations, strict=True)}}
                result = actual_native(current, *animations, **kwargs)
                row.update(end=float(scene.get_time()), end_frame=scene.frame,
                           after={role: obj.get_center().tolist() for role, obj in parts.items()})
                scene.test_native_legs.append(row)
                return result

            patcher.setattr(scene, "play", route)
            patcher.setattr(gl.Scene, "play", native)
        with native_run(refined, lesson.DerivativeIntroRoutedMotionLesson, read("plan.json"),
                        initialize=initialize) as scene:
            yield scene


@pytest.fixture(scope="module")
def lesson():
    return load()


@pytest.fixture(scope="module")
def native(lesson):
    with run(lesson) as scene:
        return scene


def check_schedule(scene):
    result = placement_diagnostic(scene, read("narration.json"), read("measured-timings.json"))
    assert result["globally_feasible"], result
    assert len(result["full_placement"]) == 9 and all(row["individually_feasible"] for row in result["units"])
    assert sum(row["duration_seconds"] for row in result["full_placement"]) == pytest.approx(184.64)
    assert sum(len(row["phrases"]) for row in result["full_placement"]) == 28
    for unit in result["full_placement"]:
        for ref in unit["phrases"]:
            assert ref["focus_start"] - 1e-10 <= ref["visual_start"] <= ref["visual_end"] <= ref["focus_end"] + 1e-10
    return result


def test_native_constructor_and_full_original_wav_schedule(native):
    check_schedule(native)
    assert native.time == 228 and native.frame == 6840
    assert len(native._routed_token_events) == len(native.test_route_requests) == 5


def test_only_semantic_actions_route_and_nonfactoring_transfers_are_straight(native):
    assert {row["stage"] for row in native._routed_token_events} == {
        "expanded", "combined", "factored", "simplified", "general_position"}
    for request in native.test_route_requests:
        event = next(row for row in native._routed_token_events if row["stage"] == request["stage"])
        assert event["focus"] == native._formula_stage_to_focus[request["stage"]]
        assert event["roles"] == request["roles"]
        if request["stage"] != "factored":
            legs = [row for row in native.test_native_legs if row["stage"] == request["stage"]]
            assert len(legs) == 1 and legs[0]["roles"] == request["roles"]
    assert all(arc == 0 for row in native.test_native_legs for arc in row["path_arcs"])


def test_factored_h_parks_half_a_unit_then_returns_without_changing_frame_budget(native):
    legs = [row for row in native.test_native_legs if row["stage"] == "factored"]
    request = next(row for row in native.test_route_requests if row["stage"] == "factored")
    assert len(legs) == 3 and legs[0]["roles"] == legs[2]["roles"] == ["h_primary"]
    assert "h_primary" not in legs[1]["roles"]
    assert set(legs[1]["roles"]) == set(request["roles"]) - {"h_primary"}
    start = legs[0]["before"]["h_primary"]
    assert legs[0]["after"]["h_primary"] == pytest.approx([start[0], start[1]-.5, start[2]])
    assert legs[1]["before"]["h_primary"] == pytest.approx(legs[0]["after"]["h_primary"])
    assert legs[1]["after"]["h_primary"] == pytest.approx(legs[0]["after"]["h_primary"])
    assert legs[2]["after"]["h_primary"] == pytest.approx(legs[2]["destinations"]["h_primary"])
    frames = round(request["duration"] * 30)
    assert [row["end_frame"]-row["start_frame"] for row in legs] == [frames//3, frames//3, frames-2*(frames//3)]
    assert legs[-1]["end_frame"]-legs[0]["start_frame"] == request["end_frame"]-request["start_frame"] == frames
    assert all(a["end_frame"] == b["start_frame"] for a, b in zip(legs, legs[1:]))


def test_routing_keeps_history_opaque_and_original_focus_lifecycles(native):
    assert all(row["source_minimum_opacity"] == pytest.approx(1) for row in native._clean_motion_events)
    for stage in {row["stage"] for row in native._clean_motion_events}:
        rows = [row for row in native._clean_motion_events if row["stage"] == stage]
        assert all(row["source_bounds"] == pytest.approx(rows[0]["source_bounds"]) for row in rows)
        assert all(row["target_syntax_opacity"] == pytest.approx(0)
                   for row in rows if row["phase"] == "tokens")
    assert len(native._closed_focus) == 28 and len(native.visual_events) == 31
    assert not native._open_focus and not native._chain_deferred_ends and not native._deferred_visibility_ends
    assert all(row["status"] == "closed" for row in native._formula_window_states.values())
    comparison = [row for row in native._visibility_events if row["phase"].startswith("promotion_")]
    assert len(comparison) == 2 and all(row["time"] == 182 and row["minimum_opacity"] >= .999 for row in comparison)


def test_versionable_fixture_preserves_same_audio_text_and_v003_baseline(lesson):
    plan, design = read("plan.json"), read("design.json")
    assert plan["scene"] == "examples/derivative_intro_routed_motion.py"
    assert plan["scene_class"] == "DerivativeIntroRoutedMotionLesson"
    assert "examples/derivative_intro_clean_motion.py" in plan["sources"]
    assert plan["narration_draft"].endswith("narration-draft-v003.json") and plan["duration"] == 228
    assert design["timing"]["voice_plan_sha256"] == lesson.VOICE_PLAN_SHA256
    assert design["timing"]["timings_sha256"] == lesson.TIMINGS_SHA256
    assert len(design["units"]) == 9 and sum(len(row["features"]) for row in design["units"]) == 14
    assert design["assets"]["intro_v003"]["sha256"] == "61637ddbb0141d2cbd83c944d5238fc6671a2b39892f807053fa0e157df812fe"


def test_real_tex_routing_constructor_integer_frame_legs_and_full_wav_schedule(lesson, monkeypatch):
    from manimind.render.manim_renderer import _render_environment
    monkeypatch.setenv("PATH", _render_environment()["PATH"])
    with run(lesson, real_tex=True) as scene:
        check_schedule(scene)
        test_only_semantic_actions_route_and_nonfactoring_transfers_are_straight(scene)
        test_factored_h_parks_half_a_unit_then_returns_without_changing_frame_budget(scene)
        test_routing_keeps_history_opaque_and_original_focus_lifecycles(scene)
