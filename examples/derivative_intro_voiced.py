"""v004 visual candidate timed against intact V01 takes and verified word estimates.

All added visibility maps and deferred ends belong to one construct. Scene
runtime writes an append-only visibility journal; independent pixel/audio
reviewers consume it. Source, wording, timing or media changes invalidate it.
Full-opacity geometry is a candidate for pixel readability, never its approval.
"""

import sys

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from derivative_intro_audio_aligned import DerivativeIntroAudioAlignedLesson
    import derivative_intro_refined as refined
    from manimlib import Dot, FadeIn, Group, Line, ShowCreation, ValueTracker, linear
    from manimind.experiments.understanding_support import UnderstandingScene
finally:
    sys.argv = _host_argv
del _host_argv


base = refined.base
CUE_DURATIONS = (15, 21, 29, 40, 25, 52, 30, 16)
VOICE_PLAN_SHA256 = "001cb7baf25a28ac95d1cca985c982551794253a5b97bac7ee3e489c15e37270"
TIMINGS_SHA256 = "cbc2f9668c3fe4dd28e73dbfdccfcd8b88da1055cb14308e247fd6c4ad452f5f"
STAGE_TIMES = {
    "opening": {"0.10": 40 / 30, "0.46": 7, "0.60": 7.6},
    "average": {"0.04": .4, "0.08": .8, "0.14": 41 / 30, "0.32": 5.9,
                "0.38": 6.2, "0.44": 6.5, "0.64": 10.5, "0.74": 11.2},
    "approach": {"0.04": .4, "0.08": .9, "0.12": 1.5, "0.24": 7.5,
                 "0.52": 16.8, "0.58": 18, "0.80": 580 / 30},
    "algebra": {"0.04": .3, "0.08": .8, "0.10": 40 / 30, "0.20": 4.5,
                "0.26": 7.9, "0.36": 12.8, "0.42": 14.6, "0.51": 17.1,
                "0.58": 19.9, "0.68": 21.9, "0.73": 22.5, "0.83": 26.8, "0.89": 29.2},
    "both_sides": {"0.04": .4, "0.08": .9, "0.12": 44 / 30, "0.34": 6.6,
                   "0.55": 10.3, "reason_motion_start": 12.8, "0.78": 13.25, "0.72": 17.8},
    "definition": {"0.04": .4, "0.08": .95, "0.12": 1.3, "0.18": 3.7,
                   "0.30": 8.7, "0.36": 9.2, "0.54": 15.6, "0.58": 17.15,
                   "0.62": 22.5, "0.66": 23.1, "0.68": 23.5, "0.72": 24,
                   "0.80": 35.2, "0.88": 36.6, "0.90": 37.1},
    "tangent_prediction": {"0.04": .4, "0.08": .9, "0.12": 38 / 30, "0.32": 7.9,
                           "0.42": 8.95, "motion_start": 15.3, "0.72": 16.25,
                           "0.78": 19.85, "0.80": 20.55},
    "closing": {"0.04": .4, "0.08": .85, "0.14": 1.3, "0.53": 6.6, "0.62": 7.2},
}
PROCESS_TAILS = {"right_approach": 20.6, "nonzero_neighborhood": 16.6}
HISTORY_FOCI = {"quotient_substitution", "expanded_terms", "nonzero_cancel"}


