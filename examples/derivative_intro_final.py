"""v005: stationary, equality-linked algebra over unchanged measured V01 takes.

The construct owns the row registry, deferred state ends and append-only chain
journal. Runtime is their sole writer; native diagnostics and independent pixel
review consume them. Rows expire on actual removal, journals on any source,
timing, text, runtime or media change. This source grants no review approval.
"""

import sys

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from derivative_intro_voiced import DerivativeIntroVoicedLesson
    from derivative_intro_audio_aligned import DerivativeIntroAudioAlignedLesson
    import derivative_intro_voiced as voiced
    import derivative_intro_refined as refined
    from manimlib import Dot, FadeIn, Group, Line, ShowCreation, VGroup
finally:
    sys.argv = _host_argv
del _host_argv


base = refined.base
CUE_DURATIONS = voiced.CUE_DURATIONS
STAGE_TIMES = voiced.STAGE_TIMES
VOICE_PLAN_SHA256 = voiced.VOICE_PLAN_SHA256
TIMINGS_SHA256 = voiced.TIMINGS_SHA256
ROW_Y = (2.35, 1.15, -.05, -1.25, -2.45)
ROW_LEFT = .85
CHAIN_HISTORY_FOCI = {"quotient_substitution", "expanded_terms", "combined_terms", "factored_h", "nonzero_cancel"}


