"""v006 separates complete-copy reveal, token motion and syntax reveal.

One construct owns the phase journal. The scene is its writer; native checks
and independent pixel reviewers consume it. A complete copy appears in the new
row before isolated token movement; the original row remains opaque throughout.
Source, wording, timing or media changes invalidate these witnesses.
"""

import sys

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from derivative_intro_final import DerivativeIntroFinalLesson
    import derivative_intro_final as previous
    from manimlib import Group, Transform, UpdateFromAlphaFunc
finally:
    sys.argv = _host_argv
del _host_argv


base = previous.base
refined = previous.refined
CUE_DURATIONS = previous.CUE_DURATIONS
STAGE_TIMES = previous.STAGE_TIMES
VOICE_PLAN_SHA256 = previous.VOICE_PLAN_SHA256
TIMINGS_SHA256 = previous.TIMINGS_SHA256


class DerivativeIntroCleanMotionLesson(DerivativeIntroFinalLesson):
    def _initialize_formula_windows(self):
        super()._initialize_formula_windows()
        self._clean_motion_events = []

    def readable_matching(self, source, target, end, stage):
        if self._cue["id"] != "algebra" and stage != "general_position":
            return super().readable_matching(source, target, end, stage)
        focus = self._formula_stage_to_focus[stage]
        state = self._formula_window_states[focus]
        if (self._active_formula_focus is not None or state["status"] != "armed"
                or not any(obj is source for obj in self.mobjects)):
            raise ValueError("Clean motion requires one armed action and its complete source")
        start, finish = float(self.get_time()), self.stage_time(end)
        span = finish - start
        if round(span * self.camera.fps) < 24:
            raise ValueError("The complete copy and rewrite need actual animation time")
        if stage == "general_position":
            target.move_to([0, -1.45, 0])
            for formula in (source, target):
                for key in ("position", "position_q", "position_p"):
                    formula.tag(key).set_color(base.DERIVATIVE)
                for key in ("h_limit", "h_num", "h_den"):
                    formula.tag(key).set_color(base.H_COLOR)
        common = tuple(key for key in source.semantic_ids if key in target.semantic_ids)
        moving = source.copy()
        moving_parts = {key: moving.tag(key) for key in common}
        old_syntax = self.syntax_parts(moving, common)
        new_syntax = self.syntax_parts(target, common)
        new_syntax.set_opacity(0)
        label = (self.put(r"2\to a", 0, 2.15, size=34, color=base.DERIVATIVE)
                 if stage == "general_position" else
                 self.put("=", .30, float(target.get_center()[1]), size=36))
        self._formula_objects[focus] = target
        self._active_formula_focus = focus
        self._record_formula_window(state, "transition_requested")
        self._start_formula_action(state)
        source_box = refined.bounds(source)
        self._chain_record("before", stage=stage, source=source.get_tex(), target=target.get_tex(),
                           source_bounds=source_box, target_bounds=refined.bounds(target))
        phase = {"name": "complete_copy"}
        driver = Group()

        def record(_):
            syntax = new_syntax.family_members_with_points()
            opacity = min(float(g.get_opacity()) for g in syntax) if syntax else 1.
            row = {"stage": stage, "phase": phase["name"], "time": float(self.get_time()),
                   "source_bounds": refined.bounds(source), "moving_bounds": refined.bounds(moving),
                   "source_minimum_opacity": min(float(g.get_opacity()) for g in source.family_members_with_points()),
                   "copy_minimum_opacity": min(float(g.get_opacity()) for g in moving.family_members_with_points()),
                   "target_syntax_opacity": opacity}
            self._clean_motion_events.append(row)
            if phase["name"] in {"tokens", "syntax"}:
                self.sample("refined_formula", stage=stage, phase=phase["name"],
                            history=source_box, target=refined.bounds(target),
                            visible_tokens=[{"id": key, "bounds": refined.bounds(
                                                target.tag(key) if phase["name"] == "syntax" else moving_parts[key])}
                                            for key in common], syntax_opacity=opacity)

        moving.shift([target.get_left()[0]-moving.get_left()[0],
                      target.get_center()[1]-moving.get_center()[1], 0]).set_opacity(0)
        self.add(moving, driver, label)
        driver.add_updater(record)
        self.until(start + span * .30, UpdateFromAlphaFunc(moving, lambda mob, alpha: mob.set_opacity(alpha)))
        if stage == "general_position":
            self._visibility("complete_specific_copy_before_promotion", focus, moving)
        phase["name"] = "syntax_out"
        self.until(start + span * .42,
                   UpdateFromAlphaFunc(moving, lambda _, alpha: old_syntax.set_opacity(1-alpha)))
        old_syntax.set_opacity(0)
        phase["name"] = "tokens"
        self.until(start + span * .78,
                   *(Transform(moving_parts[key], target.tag(key), path_arc=base.np.pi/2) for key in common))
        self.remove(moving, *moving_parts.values())
        new_syntax.set_opacity(0)
        self.add(target)
        phase["name"] = "syntax"
        self.until(finish, UpdateFromAlphaFunc(target, lambda _, alpha: new_syntax.set_opacity(alpha)))
        driver.clear_updaters()
        self.remove(driver)
        self._visibility("chain_row_completed", focus, target)
        self._chain_rows.append(target)
        if stage == "general_position":
            self._general_comparison = (source, target)
        self._chain_record("after", stage=stage, source_bounds=refined.bounds(source),
                           target_bounds=refined.bounds(target), equality_bounds=refined.bounds(label),
                           minimum_opacity=min(float(g.get_opacity()) for g in target.family_members_with_points()))
        self.symbol_transitions.append({"stage": stage, "start": start, "end": float(self.get_time()),
            "source": source.get_tex(), "target": target.get_tex(),
            "strategy": "complete_copy_then_isolated_semantic_arcs_then_syntax",
            "history_bounds": source_box, "target_bounds": refined.bounds(target),
            "source_retained": True})
        if not all(state["samples"].values()) or not any(obj is target for obj in self.mobjects):
            raise ValueError("Clean motion must actually complete both token and syntax phases")
        state["status"] = "completed"
        self._record_formula_window(state, "action_completed", target=target.get_tex())
        self._active_formula_focus = None
        return target

    def _finish_formula_windows(self):
        result = super()._finish_formula_windows()
        result.update(writer="DerivativeIntroCleanMotionLesson actual scene runtime",
                      status="v006_actual_motion_not_independent_approval",
                      clean_motion_events=self._clean_motion_events)
        result["state_contracts"].append({"state": "phase journal and complete-expression copy",
            "writer": "v006 actual scene runtime", "consumers": ["native tests", "independent pixel review"],
            "lifecycle": "One construct; copy leaves before final syntax appears; original stays visible",
            "invalidation": "Any source, wording, timings, opacity or media change"})
        return result