class DerivativeIntroVoicedLesson(DerivativeIntroAudioAlignedLesson):
    def _initialize_formula_windows(self):
        super()._initialize_formula_windows()
        self._formula_objects = {}
        self._deferred_visibility_ends = set()
        self._early_state_windows = set()
        self._assembly_pair = None
        self._visibility_events = []
        self._tangent_line = None
        self._origin_rate_record = None

    def stage_time(self, fraction):
        key = f"{fraction:.2f}" if isinstance(fraction, (int, float)) else fraction
        offset = self._cue["duration"] if fraction == 1 else self._cue.get("stage_times", {}).get(
            key, STAGE_TIMES[self._cue["id"]][key])
        if not 0 <= offset <= self._cue["duration"]:
            raise ValueError("Measured-audio stage must stay inside the actual cue")
        return self._cue["start"] + offset

    def _visibility(self, phase, focus, obj):
        glyphs = obj.family_members_with_points()
        if not glyphs:
            raise ValueError("A visibility event needs actual object geometry")
        opacities = [float(glyph.get_opacity()) for glyph in glyphs]
        if min(opacities) < .999:
            raise ValueError("A partial-opacity formula cannot open a state window")
        self._visibility_events.append({"phase": phase, "focus": focus,
            "time": float(self.get_time()), "cue": self._cue["id"],
            "bounds": obj.get_bounding_box().tolist(), "minimum_opacity": min(opacities),
            "latex": obj.get_tex()})

    def algebra_formula(self, index):
        result = super().algebra_formula(index)
        if index == 0:
            self._formula_objects["quotient_substitution"] = result
        return result

    def readable_matching(self, source, target, end, stage):
        if self._assembly_pair is not None:
            raise ValueError("Nested visible formula assembly is not supported")
        focus = self._formula_stage_to_focus[stage]
        self._formula_objects[focus] = target
        self._assembly_pair = (source, target, focus)
        result = super().readable_matching(source, target, end, stage)
        self._assembly_pair = None
        return result

    def remove(self, *objects):
        pair = getattr(self, "_assembly_pair", None)
        if pair is not None and any(obj is pair[0] for obj in objects):
            _, target, focus = pair
            self._visibility("target_fully_assembled_before_home", focus, target)
            if self._formula_window_states[focus]["intent"].mode == "state":
                UnderstandingScene.focus_begin(self, focus)
                self._early_state_windows.add(focus)
            for identity in tuple(self._deferred_visibility_ends):
                if self._formula_objects.get(identity) is pair[0]:
                    self._visibility("history_removed", identity, pair[0])
                    super().focus_end(identity)
                    self._deferred_visibility_ends.remove(identity)
        return super().remove(*objects)

    def focus_begin(self, identity):
        if identity == "nonzero_cancel":
            self._formula_objects[identity] = self._formula_objects["factored_h"]
        if identity in self._early_state_windows:
            state = self._formula_window_states[identity]
            if state["status"] != "completed" or not state["ready_seen"] or state["base_focus_claimed"]:
                raise ValueError("Settled-state handoff must follow actual completion and ready")
            state["base_focus_claimed"] = True
            self._record_formula_window(state, "settled_state_available")
            self._early_state_windows.remove(identity)
            return
        super().focus_begin(identity)

    def focus_end(self, identity):
        if identity in HISTORY_FOCI or identity == "tangent_geometry":
            if identity not in self._open_focus or identity in self._deferred_visibility_ends:
                raise ValueError("A lifecycle end must be requested exactly once for an open focus")
            self._deferred_visibility_ends.add(identity)
            return
        if identity in PROCESS_TAILS:
            self.until(self._cue["start"] + PROCESS_TAILS[identity])
        super().focus_end(identity)

    def beat(self, fraction, *animations, **kwargs):
        if self._cue["id"] == "tangent_prediction" and fraction == .72:
            self.until(self.stage_time("motion_start"))
        super().beat(fraction, *animations, **kwargs)
        if fraction == 1 and "tangent_geometry" in self._deferred_visibility_ends:
            if self._tangent_line is None or float(self._tangent_line.get_stroke_opacity()) < .999:
                raise ValueError("Tangent geometry must remain visible until its measured end")
            self._visibility_events.append({"phase": "tangent_visible_at_cue_end",
                "focus": "tangent_geometry", "time": float(self.get_time()),
                "bounds": self._tangent_line.get_bounding_box().tolist()})
            super().focus_end("tangent_geometry")
            self._deferred_visibility_ends.remove("tangent_geometry")
        if fraction == 1 and self._cue["id"] == "approach":
            if self._origin_rate_record is None:
                raise ValueError("Keep the explicit initial-rate record through the approach")
            self._visibility_events.append({"phase": "origin_rate_record_visible_at_cue_end",
                "time": float(self.get_time()), "value": 5.,
                "bounds": self._origin_rate_record.get_bounding_box().tolist()})

    def mark(self, event_id):
        if event_id == "tangent_ready":
            lines = [obj for obj in self.mobjects if isinstance(obj, Line)]
            if len(lines) != 1:
                raise ValueError("The actual tangent must be uniquely identifiable")
            self._tangent_line = lines[0]
        if event_id == "approach_setup_ready":
            self._origin_rate_record = self.label("起始斜率 5.00", 3.8, -2.65,
                                                  size=27, color=base.MUTED, width=5.1)
            self.add(self._origin_rate_record)
            self._visibility_events.append({"phase": "origin_rate_record_added",
                "time": float(self.get_time()), "value": 5.,
                "presentation": "historical_start_value_not_current_readout",
                "bounds": self._origin_rate_record.get_bounding_box().tolist()})
        super().mark(event_id)

    def both_sides(self, cue):
        self.begin_chapter(cue)
        radius = ValueTracker(.8)
        qr = Dot(base.plot_point(2.8, base.square(2.8)), color=base.H_COLOR, radius=.075)
        ql = Dot(base.plot_point(1.2, base.square(1.2)), color=base.H_COLOR, radius=.075)
        sr, sl = self.secant_line(.8), self.secant_line(-.8)
        columns = (1.9, 3.75, 5.65)
        headings = Group(*(self.put(tex, x, 1.35, size=33, color=color, width=1.3)
                           for tex, x, color in zip(("h", r"\Delta y", "m"), columns,
                                                    (base.H_COLOR, base.CURVE, base.INK))))
        rows, values = Group(), []
        for sign, y in ((1, .5), (-1, -.5)):
            row = [self.number(value, size=34, decimals=2, color=color).move_to([x, y, 0])
                   for value, x, color in zip((sign * .8, base.increments(sign * .8)[1],
                                               base.difference_quotient(sign * .8)), columns,
                                              (base.H_COLOR, base.CURVE, base.INK))]
            values.append(row)
            rows.add(*row)
        self.beat(.12, FadeIn(self.graph()), FadeIn(qr), FadeIn(ql), ShowCreation(sr), ShowCreation(sl),
                  FadeIn(headings), FadeIn(rows), FadeIn(self.put("m(h)=4+h", 3.8, 2.3, size=41)))
        self.mark("two_sides_ready")
        self.focus_begin("two_sided_start")
        self.beat(.34)
        self.focus_end("two_sided_start")
        driver = Group()

        def update(_):
            r = radius.get_value()
            for sign, point, secant, row in ((1, qr, sr, values[0]), (-1, ql, sl, values[1])):
                h = sign * r
                point.move_to(base.plot_point(2 + h, base.square(2 + h)))
                secant.become(self.secant_line(h))
                for number, value in zip(row, (h, base.increments(h)[1], base.difference_quotient(h))):
                    number.set_value(value)
            self.sample("two_sides", radius=r, right=base.two_sided_rates(r)[0], left=base.two_sided_rates(r)[1],
                        right_dy=base.increments(r)[1], left_dy=base.increments(-r)[1],
                        qr=qr.get_center().tolist(), ql=ql.get_center().tolist())

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("two_sided_motion")
        self.beat(.55, radius.animate.set_value(.1), rate_func=linear)
        self.mark("two_sides_mid")
        self.beat("reason_motion_start", radius.animate.set_value(.06), rate_func=linear)
        self.focus_end("two_sided_motion")
        self.beat(.78, radius.animate.set_value(.055),
                  FadeIn(self.put(r"h\to0\quad\Longrightarrow\quad4+h\to4", 3.8, -1.65,
                                  size=36, color=base.DERIVATIVE)),
                  FadeIn(self.put(r"|m(h)-4|=|h|", 3.8, -2.6, size=34)), rate_func=linear)
        self.mark("common_limit_ready")
        self.focus_begin("common_four")
        self.beat(.72, radius.animate.set_value(.02), rate_func=linear)
        self.mark("two_sides_near")
        self.beat(1)
        self.focus_end("common_four")
        driver.clear_updaters()

    def _finish_formula_windows(self):
        if self._deferred_visibility_ends or self._early_state_windows or self._assembly_pair is not None:
            raise ValueError("Every actual visibility lifecycle must be closed")
        report = super()._finish_formula_windows()
        report.update(status="measured_audio_visual_candidate_not_approved",
                      audio_measurements={"voice_plan_sha256": VOICE_PLAN_SHA256, "timings_sha256": TIMINGS_SHA256},
                      audio_schedule="requires current native and production placement verification",
                      visibility_events=self._visibility_events)
        report["state_contracts"].append({"state": "formula identity maps, early complete-state windows and deferred ends",
            "writer": "v004 actual scene runtime", "consumers": ["independent pixel reviewer", "audio aligner"],
            "lifecycle": "This construct only; close on actual removal or visible cue end",
            "invalidation": "Source, stage times, object opacity, text, runtime or media change"})
        return report
