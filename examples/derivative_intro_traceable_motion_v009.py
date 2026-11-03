"""v009 repairs observed v008 process pixels without changing frozen inputs.

Complete visible copies travel from history into the next active row before a
local semantic rewrite. The construct writes its copy/rewrite journal; tests
and independent reviewers consume it. Copies end on native replacement and
history ends on inherited removal. Any source/timing/media change invalidates
these observations. No review approval is supplied here.
"""

import sys

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from derivative_intro_traceable_motion import DerivativeIntroTraceableMotionLesson
    import derivative_intro_traceable_motion as previous
    from manimlib import Dot, FadeIn, Group, Transform, VGroup, ShowCreation
    from manimind.components.formula_motion import SemanticFormula, matching_transform
finally:
    sys.argv = _host_argv
del _host_argv


base, refined = previous.base, previous.refined
CUE_DURATIONS = previous.CUE_DURATIONS
STAGE_TIMES = previous.STAGE_TIMES
VOICE_PLAN_SHA256 = previous.VOICE_PLAN_SHA256
TIMINGS_SHA256 = previous.TIMINGS_SHA256


class DerivativeIntroTraceableMotionLessonV009(DerivativeIntroTraceableMotionLesson):
    def _initialize_formula_windows(self):
        super()._initialize_formula_windows()
        self._structured_copy_events = []
        self._average_reveals = []

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
                    "output_diff": "f(2+h)-4", "h_den": ("h", 1),
                    "head": "m=", "substitution_equal": ("=", 1), "result": "=5"}, font_size=40)
        if rate.get_width() > 5.1:
            rate.set_width(5.1)
        rate.move_to([3.8, -1.15, 0])
        for key, color in (("delta_y", base.CURVE), ("output_diff", base.CURVE),
                           ("delta_x", base.H_COLOR), ("h_den", base.H_COLOR)):
            rate.tag(key).set_color(color)
        bars = sorted(self.syntax_parts(rate, rate.semantic_ids).submobjects,
                      key=lambda obj: obj.get_center()[0])
        if len(bars) != 2:
            raise ValueError("The two native fraction bars must be explicitly separable")
        self.until(cue["start"] + 8.2, FadeIn(rate.tag("head")), FadeIn(bars[0]))
        self._average_reveals.append({"part": "symbolic_ratio_scaffold", "time": float(self.get_time())})
        self._travel(dy.tag("delta_y"), rate.tag("delta_y"), cue["start"] + 8.8,
                     action="average_ratio", role="output_increment")
        self._travel(dx.tag("delta_x"), rate.tag("delta_x"), cue["start"] + 9.7,
                     action="average_ratio", role="input_increment",
                     via=((.38, [1.05, .95, 0]), (.72, [1.05, -1.5, 0])))
        self.add(rate.tag("substitution_equal"), bars[1])
        self._average_reveals.append({"part": "substitution_scaffold", "time": float(self.get_time())})
        self._travel(dy.tag("output_diff"), rate.tag("output_diff"), cue["start"] + 10.5,
                     action="average_substitution", role="output_difference")
        self.beat(.64)
        self.focus_end("signed_increments")
        self._travel(dx.tag("h_den"), rate.tag("h_den"), self.stage_time(.74),
                     action="average_substitution", role="input_h",
                     via=((.4, [6.55, 1.55, 0]), (.7, [6.55, -1.75, 0])))
        self._average_reveals.append({"part": "numeric_result_after_complete_substitution", "time": float(self.get_time())})
        self.remove(*bars, *(rate.tag(key) for key in rate.semantic_ids if key != "result"))
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
            raise ValueError("A structured copy needs its actual complete source")
        start, finish = float(self.get_time()), self.stage_time(end)
        span = finish-start
        if round(span*self.camera.fps) < 36:
            raise ValueError("Do not compress a complete transport and rewrite below its action window")
        if stage == "general_position":
            target.move_to([0, -1.45, 0])
            for formula in (source, target):
                for key in ("position", "position_q", "position_p"):
                    formula.tag(key).set_color(base.DERIVATIVE)
                for key in ("h_limit", "h_num", "h_den"):
                    formula.tag(key).set_color(base.H_COLOR)
        equality = (self.put(r"2\to a", 0, 2.15, size=34, color=base.DERIVATIVE)
                    if stage == "general_position" else
                    self.put("=", .30, float(target.get_center()[1]), size=36))
        moving = source.copy()
        landed = moving.copy()
        landed.shift([target.get_left()[0]-landed.get_left()[0],
                      target.get_center()[1]-landed.get_center()[1], 0])
        self._formula_objects[focus] = target
        self._active_formula_focus = focus
        self._record_formula_window(state, "transition_requested")
        self._start_formula_action(state)
        self._chain_record("before", stage=stage, source=source.get_tex(), target=target.get_tex(),
                           source_bounds=refined.bounds(source), target_bounds=refined.bounds(target))
        self.add(moving)
        driver = Group()
        phase = {"name": "complete_copy_transport", "active": moving}

        def track(_):
            active = phase["active"]
            self._structured_copy_events.append({"stage": stage, "phase": phase["name"],
                "time": float(self.get_time()), "source_bounds": refined.bounds(source),
                "active_bounds": refined.bounds(active), "source_tex": source.get_tex(),
                "active_tex": active.get_tex(), "target_tex": target.get_tex(),
                "source_minimum_opacity": min(float(g.get_opacity()) for g in source.family_members_with_points()),
                "active_minimum_opacity": min(float(g.get_opacity()) for g in active.family_members_with_points())})
            self.sample("refined_formula", stage=stage, phase=("tokens" if phase["name"] == "complete_copy_transport" else "syntax"),
                        history=refined.bounds(source), target=refined.bounds(target), syntax_opacity=1.)

        track(driver)
        self.add(driver)
        driver.add_updater(track)
        transport_end = start+span*.42
        self.until(transport_end, Transform(moving, landed, path_arc=0))
        self.add(equality)
        self._visibility("complete_visible_copy_arrived_from_source", focus, moving)
        phase["name"] = "structured_local_rewrite"
        pairs = [(key, key) for key in source.semantic_ids if key in target.semantic_ids
                 and not (stage == "expanded" and key == "power")]
        if stage == "factored":
            factor = moving.tag("h_primary")
            raised = factor.copy().shift([0, .45, 0])
            self.until(start+span*.52, Transform(factor, raised, path_arc=0))
            parked = factor.copy().move_to([.52, float(factor.get_center()[1]), 0])
            self.until(start+span*.62, Transform(factor, parked, path_arc=0))
            interim = target.copy()
            interim.tag("h_primary").move_to(factor.get_center())
            self.until(start+span*.85, matching_transform(moving, interim, pairs=pairs,
                       run_time=span*.23, path_arc=0, unmatched_in_place=True))
            phase["active"] = interim
            self.until(finish, Transform(interim.tag("h_primary"), target.tag("h_primary"), path_arc=0))
            self.remove(interim)
            self.add(target)
        else:
            self.until(finish, matching_transform(moving, target, pairs=pairs,
                       run_time=finish-self.get_time(), path_arc=0, unmatched_in_place=True))
        driver.clear_updaters()
        self.remove(driver)
        self._visibility("chain_row_completed", focus, target)
        self._chain_rows.append(target)
        if stage == "general_position":
            self._general_comparison = (source, target)
        self._chain_record("after", stage=stage, source_bounds=refined.bounds(source),
                           target_bounds=refined.bounds(target), minimum_opacity=1.)
        self.symbol_transitions.append({"stage": stage, "start": start, "end": float(self.get_time()),
            "source": source.get_tex(), "target": target.get_tex(),
            "strategy": "visible_complete_copy_transport_then_structured_local_operation",
            "source_retained": True})
        if not all(state["samples"].values()):
            raise ValueError("Record actual complete-copy transport and structured rewrite")
        state["status"] = "completed"
        self._record_formula_window(state, "action_completed", target=target.get_tex())
        self._active_formula_focus = None
        return target

    def _finish_formula_windows(self):
        report = super()._finish_formula_windows()
        report.update(writer="DerivativeIntroTraceableMotionLessonV009 actual runtime",
                      status="v009_structured_source_copy_candidate_not_independent_approval",
                      structured_copy_events=self._structured_copy_events, average_reveals=self._average_reveals)
        report["state_contracts"].append({"state": "complete moving copies, local rewrites and deferred average reveals",
            "writer": "v009 actual scene runtime", "consumers": ["native tests", "independent pixel reviewers"],
            "lifecycle": "One construct; source retained, moving copy replaced on arrival and operation completion",
            "invalidation": "Source, timing, opacity, semantic mapping, geometry, text or media change"})
        return report
