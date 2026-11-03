"""Local v002 revision of the frozen derivative introduction, not a new engine."""

import sys

_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    import derivative_intro_visual as base
    from manimlib import FadeIn, FadeOut, Group, UpdateFromAlphaFunc, ValueTracker, VGroup, linear
    from manimind.components.formula_motion import SemanticFormula, matching_transform
finally:
    sys.argv = _host_argv
del _host_argv


CUE_DURATIONS = (22, 34, 42, 74, 36, 68, 44, 18)
DEFINITION_STAGES = {
    "0.04": 1.36, "0.08": 2.72, "0.12": 4.76, "0.18": 7.48,
    "0.30": 14.96, "0.36": 16.32, "0.54": 25.84, "0.58": 28.56,
    "0.62": 34, "0.66": 35.36, "0.68": 36.72, "0.72": 38.08,
    "0.80": 51, "0.88": 54.4, "0.90": 55,
}
SPECIFIC_DEFINITION = (
    r"f'(2)=\lim_{h\to0}\frac{f(2+h)-f(2)}{h}=4",
    {"position": ("2", 0), "position_q": ("2", 1), "position_p": ("2", 2),
     "h_limit": ("h", 0), "h_num": ("h", 1), "h_den": ("h", 2)},
)
GENERAL_DEFINITION = (
    r"f'(a)=\lim_{h\to0}\frac{f(a+h)-f(a)}{h}",
    {"position": ("a", 0), "position_q": ("a", 1), "position_p": ("a", 2),
     "h_limit": ("h", 0), "h_num": ("h", 1), "h_den": ("h", 2)},
)


def raw_quotient_components(h, at=2):
    base.finite_real(h)
    base.finite_real(at)
    return base.square(at + h) - base.square(at), h


def bounds(obj):
    return [float(obj.get_left()[0]), float(obj.get_right()[0]),
            float(obj.get_bottom()[1]), float(obj.get_top()[1])]