class DerivativeIntroFinalLesson(DerivativeIntroVoicedLesson):
    def _initialize_formula_windows(self):
        super()._initialize_formula_windows()
        self._chain_rows = []
        self._chain_events = []
        self._chain_deferred_ends = set()
        self._general_comparison = None

    def algebra_formula(self, index):
        _, latex, tokens = base.ALGEBRA[index]
        colors = {key: base.H_COLOR for key in tokens if key.startswith("h_")}
        if "coefficient" in tokens:
            colors["coefficient"] = base.DERIVATIVE
        formula = refined.SemanticFormula(latex, tokens=tokens, font_size=44).set_color(base.INK)
        for key, color in colors.items():
            formula.tag(key).set_color(color)
        formula.move_to([0, ROW_Y[index], 0])
        formula.shift([ROW_LEFT - formula.get_left()[0], 0, 0])
        if index == 0:
            self._formula_objects["quotient_substitution"] = formula
        return formula

    def _chain_record(self, phase, **details):
        self._chain_events.append({"phase": phase, "time": float(self.get_time()), **details})

    def readable_matching(self, source, target, end, stage):
        if self._cue["id"] != "algebra" and stage != "general_position":
            return super().readable_matching(source, target, end, stage)
        focus = self._formula_stage_to_focus[stage]
        state = self._formula_window_states[focus]
        if (self._active_formula_focus is not None or state["status"] != "armed"
                or not any(obj is source for obj in self.mobjects)):
            raise ValueError("A chain action needs one armed intent and its complete visible source")
        start, finish = float(self.get_time()), self.stage_time(end)
        if round((finish - start) * self.camera.fps) < 12:
            raise ValueError("A chain transition needs at least twelve actual frames")
        if stage == "general_position":
            target.move_to([0, -1.45, 0])
            for formula in (source, target):
                for key in ("position", "position_q", "position_p"):
                    formula.tag(key).set_color(base.DERIVATIVE)
                for key in ("h_limit", "h_num", "h_den"):
                    formula.tag(key).set_color(base.H_COLOR)
        source_box = refined.bounds(source)
        common = tuple(key for key in source.semantic_ids if key in target.semantic_ids)
        moving = source.copy()
        new_syntax = self.syntax_parts(target, common)
        equality = (self.put(r"2\to a", 0, 2.15, size=34, color=base.DERIVATIVE)
                    if stage == "general_position" else
                    self.put("=", .30, float(target.get_center()[1]), size=36))
        self._formula_objects[focus] = target
        self._active_formula_focus = focus
        self._record_formula_window(state, "transition_requested")
        # The condition is already stationary, so simplified assembly starts now.
        self._start_formula_action(state)
        self._chain_record("before", stage=stage, source=source.get_tex(), target=target.get_tex(),
                           source_bounds=source_box, target_bounds=refined.bounds(target))
        driver = Group()

        def track(_):
            syntax_glyphs = new_syntax.family_members_with_points()
            opacity = min(float(g.get_opacity()) for g in syntax_glyphs) if syntax_glyphs else 1.
            tokens = [{"id": key, "bounds": refined.bounds(moving.tag(key))} for key in common]
            values = {"stage": stage, "history": source_box, "target": refined.bounds(target),
                      "visible_tokens": tokens, "syntax_opacity": opacity}
            # Native matching moves tagged glyphs and reveals unmatched syntax
            # concurrently; neither a second syntax-only phase nor a home move.
            self.sample("refined_formula", phase="tokens", **values)
            self.sample("refined_formula", phase="syntax", **values)
            self._chain_record("during", stage=stage, source_bounds=refined.bounds(source),
                               target_bounds=refined.bounds(target), tokens=tokens,
                               source_minimum_opacity=min(float(g.get_opacity())
                                   for g in source.family_members_with_points()),
                               target_syntax_opacity=opacity)

        if stage == "general_position":
            # Copy a complete quotient into its final row before changing the
            # three position symbols. Its fraction structure is never withheld.
            moving.move_to(target.get_center())
            self.until(start + .4, FadeIn(moving), FadeIn(equality))
            self._visibility("complete_specific_copy_before_promotion", focus, moving)
        self.add(moving, driver)
        driver.add_updater(track)
        animations = [refined.matching_transform(moving, target, run_time=finish-self.get_time(),
                                                  path_arc=0, unmatched_in_place=True)]
        if stage != "general_position":
            animations.append(FadeIn(equality))
        self.until(finish, *animations)
        driver.clear_updaters()
        self.remove(driver)
        self._visibility("chain_row_completed", focus, target)
        self._chain_rows.append(target)
        if stage == "general_position":
            self._general_comparison = (source, target)
        self._chain_record("after", stage=stage, source_bounds=refined.bounds(source),
                           target_bounds=refined.bounds(target), equality_bounds=refined.bounds(equality),
                           minimum_opacity=min(float(g.get_opacity())
                               for g in target.family_members_with_points()))
        self.symbol_transitions.append({"stage": stage, "start": start, "end": float(self.get_time()),
            "source": source.get_tex(), "target": target.get_tex(),
            "strategy": ("complete_copy_in_place_promotion" if stage == "general_position" else
                         "stationary_equality_chain_semantic_matching"), "history_bounds": source_box,
            "target_bounds": refined.bounds(target), "source_retained": True})
        if not all(state["samples"].values()) or not any(obj is target for obj in self.mobjects):
            raise ValueError("The native formula action must finish with actual syntax and tagged glyphs")
        state["status"] = "completed"
        self._record_formula_window(state, "action_completed", target=target.get_tex())
        self._active_formula_focus = None
        return target

    def focus_end(self, identity):
        if self._cue["id"] == "algebra" and identity in CHAIN_HISTORY_FOCI:
            if identity not in self._open_focus or identity in self._chain_deferred_ends:
                raise ValueError("A retained chain state needs exactly one requested end")
            self._chain_deferred_ends.add(identity)
            return
        super().focus_end(identity)

    def remove(self, *objects):
        for identity in tuple(getattr(self, "_chain_deferred_ends", ())):
            obj = self._formula_objects[identity]
            if any(obj is removed for removed in objects):
                self._visibility("history_removed", identity, obj)
                DerivativeIntroAudioAlignedLesson.focus_end(self, identity)
                self._chain_deferred_ends.remove(identity)
        return super().remove(*objects)

    def algebra(self, cue):
        self.begin_chapter(cue)
        p = lambda x, y: [-5.5 + 1.2 * (x - 2), 1.1 + .36 * (y - 4), 0]
        diagram = VGroup(base.path([p(x, base.square(x)) for x in base.np.linspace(1.7, 2.8, 50)]),
                         Line(p(2, 4), p(2.7, 4), color=base.H_COLOR, stroke_width=4),
                         Line(p(2.7, 4), p(2.7, base.square(2.7)), color=base.CURVE, stroke_width=4),
                         Dot(p(2, 4), color=base.INK), Dot(p(2.7, base.square(2.7)), color=base.H_COLOR))
        small = Group(diagram, self.put("h", -5.1, .8, size=29, color=base.H_COLOR),
                      self.put(r"\Delta y", -4.2, 1.6, size=29, color=base.CURVE))
        quotient = self.put(r"m=\frac{\Delta y}{\Delta x}=\frac{f(2+h)-4}{h}",
                            -4.1, -.15, size=32, width=4.9)
        current = self.algebra_formula(0)
        self.beat(.10, FadeIn(small), FadeIn(quotient), FadeIn(current),
                  FadeIn(self.put("m=", -.05, ROW_Y[0], size=34, width=1.2)))
        self._chain_rows.append(current)
        self._visibility("chain_row_completed", "quotient_substitution", current)
        self.mark("substitution_ready")
        self.focus_begin("quotient_substitution")
        self.beat(.20)
        self.focus_end("quotient_substitution")
        for index, end, hold, focus in (
            (1, .26, .36, "expanded_terms"),
            (2, .42, .51, "combined_terms"),
            (3, .58, .68, "factored_h"),
        ):
            current = self.move_formula(current, index, end)
            self.mark(base.ALGEBRA[index][0] + "_ready")
            self.focus_begin(focus)
            self.beat(hold)
            self.focus_end(focus)
        condition = self.put(r"h\ne0", -4.1, -1.65, size=40, color=base.H_COLOR)
        explanation = self.label("P、Q 仍是两个不同的点", -4.1, -2.45, size=26,
                                 color=base.MUTED, width=4.9)
        strikes = VGroup(*(Line(current.tag(key).get_corner(base.np.array([-1, -1, 0])),
                                current.tag(key).get_corner(base.np.array([1, 1, 0])),
                                color=base.DERIVATIVE, stroke_width=4)
                            for key in ("h_primary", "h_den")))
        self.beat(.73, FadeIn(condition), FadeIn(explanation), ShowCreation(strikes))
        self.mark("cancellation_condition_ready")
        self.focus_begin("nonzero_cancel")
        self.beat(.83)
        self.focus_end("nonzero_cancel")
        self.move_formula(current, 4, .89)
        self.remove(strikes)
        self.mark("simplified_ready")
        self.focus_begin("simplified_rate")
        self.beat(1)
        self.focus_end("simplified_rate")
        # All complete rows really leave the scene here, closing retained state
        # windows at the runtime event, not at a requested earlier hold boundary.
        self.remove(*(obj for obj in self.mobjects if obj is not self._subtitle_driver))

    def label(self, text, x, y, size=30, color=base.INK, width=12.6):
        if text == "a 附近有定义，双侧极限存在且有限":
            y, size = -2.75, 27
        return super().label(text, x, y, size=size, color=color, width=width)

    def beat(self, fraction, *animations, **kwargs):
        super().beat(fraction, *animations, **kwargs)
        if fraction == 1 and self._cue["id"] == "definition":
            if self._general_comparison is None:
                raise ValueError("The definition needs a completed two-formula comparison")
            for role, obj in zip(("specific", "general"), self._general_comparison):
                if not any(obj is candidate for candidate in self.mobjects):
                    raise ValueError("The complete comparison formula was removed before cue end")
                self._visibility("promotion_" + role + "_visible_at_cue_end", "definition_pattern", obj)
            self._chain_record("comparison_end", stage="general_position")
            self._general_comparison = None

    def _finish_formula_windows(self):
        if self._chain_deferred_ends or self._general_comparison is not None:
            raise ValueError("Retained chain states must close at actual removal")
        report = super()._finish_formula_windows()
        report.update(writer="DerivativeIntroFinalLesson actual scene runtime",
                      status="v005_native_candidate_not_approved", chain_events=self._chain_events)
        report["state_contracts"].append({"state": "stationary algebra rows, deferred ends and chain journal",
            "writer": "v005 actual scene runtime", "consumers": ["native tests", "independent pixel reviewer"],
            "lifecycle": "One construct; rows and retained states end on actual removal",
            "invalidation": "Any source, timing, text, runtime or media change"})
        return report
