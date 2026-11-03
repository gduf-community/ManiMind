"""Chapter 04: two successive one-variable changes, on a native visual clock.

Trackers and referents belong to this construct; ChapterScene journals actual
frames. Source, cue, geometry or wording changes invalidate those observations.
Pure functions below are also the source for the versioned mathematics tests.
"""

import math
from numbers import Real

import numpy as np
from manimlib import Arrow, Dot, FadeIn, FadeOut, Group, Line, ValueTracker, linear

from derivative_chapter_shared import ChapterScene, INK, MUTED, CURVE, RATE, ACCENT
from manimind.components.formula_motion import SemanticFormula


AUTHOR_AGENT = "01a199e9-73ab-7700-8a9f-cd7b5541b0ad"
CUE_IDS = ("opening", "two-stages", "one-change", "ratios", "rule", "linear-inner", "practice", "handoff")
CUE_DURATIONS = (24, 42, 54, 52, 50, 36, 46, 32)
X_COLOR, U_COLOR, Y_COLOR = ACCENT, CURVE, RATE


def finite_real(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("Expected a real number")
    if not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def inner(x):
    return finite_real(x) ** 2 + 1


def outer(u):
    return finite_real(u) ** 3


def composite(x):
    return outer(inner(x))


def chain_state(x):
    x = finite_real(x)
    u = inner(x)
    return {"x": x, "u": u, "y": outer(u), "inner_rate": 2*x,
            "outer_rate": 3*u*u, "total_rate": 6*x*u*u}


def chain_increments(x, h):
    x, h = finite_real(x), finite_real(h)
    du = inner(x+h) - inner(x)
    return {"dx": h, "du": du, "dy": composite(x+h)-composite(x)}


def chain_ratios(x, h):
    values = chain_increments(x, h)
    if values["dx"] == 0 or values["du"] == 0:
        raise ValueError("Ratio factorization requires dx != 0 and du != 0")
    return {"inner_ratio": values["du"]/h, "outer_ratio": values["dy"]/values["du"],
            "total_ratio": values["dy"]/h}


def affine_fourth(x):
    return (3*finite_real(x)-1) ** 4


def affine_fourth_derivative(x):
    return 12*(3*finite_real(x)-1) ** 3


def affine_input(x, a, b):
    return finite_real(a)*finite_real(x)+finite_real(b)


def affine_increment(h, a):
    return finite_real(a)*finite_real(h)


def affine_cube_derivative(x, a, b):
    a = finite_real(a)
    u = affine_input(x, a, b)
    return 0 if a == 0 else 3*a*u*u


class DerivativeChainLesson(ChapterScene):
    def semantic(self, latex, tokens, x=0, y=0, size=44, colors=None, width=11.8):
        result = SemanticFormula(latex, tokens=tokens, colors=colors, font_size=size)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def construct(self):
        self.motion_samples = []
        methods = (self.opening, self.two_stages, self.one_change, self.ratios,
                   self.rule, self.linear_inner, self.practice, self.handoff)
        if tuple(c["id"] for c in self.cues) != CUE_IDS:
            raise ValueError("Chapter 04 cue order changed")
        for cue, duration, method in zip(self.cues, CUE_DURATIONS, methods, strict=True):
            if cue["duration"] != duration:
                raise ValueError("Re-author timing before changing a cue duration")
            self.begin_chapter(cue)
            method()
            self.end_chapter()

    def opening(self):
        title = self.label("链式法则", 0, 1.65, size=60)
        expression = self.semantic(r"y=(x^2+1)^3", {"inside": "x^2+1"}, y=.2,
                                   colors={"inside": U_COLOR})
        self.beat(.15, FadeIn(title), FadeIn(expression))
        self.mark("chain_title_ready")
        self.focus_begin("chain_opening")
        self.beat(.55)
        self.beat(.68, FadeIn(self.label("平方加一，再把结果立方", 0, -1.1, size=34)))
        self.mark("chain_question_ready")

    def two_stages(self):
        original = self.semantic(r"y=(x^2+1)^3", {"inside": "x^2+1"}, y=2.1,
                                 colors={"inside": U_COLOR})
        self.beat(.12, FadeIn(original))
        self.focus_begin("compound_expression")
        token = original.tag("inside").copy()
        self.add(token)
        self.beat(.24, token.animate.move_to([-3.4, .9, 0]))
        self.beat(.28, FadeOut(token))
        first = self.semantic(r"u=x^2+1", {"u": "u", "x": "x"}, x=-3.4, y=.9,
                              colors={"u": U_COLOR, "x": X_COLOR})
        self.beat(.34, FadeIn(first))
        self.mark("chain_inner_named")
        self.focus_begin("inner_named")
        second = self.semantic(r"y=u^3", {"y": "y", "u": "u"}, x=3.4, y=.9,
                               colors={"y": Y_COLOR, "u": U_COLOR})
        arrow = Arrow([-1.5, .9, 0], [1.6, .9, 0], buff=.1, stroke_color=U_COLOR)
        self.beat(.48, FadeIn(arrow), FadeIn(second))
        self.mark("chain_two_levels_ready")
        self.focus_begin("two_levels")
        values = Group(self.put("x=1", -4.2, -.7, color=X_COLOR),
                       self.put("u=2", 0, -.7, color=U_COLOR),
                       self.put("y=8", 4.2, -.7, color=Y_COLOR),
                       Arrow([-3.1, -.7, 0], [-1, -.7, 0], buff=.1),
                       Arrow([1, -.7, 0], [3.1, -.7, 0], buff=.1))
        self.beat(.66, FadeIn(values))
        self.mark("chain_base_values_ready")
        self.focus_begin("base_values")
        self.beat(.9, FadeIn(self.label("u：前一步的输出，后一步的输入", 0, -2.1, color=U_COLOR)))

    def one_change(self):
        x, u, y = ValueTracker(1), ValueTracker(2), ValueTracker(8)
        trackers, positions, colors = (x, u, y), (-4.2, 0, 4.2), (X_COLOR, U_COLOR, Y_COLOR)
        numbers = [self.number(t.get_value(), size=40, color=color, decimals=3).move_to([p, .55, 0])
                   for t, p, color in zip(trackers, positions, colors)]
        group = Group(*(self.put(name, p, 1.5, color=color) for name, p, color in
                        zip(("x", "u=x^2+1", "y=u^3"), positions, colors)), *numbers,
                      Arrow([-3, .55, 0], [-1.2, .55, 0], buff=.1),
                      Arrow([1.2, .55, 0], [3, .55, 0], buff=.1))
        self.beat(.12, FadeIn(group))
        self.mark("change_base_ready")
        phase = {"name": "input"}
        driver = Group()

        def update(_):
            for number, tracker in zip(numbers, trackers):
                number.set_value(tracker.get_value())
            self.sample("chain_transfer", phase=phase["name"], x=float(x.get_value()),
                        u=float(u.get_value()), y=float(y.get_value()))

        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("input_change")
        self.beat(.28, x.animate.set_value(1.1), rate_func=linear)
        self.focus_end("input_change")
        self.mark("input_change_complete")
        self.beat(.34, FadeIn(self.put(r"\Delta x=0.1", -4.2, -.45, size=32, color=X_COLOR)))
        phase["name"] = "inner"
        self.focus_begin("inner_change")
        self.beat(.51, u.animate.set_value(inner(1.1)), rate_func=linear)
        self.focus_end("inner_change")
        self.mark("inner_change_complete")
        self.beat(.57, FadeIn(self.put(r"\Delta u=0.21", 0, -.45, size=32, color=U_COLOR)))
        phase["name"] = "outer"
        self.focus_begin("outer_change")
        self.beat(.74, y.animate.set_value(composite(1.1)), rate_func=linear)
        self.focus_end("outer_change")
        self.mark("outer_change_complete")
        driver.clear_updaters()
        self.beat(.8, FadeIn(self.put(r"\Delta y=2.793861", 4.2, -.45, size=30, color=Y_COLOR)))
        self.beat(.86, FadeIn(self.label("同一次输入改变，经过两级传到输出", 0, -1.6, size=32)))
        self.focus_begin("transfer_complete")
        self.mark("chain_transfer_ready")

    def ratios(self):
        identity = self.semantic(r"\frac{\Delta y}{\Delta x}=\frac{\Delta y}{\Delta u}\cdot\frac{\Delta u}{\Delta x}",
                                 {"outer": r"\frac{\Delta y}{\Delta u}",
                                  "inner": r"\frac{\Delta u}{\Delta x}"}, y=1.9,
                                 colors={"outer": Y_COLOR, "inner": U_COLOR})
        self.beat(.14, FadeIn(identity), FadeIn(self.put(r"x=1,\quad 0<|h|<1,\quad \Delta x=h", 0, 2.7, size=30)))
        self.mark("ratio_identity_ready")
        self.focus_begin("ratio_identity")
        condition = self.put(r"\Delta u=(1+h)^2-1=h(2+h)\ne0", 0, .75, size=37, color=U_COLOR)
        self.beat(.3, FadeIn(condition))
        self.mark("ratio_nonzero_ready")
        self.focus_begin("nonzero_increment")
        labels = Group(self.label("输入增量 h", -4.8, -.15, size=24),
                       self.label("内层比值", -1.6, -.15, size=24, color=U_COLOR),
                       self.label("外层比值", 1.6, -.15, size=24, color=Y_COLOR),
                       self.label("总比值", 4.8, -.15, size=24))
        self.beat(.38, FadeIn(labels))
        for index, h in enumerate((.1, .01, .001)):
            rates = chain_ratios(1, h)
            row = Group(*(self.number(v, size=29, decimals=5).move_to([p, -.75-index*.58, 0])
                          for p, v in zip((-4.8, -1.6, 1.6, 4.8),
                                          (h, rates["inner_ratio"], rates["outer_ratio"], rates["total_ratio"]))))
            self.beat(.48+index*.15, FadeIn(row))
            self.mark(f"ratio_row_{index+1}_ready")
            self.sample("ratio_row", h=h, **rates)
        self.focus_begin("ratio_limit")
        self.beat(.9, FadeIn(self.put(r"2\times12=24", 0, -2.65, color=ACCENT)))
        self.mark("ratio_limit_ready")

    def rule(self):
        general = self.semantic(r"u=g(x),\qquad y=f(u)", {"inner": "g(x)", "outer": "f(u)"}, y=2.35,
                                colors={"inner": U_COLOR, "outer": Y_COLOR})
        self.beat(.14, FadeIn(general))
        self.beat(.25, FadeIn(self.label("内层在 x 处可导，外层在 u=g(x) 处可导", 0, 1.45, size=30)))
        self.mark("chain_conditions_ready")
        self.focus_begin("chain_conditions")
        rule = self.semantic(r"y'=f'(u)\,g'(x)", {"outer_rate": "f'(u)", "inner_rate": "g'(x)"}, y=.4,
                             colors={"outer_rate": Y_COLOR, "inner_rate": U_COLOR})
        self.beat(.4, FadeIn(rule))
        self.mark("chain_rule_ready")
        self.focus_begin("chain_rule")
        local = self.put(r"\Delta u=2h+h^2,\quad\Delta y=12\Delta u+6(\Delta u)^2+(\Delta u)^3", 0, -.7, size=29)
        self.beat(.56, FadeIn(local))
        self.mark("chain_remainders_ready")
        self.focus_begin("small_change_reason")
        self.beat(.69, FadeIn(self.label("输入越来越小，高次项除以 h 后也趋于零", 0, -1.45, size=28)))
        self.beat(.82, FadeIn(self.put(r"y'=3(x^2+1)^2\cdot2x,\qquad y'(1)=24", 0, -2.2, size=37)))
        self.mark("chain_example_derivative_ready")
        self.focus_begin("chain_example_result")

    def linear_inner(self):
        general = self.semantic(r"y=f(ax+b),\qquad u=ax+b", {"input": ("ax+b", 0), "inner": ("ax+b", 1)},
                                y=2.05, colors={"input": U_COLOR, "inner": U_COLOR})
        self.beat(.16, FadeIn(general))
        self.mark("linear_inner_ready")
        self.focus_begin("linear_input")
        self.beat(.31, FadeIn(self.put(r"\Delta u=a\,\Delta x", 0, .95, size=47, color=U_COLOR)))
        self.mark("linear_increment_ready")
        self.focus_begin("linear_increment")
        self.beat(.49, FadeIn(self.put(r"y'=f'(ax+b)\cdot a", 0, -.2, size=47)))
        self.mark("linear_chain_ready")
        self.focus_begin("linear_chain")
        self.beat(.7, FadeIn(self.put(r"a=0:\quad u=b,\quad y=f(b)", 0, -1.35, size=39)))
        self.beat(.83, FadeIn(self.label("f(b) 有定义时，这是常数函数，导数为 0", 0, -2.35, size=29)))
        self.mark("zero_linear_constant_ready")
        self.focus_begin("zero_linear_constant")

    def practice(self):
        original = self.semantic(r"y=(3x-1)^4", {"inside": "3x-1"}, y=2.2,
                                 colors={"inside": U_COLOR})
        self.beat(.13, FadeIn(original))
        self.mark("affine_composite_ready")
        self.focus_begin("affine_question")
        first = self.put(r"u=3x-1,\quad u'=3", -2.9, .95, size=39, color=U_COLOR, width=5.4)
        second = self.put(r"y=u^4,\quad f'(u)=4u^3", 3, .95, size=39, color=Y_COLOR, width=5.4)
        self.beat(.36, FadeIn(first))
        self.mark("affine_inner_ready")
        self.focus_begin("affine_inner")
        self.beat(.51, FadeIn(second))
        self.mark("affine_outer_ready")
        self.focus_begin("affine_outer")
        self.beat(.69, FadeIn(self.put(r"y'=4(3x-1)^3\cdot3=12(3x-1)^3", 0, -.3, size=43)))
        self.mark("affine_product_ready")
        self.focus_begin("affine_product")
        self.beat(.82, FadeIn(self.label("这两个多项式复合，对所有实数 x 都可导", 0, -1.45, size=30)))
        self.beat(.9, FadeIn(self.label("外层的输入是整个 3x-1，内层变化率是 3", 0, -2.2, size=29)))

    def handoff(self):
        self.beat(.15, FadeIn(self.put(r"x\longrightarrow u\longrightarrow y", 0, 1.8, size=53)))
        self.beat(.3, FadeIn(self.put(r"y'=f'(u)u'", 0, .65, size=54)))
        self.mark("chain_summary_ready")
        self.focus_begin("chain_summary")
        self.beat(.58, FadeIn(self.label("两级变化率相乘，得到对原输入的变化率", 0, -.6, size=32)))
        self.beat(.77, FadeIn(self.label("导数算出来后，怎样看出函数在哪一段增长？", 0, -1.8, size=32)))
        self.mark("chain_handoff_ready")
        self.focus_begin("chain_to_monotonicity")
