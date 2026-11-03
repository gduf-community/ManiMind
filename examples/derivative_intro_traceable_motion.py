"""v008: visible source-origin transfers over the intact 228-second lesson.

The construct owns copied glyphs and the append-only transfer journal. Runtime
writes them; native tests and independent pixel reviewers consume them. Copies
end at landing, history ends at the inherited removal, and all witnesses expire
when source, timing, wording, geometry or media changes. This is not approval.
"""

import sys

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from derivative_intro_final import DerivativeIntroFinalLesson
    import derivative_intro_final as previous
    from manimlib import Dot, FadeIn, Group, Transform, VGroup, ShowCreation
    from manimind.components.formula_motion import SemanticFormula
finally:
    sys.argv = _host_argv
del _host_argv


base = previous.base
refined = previous.refined
CUE_DURATIONS = previous.CUE_DURATIONS
STAGE_TIMES = previous.STAGE_TIMES
VOICE_PLAN_SHA256 = previous.VOICE_PLAN_SHA256
TIMINGS_SHA256 = previous.TIMINGS_SHA256


def parts(formula, keys):
    glyphs = dict.fromkeys(glyph for key in keys
                           for glyph in formula.tag(key).family_members_with_points())
    return VGroup(*glyphs)


class DerivativeIntroTraceableMotionLesson(DerivativeIntroFinalLesson):
    def _initialize_formula_windows(self):
        super()._initialize_formula_windows()
        self._transfer_events = []

    def _travel(self, source, target, finish, *, action, role, via=()):
        """Copy at the real source, then move; never pre-position an unseen copy."""
        moving = source.copy()
        start = float(self.get_time())
        source_box, target_box = refined.bounds(source), refined.bounds(target)
        self.add(moving)
        driver = Group()

        def track(_):
            self._transfer_events.append({
                "action": action, "role": role, "time": float(self.get_time()),
                "start": start, "finish": finish, "source_bounds": refined.bounds(source),
                "origin_bounds": source_box, "destination_bounds": target_box,
                "moving_bounds": refined.bounds(moving),
                "moving_minimum_opacity": min(float(g.get_opacity())
                                               for g in moving.family_members_with_points()),
                "source_minimum_opacity": min(float(g.get_opacity())
                                               for g in source.family_members_with_points()),
            })
            if self._active_formula_focus is not None:
                self.sample("refined_formula", stage=action, phase="tokens",
                            history=source_box, target=target_box,
                            visible_tokens=[{"id": role, "bounds": refined.bounds(moving)}],
                            syntax_opacity=0.)

        track(driver)
        self.add(driver)
        driver.add_updater(track)
        for fraction, point in via:
            waypoint = moving.copy().move_to(point)
            self.until(start + (finish-start)*fraction, Transform(moving, waypoint, path_arc=0))
        self.until(finish, Transform(moving, target, path_arc=0))
        track(driver)
        driver.clear_updaters()
        self.remove(driver, moving)
        self.add(target)

    def average(self, cue):
        self.begin_chapter(cue)
        q = Dot(base.plot_point(3, 9), radius=.075, color=base.H_COLOR)
        name = self.put("Q=(3,9)", -.15, 2.18, size=28, color=base.H_COLOR, width=2.5)
        function = self.put(r"Q=(2+h,\ f(2+h))", 3.8, 2.25, size=36, color=base.H_COLOR)
        self.beat(.14, FadeIn(self.graph()), FadeIn(q), FadeIn(name),
                  ShowCreation(self.secant_line(1)), FadeIn(function))
        self.mark("interval_points_ready")
        self.focus_begin("interval_points")
        self.beat(.32)
        self.focus_end("interval_points")
        triangle = self.increment_lines(1)
        dx = SemanticFormula(r"\Delta x=h=1", tokens={"delta_x": r"\Delta x", "h_den": "h"},
                             font_size=38).set_color(base.H_COLOR).move_to([3.8, 1.15, 0])
        dy = SemanticFormula(r"\Delta y=f(2+h)-4=5",
                             tokens={"delta_y": r"\Delta y", "output_diff": "f(2+h)-4"},
                             font_size=37).set_color(base.CURVE)
        if dy.get_width() > 5.1:
            dy.set_width(5.1)
        dy.move_to([3.8, .20, 0])
        self.beat(.38, ShowCreation(triangle[0]), FadeIn(dx))
        self.beat(.44, ShowCreation(triangle[1]), FadeIn(dy))
        self.mark("increments_ready")
        self.focus_begin("signed_increments")
        self.until(cue["start"] + 8)
        rate = SemanticFormula(r"m=\frac{\Delta y}{\Delta x}=\frac{f(2+h)-4}{h}=5",
            tokens={"delta_y": r"\Delta y", "delta_x": r"\Delta x",
                    "output_diff": "f(2+h)-4", "h_den": ("h", 1)}, font_size=40)
        if rate.get_width() > 5.1:
            rate.set_width(5.1)
        rate.move_to([3.8, -1.15, 0])
        for key, color in (("delta_y", base.CURVE), ("output_diff", base.CURVE),
                           ("delta_x", base.H_COLOR), ("h_den", base.H_COLOR)):
            rate.tag(key).set_color(color)
        syntax = self.syntax_parts(rate, rate.semantic_ids)
        self.until(cue["start"] + 8.2, FadeIn(syntax))
        self._travel(dy.tag("delta_y"), rate.tag("delta_y"), cue["start"] + 8.8,
                     action="average_ratio", role="output_increment")
        # The left lane lies between the graph and the stationary increment text.
        self._travel(dx.tag("delta_x"), rate.tag("delta_x"), cue["start"] + 9.7,
                     action="average_ratio", role="input_increment",
                     via=((.38, [1.05, .95, 0]), (.72, [1.05, -1.5, 0])))
        self._travel(dy.tag("output_diff"), rate.tag("output_diff"), cue["start"] + 10.5,
                     action="average_substitution", role="output_difference")
        self.beat(.64)
        self.focus_end("signed_increments")
        self._travel(dx.tag("h_den"), rate.tag("h_den"), self.stage_time(.74),
                     action="average_substitution", role="input_h",
                     via=((.4, [6.55, .95, 0]), (.7, [6.55, -1.5, 0])))
        self.remove(syntax, *(rate.tag(key) for key in rate.semantic_ids))
        self.add(rate, self.label("区间平均变化率 · 割线斜率", 3.8, -2.2, size=27, width=5.4))
        self.mark("average_quotient_ready")
        self.focus_begin("average_quotient")
        self.beat(1)
        self.focus_end("average_quotient")

    def readable_matching(self, source, target, end, stage):
        focus = self._formula_stage_to_focus[stage]
        state = self._formula_window_states[focus]
        if (self._active_formula_focus is not None or state["status"] != "armed"
                or not any(obj is source for obj in self.mobjects)):
            raise ValueError("One armed action needs its complete visible source")
        start, finish = float(self.get_time()), self.stage_time(end)
        if round((finish-start)*self.camera.fps) < 36:
            raise ValueError("Traceable transfers need their actual action window")
        if stage == "general_position":
            target.move_to([0, -1.45, 0])
            for formula in (source, target):
                for key in ("position", "position_q", "position_p"):
                    formula.tag(key).set_color(base.DERIVATIVE)
                for key in ("h_limit", "h_num", "h_den"):
                    formula.tag(key).set_color(base.H_COLOR)
        groups = {
            "expanded": (("h_den",), ("h_primary",), ("sub_four",)),
            "combined": (("h_den",), ("coefficient", "h_primary"), ("h_extra", "power")),
            "factored": (("h_den",), ("h_primary",), ("coefficient",), ("h_extra",)),
            "simplified": (("coefficient",), ("h_extra",)),
            "general_position": (("h_den",), ("position", "h_limit"),
                                 ("position_q", "h_num", "position_p")),
        }[stage]
        common = tuple(key for group in groups for key in group)
        syntax = self.syntax_parts(target, common)
        equality = (self.put(r"2\to a", 0, 2.15, size=34, color=base.DERIVATIVE)
                    if stage == "general_position" else
                    self.put("=", .30, float(target.get_center()[1]), size=36))
        self._formula_objects[focus] = target
        self._active_formula_focus = focus
        self._record_formula_window(state, "transition_requested")
        self._start_formula_action(state)
        self._chain_record("before", stage=stage, source=source.get_tex(), target=target.get_tex(),
                           source_bounds=refined.bounds(source), target_bounds=refined.bounds(target))
        span = finish-start
        for index, keys in enumerate(groups):
            left, right = parts(source, keys), parts(target, keys)
            via = ()
            if stage == "expanded" and keys == ("h_primary",):
                via = ((.42, [.95, 2.25, 0]),)
            if stage == "combined" and keys == ("h_extra", "power"):
                via = ((.55, [3.25, .15, 0]),)
            self._travel(left, right, start+span*.82*(index+1)/len(groups),
                         action=stage, role="+".join(keys), via=via)
        self.add(equality)
        driver = Group()

        def track(_):
            self.sample("refined_formula", stage=stage, phase="syntax",
                        history=refined.bounds(source), target=refined.bounds(target),
                        syntax_opacity=min(float(g.get_opacity())
                                           for g in syntax.family_members_with_points()))

        self.add(driver)
        driver.add_updater(track)
        self.until(finish, FadeIn(syntax))
        driver.clear_updaters()
        self.remove(driver, syntax, *(parts(target, keys) for keys in groups))
        self.add(target)
        self._visibility("chain_row_completed", focus, target)
        self._chain_rows.append(target)
        if stage == "general_position":
            self._general_comparison = (source, target)
        self._chain_record("after", stage=stage, source_bounds=refined.bounds(source),
                           target_bounds=refined.bounds(target), minimum_opacity=1.)
        self.symbol_transitions.append({"stage": stage, "start": start, "end": float(self.get_time()),
            "source": source.get_tex(), "target": target.get_tex(),
            "strategy": "visible_source_origin_group_transfers_then_new_syntax",
            "source_retained": True})
        if not all(state["samples"].values()):
            raise ValueError("A transfer must produce actual motion and completed syntax samples")
        state["status"] = "completed"
        self._record_formula_window(state, "action_completed", target=target.get_tex())
        self._active_formula_focus = None
        return target

    def _finish_formula_windows(self):
        report = super()._finish_formula_windows()
        report.update(writer="DerivativeIntroTraceableMotionLesson actual runtime",
                      status="v008_source_origin_motion_not_independent_approval",
                      transfer_events=self._transfer_events)
        report["state_contracts"].append({"state": "visible source-origin copies and transfer journal",
            "writer": "v008 actual scene runtime", "consumers": ["native tests", "independent pixel reviewers"],
            "lifecycle": "One construct; each copy removed on landing, original retained",
            "invalidation": "Source, semantic role, timing, opacity, geometry, wording or media changes"})
        return report