class DerivativeIntroRefinedLesson(base.DerivativeIntroLesson):
    def stage_time(self, fraction):
        key = f"{fraction:.2f}"
        if (self._cue["id"] == "definition" and fraction != 1
                and key not in self._cue.get("stage_times", {})):
            return self._cue["start"] + DEFINITION_STAGES[key]
        return super().stage_time(fraction)

    @staticmethod
    def syntax_parts(formula, identities):
        matched = {id(glyph) for key in identities
                   for glyph in formula.tag(key).family_members_with_points()}
        return VGroup(*(glyph for glyph in formula.family_members_with_points() if id(glyph) not in matched))

    def readable_matching(self, source, target, end, stage):
        """Keep a readable history row while tokens assemble the separate next row."""
        start = float(self.get_time())
        finish = self.stage_time(end)
        fps = self.camera.fps
        frames = round(finish * fps) - round(start * fps)
        if frames < 12:
            raise ValueError("A staged semantic transition needs at least twelve frames")
        boundaries = [round(start * fps) + round(frames * part) for part in (.18, .65, .82, 1)]
        home = source.get_center().copy()
        self.until(boundaries[0] / fps, source.animate.move_to([0, .35, 0]))
        history = bounds(source)
        target.move_to([0, -1.55, 0])
        common = tuple(key for key in source.semantic_ids if key in target.semantic_ids)
        traveling = source.copy()
        old_syntax = self.syntax_parts(traveling, common)
        new_syntax = self.syntax_parts(target, common)
        old_syntax.set_opacity(0)
        new_syntax.set_opacity(0)
        driver = Group()

        def track(_):
            visible = []
            for key in common:
                token = traveling.tag(key)
                box = bounds(token)
                # Copied tokens become visible only after leaving the readable row.
                separated = box[3] < history[2] - .06
                token.set_opacity(1 if separated else 0)
                visible.append({"id": key, "bounds": box, "visible": separated})
            self.sample("refined_formula", stage=stage, phase="tokens", history=history,
                        target=bounds(target), visible_tokens=visible,
                        syntax_opacity=float(new_syntax.get_opacity()))

        self.add(traveling, driver)
        driver.add_updater(track)
        track(driver)
        duration = (boundaries[1] - boundaries[0]) / fps
        self.until(boundaries[1] / fps, matching_transform(
            traveling, target, run_time=duration, path_arc=0, unmatched_in_place=True))
        driver.clear_updaters()
        self.remove(driver)

        def reveal(_, alpha):
            new_syntax.set_opacity(alpha)
            self.sample("refined_formula", stage=stage, phase="syntax", history=history,
                        target=bounds(target), syntax_opacity=float(alpha))

        self.until(boundaries[2] / fps, UpdateFromAlphaFunc(target, reveal))
        self.remove(source)
        self.until(boundaries[3] / fps, target.animate.move_to(home))
        self.symbol_transitions.append({"stage": stage, "start": start,
                                        "end": float(self.get_time()), "source": source.get_tex(),
                                        "target": target.get_tex(),
                                        "strategy": "readable_history_then_tokens_then_syntax",
                                        "history_bounds": history, "assembly_center_y": -1.55,
                                        "phase_ends": [value / fps for value in boundaries]})
        return target

    def move_formula(self, current, index, end):
        return self.readable_matching(current, self.algebra_formula(index), end, base.ALGEBRA[index][0])

    def definition(self, cue):
        self.begin_chapter(cue)
        raw = self.put(r"m(h)=\frac{(2+h)^2-4}{h}", -3.5, 1.65, size=42, width=5.8)
        self.beat(.12, FadeIn(raw),
                  FadeIn(self.label("原差商", -3.5, 2.55, size=29, color=base.MUTED)))
        self.mark("raw_difference_quotient_ready")
        self.focus_begin("raw_zero_input")
        self.beat(.18, FadeIn(self.put(r"h=0:\quad\frac{(2+0)^2-4}{0}=\frac{0}{0}",
                                     -3.5, .15, size=40, width=5.9)),
                  FadeIn(self.label("原差商在 h = 0 处无定义", -3.5, -1.1, size=29, width=5.9)))
        self.focus_end("raw_zero_input")
        self.mark("zero_input_undefined_ready")
        self.focus_begin("zero_undefined")
        self.beat(.30)
        self.focus_end("zero_undefined")
        radius = ValueTracker(.1)
        cells = []
        table = Group()
        for sign, y in ((1, .25), (-1, -.6)):
            row = [self.number(value, size=35, decimals=2, color=color).move_to([x, y, 0])
                   for value, color, x in ((sign * .1, base.H_COLOR, 2.8),
                                           (base.difference_quotient(sign * .1), base.INK, 5.1))]
            cells.append(row)
            table.add(*row)
        self.beat(.36, FadeIn(self.put(r"h\ne0:\quad m(h)=4+h", 3.6, 1.75, size=38, width=5.8)),
                  FadeIn(self.put("h", 2.8, 1, size=31, color=base.H_COLOR)),
                  FadeIn(self.put("m(h)", 5.1, 1, size=31)), FadeIn(table))
        self.mark("nearby_nonzero_ready")
        driver = Group()

        def update(_):
            r = radius.get_value()
            for sign, row in zip((1, -1), cells):
                row[0].set_value(sign * r)
                row[1].set_value(base.difference_quotient(sign * r))
            self.sample("zero_bridge", radius=r, raw_numerator=0, raw_denominator=0,
                        right=base.difference_quotient(r), left=base.difference_quotient(-r))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("nonzero_neighborhood")
        self.beat(.54, radius.animate.set_value(.01), rate_func=linear)
        self.mark("nonzero_near_limit")
        self.focus_end("nonzero_neighborhood")
        driver.clear_updaters()
        self.beat(.58, FadeIn(self.put(r"\lim_{h\to0}m(h)=4", 3.6, -1.75,
                                     size=43, color=base.DERIVATIVE, width=5.8)),
                  FadeIn(self.label("非零输入的共同趋近值", 3.6, -2.6, size=28, width=5.8)))
        self.mark("zero_limit_comparison_ready")
        self.focus_begin("zero_value_vs_limit")
        self.beat(.62)
        self.focus_end("zero_value_vs_limit")
        objects = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        self.beat(.66, *(FadeOut(obj) for obj in objects))
        self.beat(.68, FadeIn(self.label("把这个极限叫作导数", 0, 3.35, size=39)))
        height = self.put(r"f(2)=4", -4.5, 1.95, size=35)
        value = self.label("函数值：P 的纵坐标", -.4, 1.95, size=29, color=base.MUTED)
        rate = self.label("本点变化率", 0, -1.15, size=31, color=base.DERIVATIVE)
        specific = SemanticFormula(SPECIFIC_DEFINITION[0], tokens=SPECIFIC_DEFINITION[1], font_size=49)
        specific.move_to([0, .25, 0])
        self.beat(.72, FadeIn(height), FadeIn(value), FadeIn(specific), FadeIn(rate))
        self.mark("derivative_value_ready")
        self.focus_begin("derivative_at_two")
        self.beat(.80)
        self.focus_end("derivative_at_two")
        self.remove(height, value, rate)
        general = SemanticFormula(GENERAL_DEFINITION[0], tokens=GENERAL_DEFINITION[1], font_size=49)
        self.readable_matching(specific, general, .88, "general_position")
        condition = self.label("a 附近有定义，双侧极限存在且有限", 0, -2.3, size=29, color=base.MUTED)
        self.beat(.90, FadeIn(condition))
        self.mark("definition_pattern_ready")
        self.focus_begin("definition_pattern")
        self.beat(1)
        self.focus_end("definition_pattern")
