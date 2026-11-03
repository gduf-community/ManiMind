"""v010: keep the point-specific numerical result out of promotion copies.

Only general_position changes. The complete upper point definition remains;
the moving derivative/limit quotient starts at its exact source geometry but
never contains the point-only =4 tail. Runtime writes a per-frame scope journal
for tests and independent review. It expires with source, timing or media.
"""

import sys

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from derivative_intro_traceable_motion_v009 import DerivativeIntroTraceableMotionLessonV009
    import derivative_intro_traceable_motion_v009 as previous
    from manimlib import Group, Transform
    from manimind.components.formula_motion import SemanticFormula, matching_transform
finally:
    sys.argv = _host_argv
del _host_argv


base, refined = previous.base, previous.refined
CUE_DURATIONS = previous.CUE_DURATIONS
STAGE_TIMES = previous.STAGE_TIMES
VOICE_PLAN_SHA256 = previous.VOICE_PLAN_SHA256
TIMINGS_SHA256 = previous.TIMINGS_SHA256


class DerivativeIntroTraceableMotionLessonV010(DerivativeIntroTraceableMotionLessonV009):
    def _initialize_formula_windows(self):
        super()._initialize_formula_windows()
        self._general_scope_events = []

    def readable_matching(self, source, target, end, stage):
        if stage != "general_position":
            return super().readable_matching(source, target, end, stage)
        focus = self._formula_stage_to_focus[stage]
        state = self._formula_window_states[focus]
        if (self._active_formula_focus is not None or state["status"] != "armed"
                or not any(obj is source for obj in self.mobjects)):
            raise ValueError("Promotion needs its complete point-specific source")
        specific, tokens = refined.SPECIFIC_DEFINITION
        if source.get_tex() != specific or not specific.endswith("=4"):
            raise ValueError("Explicitly identify the point-only numerical conclusion")
        prefix_tex = specific.removesuffix("=4")
        prefix_source = source.get_parts_by_tex(prefix_tex)
        tail = source.get_parts_by_tex("=4")
        if len(prefix_source) != 1 or len(tail) != 1:
            raise ValueError("Keep the source quotient and point-only result separately identifiable")
        moving = SemanticFormula(prefix_tex, tokens=tokens, font_size=49)
        moving.move_to(prefix_source.get_center())
        target.move_to([0, -1.45, 0])
        for formula in (source, moving, target):
            for key in ("position", "position_q", "position_p"):
                formula.tag(key).set_color(base.DERIVATIVE)
            for key in ("h_limit", "h_num", "h_den"):
                formula.tag(key).set_color(base.H_COLOR)
        for key in moving.semantic_ids:
            if max(abs(moving.tag(key).get_center()-source.tag(key).get_center())) > 1e-5:
                raise ValueError("The restricted copy must start at the actual upper source glyphs")
        start, finish = float(self.get_time()), self.stage_time(end)
        landed = moving.copy()
        landed.shift([target.get_left()[0]-landed.get_left()[0],
                      target.get_center()[1]-landed.get_center()[1], 0])
        equality = self.put(r"2\to a", 0, 2.15, size=34, color=base.DERIVATIVE)
        self._formula_objects[focus] = target
        self._active_formula_focus = focus
        self._record_formula_window(state, "transition_requested")
        self._start_formula_action(state)
        self._chain_record("before", stage=stage, source=source.get_tex(), target=target.get_tex(),
                           source_bounds=refined.bounds(source), target_bounds=refined.bounds(target))
        phase = {"name": "complete_copy_transport", "active": moving}
        driver = Group()

        def track(_):
            active = phase["active"]
            numeric_parts = len(active.get_parts_by_tex("=4"))
            row = {"stage": stage, "phase": phase["name"], "time": float(self.get_time()),
                "source_bounds": refined.bounds(source), "active_bounds": refined.bounds(active),
                "source_tex": source.get_tex(), "active_tex": active.get_tex(), "target_tex": target.get_tex(),
                "source_minimum_opacity": min(float(g.get_opacity()) for g in source.family_members_with_points()),
                "active_minimum_opacity": min(float(g.get_opacity()) for g in active.family_members_with_points())}
            self._structured_copy_events.append(row)
            self._general_scope_events.append({**row, "active_numeric_tail_count": numeric_parts,
                "upper_numeric_tail_bounds": refined.bounds(tail),
                "upper_numeric_tail_minimum_opacity": min(float(g.get_opacity()) for g in tail.family_members_with_points())})
            if numeric_parts:
                raise ValueError("A general-position actor cannot contain the point-only =4 result")
            self.sample("refined_formula", stage=stage,
                        phase="tokens" if phase["name"] == "complete_copy_transport" else "syntax",
                        history=refined.bounds(source), target=refined.bounds(target), syntax_opacity=1.)

        self.add(moving)
        track(driver)
        self.add(driver)
        driver.add_updater(track)
        self.until(start+(finish-start)*.42, Transform(moving, landed, path_arc=0))
        self.add(equality)
        self._visibility("complete_visible_copy_arrived_from_source_without_numeric_tail", focus, moving)
        phase["name"] = "structured_local_rewrite"
        self.until(finish, matching_transform(moving, target, run_time=finish-self.get_time(),
                                             path_arc=0, unmatched_in_place=True))
        phase["active"] = target
        track(driver)
        driver.clear_updaters()
        self.remove(driver)
        self._visibility("chain_row_completed", focus, target)
        self._chain_rows.append(target)
        self._general_comparison = (source, target)
        self._chain_record("after", stage=stage, source_bounds=refined.bounds(source),
                           target_bounds=refined.bounds(target), minimum_opacity=1.)
        self.symbol_transitions.append({"stage": stage, "start": start, "end": float(self.get_time()),
            "source": source.get_tex(), "target": target.get_tex(),
            "strategy": "source_origin_complete_quotient_copy_without_point_only_result_then_promotion",
            "source_retained": True, "numeric_result_only_in_upper_specific_formula": True})
        if not all(state["samples"].values()):
            raise ValueError("Promotion must record actual transport and local operation")
        state["status"] = "completed"
        self._record_formula_window(state, "action_completed", target=target.get_tex())
        self._active_formula_focus = None
        return target

    def _finish_formula_windows(self):
        report = super()._finish_formula_windows()
        report.update(writer="DerivativeIntroTraceableMotionLessonV010 actual runtime",
                      status="v010_numeric_scope_repair_candidate_not_independent_approval",
                      general_scope_events=self._general_scope_events)
        report["state_contracts"].append({"state": "promotion-only numerical-scope witnesses",
            "writer": "v010 actual scene runtime", "consumers": ["native tests", "independent reviewers"],
            "lifecycle": "One promotion; the full specific formula remains, moving prefix never contains =4",
            "invalidation": "Source, scope selection, glyph geometry, timing, media or review changes"})
        return report
