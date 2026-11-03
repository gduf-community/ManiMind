"""Explicit affine subtraction; no whole-row glyph morph or retained overlay.

Writer: 01a19f6b-1725-7be3-a4d8-bf988a308b31. Consumers: renderer/native tests
and independent reviewers. Lifetime: this scene/clock; changed mathematical
grouping, source or pixels invalidates evidence. No review authority.
"""

from derivative_ch04_traceable_v007 import DerivativeChainTraceableV007, AUTHOR_AGENT
from derivative_ch04_chain import U_COLOR, X_COLOR
from derivative_chapter_shared import MUTED, RATE
from manimlib import FadeIn, FadeOut, Line, ShowCreation, Transform, VGroup


def remainder(formula, parts):
    occupied = {id(g) for part in parts for g in part.family_members_with_points()}
    return VGroup(*(g for g in formula.family_members_with_points() if id(g) not in occupied))


class DerivativeChainTraceableV008(DerivativeChainTraceableV007):
    def linear_inner(self):
        general = self.semantic(r"y=f(ax+b),\qquad u=ax+b", {"input": ("ax+b", 0), "inner": ("ax+b", 1)},
                                y=2.05, colors={"input": U_COLOR, "inner": U_COLOR})
        self.beat(.16, FadeIn(general))
        self.mark("linear_inner_ready")
        self.focus_begin("linear_input")
        difference = self.semantic(r"\Delta u=[a(x+\Delta x)+b]-(ax+b)",
            {"du": r"\Delta u", "growing": r"a(x+\Delta x)", "fixed": ("b", 0), "old_state": "ax+b"},
            y=.95, size=36)
        self.beat(.31, FadeIn(difference))
        self.focus_begin("linear_increment")
        expanded = self.semantic(r"\Delta u=ax+a\Delta x+b-ax-b",
            {"du": r"\Delta u", "left_ax": ("ax", 0), "increment": r"a\Delta x", "left_b": ("b", 0),
             "right_ax": ("ax", 1), "right_b": ("b", 1)}, y=.95, size=36,
            colors={"increment": U_COLOR, "left_ax": X_COLOR, "right_ax": X_COLOR, "left_b": MUTED, "right_b": MUTED})
        old = [difference.tag(k) for k in ("du", "growing", "fixed", "old_state")]
        destinations = [expanded.tag("du"), VGroup(expanded.tag("left_ax"), expanded.tag("increment")),
                        expanded.tag("left_b"), VGroup(expanded.tag("right_ax"), expanded.tag("right_b"))]
        old_syntax = remainder(difference, old)
        new_syntax = remainder(expanded, destinations)
        self.at(10)
        self.remove(difference)
        self.add(*old, old_syntax)
        self.sample("affine_expand", operation="distribute a and subtract the entire old state")
        self.at(11.2, *(Transform(a, b) for a, b in zip(old, destinations, strict=True)),
                FadeOut(old_syntax), FadeIn(new_syntax))
        self.remove(*old, old_syntax, new_syntax)
        self.add(expanded)

        du, increment = expanded.tag("du"), expanded.tag("increment")
        ax_pair = VGroup(expanded.tag("left_ax"), expanded.tag("right_ax"))
        b_pair = VGroup(expanded.tag("left_b"), expanded.tag("right_b"))
        syntax = remainder(expanded, [du, increment, ax_pair, b_pair])
        self.remove(expanded)
        self.add(du, increment, ax_pair, b_pair, syntax)
        def strikes(parts):
            return VGroup(*(Line(p.get_left()+[0, -.10, 0], p.get_right()+[0, .10, 0],
                                stroke_color=RATE, stroke_width=2.5) for p in parts))
        ax_marks, b_marks = strikes(ax_pair), strikes(b_pair)
        self.at(11.6, ShowCreation(ax_marks))
        self.sample("affine_cancel_pair", pair="ax", reason="ax-ax=0")
        self.at(12, ShowCreation(b_marks))
        self.sample("affine_cancel_pair", pair="b", reason="b-b=0")
        self.at(12.7, FadeOut(ax_pair), FadeOut(b_pair), FadeOut(syntax), FadeOut(ax_marks), FadeOut(b_marks))
        self.remove(ax_pair, b_pair, syntax, ax_marks, b_marks)
        result_increment = self.semantic(r"\Delta u=a\,\Delta x",
            {"du": r"\Delta u", "factor": "a", "dx": r"\Delta x"}, y=.95, size=43,
            colors={"factor": U_COLOR})
        surviving_target = VGroup(result_increment.tag("factor"), result_increment.tag("dx"))
        self.at(14, Transform(du, result_increment.tag("du")), Transform(increment, surviving_target))
        self.remove(du, increment)
        self.add(result_increment)
        self.mark("linear_increment_ready")
        self.at(16.3)
        self.focus_begin("linear_chain")
        result = self.semantic(r"y'=f'(ax+b)\cdot a", {"input": "ax+b", "factor": ("a", 1), "relation": "="},
                               y=-.2, size=47, colors={"input": U_COLOR, "factor": U_COLOR})
        syntax = self.syntax(result, 17, 17.4)
        self.carry(general.tag("inner"), result.tag("input"), 17.4, 20, "affine_whole_input")
        self.carry(result_increment.tag("factor"), result.tag("factor"), 20.3, 23, "affine_rate")
        self.install(result, syntax)
        self.mark("linear_chain_ready")
        self.beat(.7, FadeIn(self.put(r"a=0:\quad u=b,\quad y=f(b)", 0, -1.35, size=39)))
        self.beat(.83, FadeIn(self.label("f(b) 有定义时，这是常数函数，导数为 0", 0, -2.35, size=29)))
        self.mark("zero_linear_constant_ready")
        self.focus_begin("zero_linear_constant")


class DerivativeChainLinearProbeV008(DerivativeChainTraceableV008):
    def construct(self):
        self.motion_samples = []
        self.begin_chapter(self.cues[0])
        self.linear_inner()
        self.end_chapter()
