"""v007 routes explicit semantic tokens without a uniform curved-path effect.

The scene records each routing decision within its current formula action.
Native tests and independent reviewers consume these witnesses; they expire
with this construct or any source, geometry, timing, text or media change.
"""

import sys

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from derivative_intro_clean_motion import DerivativeIntroCleanMotionLesson
    import derivative_intro_clean_motion as previous
    from manimlib import Transform
finally:
    sys.argv = _host_argv
del _host_argv


CUE_DURATIONS = previous.CUE_DURATIONS
STAGE_TIMES = previous.STAGE_TIMES
VOICE_PLAN_SHA256 = previous.VOICE_PLAN_SHA256
TIMINGS_SHA256 = previous.TIMINGS_SHA256


def glyph_ids(obj):
    return frozenset(id(glyph) for glyph in obj.family_members_with_points())


class DerivativeIntroRoutedMotionLesson(DerivativeIntroCleanMotionLesson):
    def _initialize_formula_windows(self):
        super()._initialize_formula_windows()
        self._routed_token_events = []

    def play(self, *animations, **kwargs):
        focus = getattr(self, "_active_formula_focus", None)
        if not focus or not animations or not all(isinstance(a, Transform) for a in animations):
            return super().play(*animations, **kwargs)
        target = self._formula_objects[focus]
        roles = {glyph_ids(target.tag(key)): key for key in target.semantic_ids}
        actions = []
        for animation in animations:
            role = roles.get(glyph_ids(animation.target_mobject))
            if role is None:
                raise ValueError("Formula routing requires an explicit target semantic identity")
            actions.append((role, animation.mobject, animation.target_mobject))
        stage = self._formula_window_states[focus]["intent"].stage
        self._routed_token_events.append({"stage": stage, "focus": focus,
            "start": float(self.get_time()), "roles": [row[0] for row in actions],
            "strategy": "straight_same_order" if stage != "factored" else "park_factor_h_then_reorder",
            "duration": kwargs.get("run_time")})
        if stage != "factored":
            return super().play(*(Transform(left, right, path_arc=0) for _, left, right in actions), **kwargs)
        primary = next((row for row in actions if row[0] == "h_primary"), None)
        if primary is None or "run_time" not in kwargs:
            raise ValueError("Factoring needs the explicitly identified h and measured duration")
        _, moving, destination = primary
        frames = round(kwargs["run_time"] * self.camera.fps)
        if frames < 9:
            raise ValueError("Three genuine semantic routing steps require actual frames")
        lengths = (frames // 3, frames // 3, frames - 2*(frames // 3))
        options = {key: value for key, value in kwargs.items() if key != "run_time"}
        parked = moving.copy().shift([0, -.5, 0])
        super().play(Transform(moving, parked, path_arc=0), run_time=lengths[0]/self.camera.fps, **options)
        super().play(*(Transform(left, right, path_arc=0) for role, left, right in actions if role != "h_primary"),
                     run_time=lengths[1]/self.camera.fps, **options)
        super().play(Transform(moving, destination, path_arc=0), run_time=lengths[2]/self.camera.fps, **options)

    def _finish_formula_windows(self):
        result = super()._finish_formula_windows()
        result.update(writer="DerivativeIntroRoutedMotionLesson actual scene runtime",
                      status="v007_actual_semantic_routing_not_independent_approval",
                      routed_token_events=self._routed_token_events)
        result["state_contracts"].append({"state": "per-action semantic routing witnesses",
            "writer": "v007 actual scene runtime", "consumers": ["native tests", "independent pixel review"],
            "lifecycle": "One construct; three factoring legs conserve the measured total frame count",
            "invalidation": "Source, role identities, geometry, timing, wording or media changes"})
        return result
