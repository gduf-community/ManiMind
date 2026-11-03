"""Chapter 05: a common x drives function height, tangent and derivative height.

The construct owns each tracker/driver; its samples expire with any source,
mapping, timing or text change. There is no acoustic or review state here.
"""

import math
from numbers import Real

import numpy as np
from manimlib import Dot, FadeIn, FadeOut, Group, Line, ShowCreation, ValueTracker, VMobject, VGroup, linear

from derivative_chapter_shared import ChapterScene, INK, MUTED, CURVE, RATE, ACCENT
from manimind.components.formula_motion import SemanticFormula


AUTHOR_AGENT = "01a199e9-73ab-7700-8a9f-cd7b5541b0ad"
CUE_IDS = ("opening", "same-x", "sweep", "signs", "interval", "zero-point", "handoff")
CUE_DURATIONS = (24, 42, 70, 42, 66, 50, 30)


def finite_real(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("Expected a real number")
    if not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def function(x):
    x = finite_real(x)
    return x**3-3*x


def derivative(x):
    x = finite_real(x)
    return 3*(x*x-1)


def derivative_sign(x):
    value = derivative(x)
    return int(value > 0)-int(value < 0)


def plot_point(x, value, derivative_plot=False):
    x, value = finite_real(x), finite_real(value)
    return (-.8+2*x, (-1.35+.14*value) if derivative_plot else (1.65+.30*value), 0.)


def linked_state(x):
    x = finite_real(x)
    f, df = function(x), derivative(x)
    return {"x": x, "f": f, "df": df, "sign": derivative_sign(x),
            "curve_point": plot_point(x, f), "derivative_point": plot_point(x, df, True)}


def tangent_endpoints(x):
    x = finite_real(x)
    left, right = max(-2.05, x-.35), min(2.05, x+.35)
    return (plot_point(left, function(x)+derivative(x)*(left-x)),
            plot_point(right, function(x)+derivative(x)*(right-x)))


def cube(x):
    return finite_real(x)**3


def cube_derivative(x):
    return 3*finite_real(x)**2


def cube_difference(a, b):
    a, b = finite_real(a), finite_real(b)
    if not a < b:
        raise ValueError("Choose a < b")
    return (b-a)*(a*a+a*b+b*b)


def secant_witness(a, b):
    a, b = finite_real(a), finite_real(b)
    if not a < b < -1:
        raise ValueError("Witness example requires a < b < -1")
    slope = (function(b)-function(a))/(b-a)
    return -math.sqrt((slope+3)/3)


def polyline(points, color=CURVE):
    return VMobject().set_points_as_corners(points).set_stroke(color, 3.5)


class DerivativeMonotonicityLesson(ChapterScene):
    def semantic(self, latex, tokens, x=0, y=0, size=42, colors=None, width=12):
        result = SemanticFormula(latex, tokens=tokens, colors=colors, font_size=size)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def construct(self):
        self.motion_samples = []
        methods = (self.opening, self.same_x, self.sweep, self.signs,
                   self.interval, self.zero_point, self.handoff)
        if tuple(c["id"] for c in self.cues) != CUE_IDS:
            raise ValueError("Chapter 05 cue order changed")
        for cue, duration, method in zip(self.cues, CUE_DURATIONS, methods, strict=True):
            if cue["duration"] != duration:
                raise ValueError("Re-author timing before changing a cue duration")
            self.begin_chapter(cue)
            method()
            self.end_chapter()

    def plots(self, tracker, upper_end=.13, lower_end=.25):
        upper = VGroup(Line(plot_point(-2.05, 0), plot_point(2.05, 0)),
                       Line(plot_point(0, -3), plot_point(0, 3))).set_stroke(MUTED, 1.2)
        lower = VGroup(Line(plot_point(-2.05, 0, True), plot_point(2.05, 0, True)),
                       Line(plot_point(0, -4, True), plot_point(0, 10, True))).set_stroke(MUTED, 1.2)
        for x in (-2, -1, 0, 1, 2):
            upper.add(Line(plot_point(x, -.13), plot_point(x, .13), color=MUTED, stroke_width=1))
            lower.add(Line(np.array(plot_point(x, 0, True))+[0, -.04, 0],
                           np.array(plot_point(x, 0, True))+[0, .04, 0], color=MUTED, stroke_width=1))
        curve = polyline([plot_point(x, function(x)) for x in np.linspace(-2.05, 2.05, 181)])
        dcurve = polyline([plot_point(x, derivative(x), True) for x in np.linspace(-2.05, 2.05, 181)], RATE)
        upper_labels = Group(self.label("函数高度", -5.65, 2.86, size=24, color=CURVE, width=2),
                             self.put(r"f(x)=x^3-3x", -1.35, 2.86, size=29, color=CURVE, width=5),
                             self.put("x", 3.65, 1.65, size=26))
        lower_labels = Group(self.label("导数值", -5.65, .42, size=24, color=RATE, width=2),
                             self.put(r"f'(x)=3(x^2-1)", -1.1, .42, size=29, color=RATE, width=5),
                             self.put("x", 3.65, -1.35, size=26),
                             *(self.put(str(x), -.8+2*x, -2.12, size=24, width=.6) for x in (-2, -1, 0, 1, 2)))
        self.beat(upper_end, FadeIn(upper), ShowCreation(curve), FadeIn(upper_labels))
        self.beat(lower_end, FadeIn(lower), ShowCreation(dcurve), FadeIn(lower_labels))
        cursor = Line([0, -2, 0], [0, 2.63, 0], color=ACCENT, stroke_width=1.5)
        point = Dot(radius=.075, fill_color=CURVE)
        dpoint = Dot(radius=.075, fill_color=RATE)
        tangent = Line(*tangent_endpoints(tracker.get_value()), color=ACCENT, stroke_width=3)
        xnum = self.number(tracker.get_value(), decimals=2, size=29, color=ACCENT).move_to([5.15, 1.8, 0])
        fnum = self.number(function(tracker.get_value()), decimals=2, size=29, color=CURVE).move_to([5.15, .7, 0])
        dnum = self.number(derivative(tracker.get_value()), decimals=2, size=29, color=RATE).move_to([5.15, -.8, 0])
        values = Group(self.put("x", 5.15, 2.25, size=27), xnum,
                       self.put("f(x)", 5.15, 1.15, size=25, color=CURVE), fnum,
                       self.put("f'(x)", 5.15, -.35, size=25, color=RATE), dnum)
        driver = Group()

        def update(_):
            state = linked_state(float(tracker.get_value()))
            sx = state["curve_point"][0]
            cursor.put_start_and_end_on(np.array([sx, -2, 0]), np.array([sx, 2.63, 0]))
            point.move_to(state["curve_point"])
            dpoint.move_to(state["derivative_point"])
            tangent.put_start_and_end_on(*(np.array(p) for p in tangent_endpoints(state["x"])))
            xnum.set_value(state["x"])
            fnum.set_value(state["f"])
            dnum.set_value(state["df"])
            self.sample("linked_graphs", **state, tangent=tangent_endpoints(state["x"]))

        update(driver)
        self.add(cursor, point, dpoint, tangent, values, driver)
        driver.add_updater(update)
        return driver

    def opening(self):
        self.beat(.16, FadeIn(self.label("导数与单调性", 0, 1.5, size=58)))
        self.mark("monotonicity_title_ready")
        self.focus_begin("monotonicity_opening")
        self.beat(.42, FadeIn(self.put(r"f(x)=x^3-3x", 0, .1, size=49, color=CURVE)))
        self.beat(.69, FadeIn(self.label("沿 x 向右走，函数哪一段升、哪一段降？", 0, -1.3, size=33)))
        self.mark("monotonicity_question_ready")

    def same_x(self):
        x = ValueTracker(-1.7)
        driver = self.plots(x)
        self.mark("linked_axes_ready")
        self.focus_begin("axes_meanings")
        self.beat(.41, FadeIn(self.label("同一个 x：上面读函数值，下面读导数值", 0, -2.75, size=29)))
        self.mark("shared_x_ready")
        self.focus_begin("same_x_motion")
        self.beat(.75, x.animate.set_value(-1.3), rate_func=linear)
        self.focus_end("same_x_motion")
        driver.clear_updaters()
        self.mark("shared_x_motion_complete")
        self.focus_begin("same_x_result")

    def sweep(self):
        x = ValueTracker(-2)
        driver = self.plots(x, .10, .16)
        self.mark("sweep_start_ready")
        self.focus_begin("left_interval_motion")
        self.beat(.35, x.animate.set_value(-1), rate_func=linear)
        self.focus_end("left_interval_motion")
        self.mark("left_boundary_reached")
        self.focus_begin("minus_one_horizontal")
        self.beat(.42)
        self.focus_end("minus_one_horizontal")
        self.focus_begin("middle_interval_motion")
        self.beat(.66, x.animate.set_value(1), rate_func=linear)
        self.focus_end("middle_interval_motion")
        self.mark("right_boundary_reached")
        self.focus_begin("plus_one_horizontal")
        self.beat(.73)
        self.focus_end("plus_one_horizontal")
        self.focus_begin("right_interval_motion")
        self.beat(.92, x.animate.set_value(2), rate_func=linear)
        self.focus_end("right_interval_motion")
        driver.clear_updaters()
        self.mark("three_intervals_traversed")
        self.focus_begin("sweep_result")

    def signs(self):
        factor = self.semantic(r"f'(x)=3(x-1)(x+1)", {"positive_root": "x-1", "negative_root": "x+1"}, y=2.2,
                               colors={"positive_root": ACCENT, "negative_root": ACCENT})
        self.beat(.15, FadeIn(factor))
        self.beat(.27, FadeIn(self.put(r"f'(x)=0\quad\Longleftrightarrow\quad x=-1\;\mathrm{or}\;x=1", 0, 1.25, size=37)))
        self.mark("derivative_roots_ready")
        self.focus_begin("sign_boundaries")
        line = Line([-5.9, .15, 0], [5.9, .15, 0], color=MUTED)
        ticks = Group(self.put("-1", -2, .6, size=30), self.put("1", 2, .6, size=30),
                      Line([-2, .03, 0], [-2, .27, 0], color=ACCENT),
                      Line([2, .03, 0], [2, .27, 0], color=ACCENT))
        self.beat(.38, FadeIn(line), FadeIn(ticks))
        for p, sign, trend, end in ((-4, "+", "增", .51), (0, "-", "减", .65), (4, "+", "增", .79)):
            self.beat(end, FadeIn(self.put(sign, p, -.45, size=48, color=RATE)),
                      FadeIn(self.label(trend, p, -1.2, size=38, color=CURVE)))
            self.mark({-4: "left_sign_ready", 0: "middle_sign_ready", 4: "right_sign_ready"}[p])
            self.focus_begin({-4: "left_sign", 0: "middle_sign", 4: "right_sign"}[p])
        self.focus_begin("whole_sign_chart")
        self.beat(.9, FadeIn(self.put(r"(-\infty,-1):+\qquad(-1,1):-\qquad(1,+\infty):+", 0, -2.35, size=32)))
        self.mark("sign_chart_complete")

    def interval(self):
        heading_objects = tuple(self.mobjects)
        x = ValueTracker(-1.85)
        driver = self.plots(x, .10, .17)
        a = -2.
        fixed = Dot(plot_point(a, function(a)), radius=.09, fill_color=INK)
        secant = Line(plot_point(a, function(a)), plot_point(x.get_value(), function(x.get_value())), color=INK, stroke_width=2)
        secant.add_updater(lambda line: line.put_start_and_end_on(np.array(plot_point(a, function(a))),
                                                                 np.array(plot_point(x.get_value(), function(x.get_value())))))
        self.beat(.24, FadeIn(fixed), FadeIn(secant),
                  FadeIn(self.label("取区间内任意 a < b", 0, -2.75, size=29)))
        self.mark("interval_pair_ready")
        self.focus_begin("interval_pair_motion")
        self.beat(.43, x.animate.set_value(-1.15), rate_func=linear)
        self.focus_end("interval_pair_motion")
        secant.clear_updaters()
        self.mark("interval_pair_complete")
        self.focus_begin("interval_pair_result")
        self.beat(.46)
        self.focus_end("interval_pair_result")
        b = x.get_value()
        self.add(Dot(plot_point(b, function(b)), radius=.09, fill_color=INK))
        self.focus_begin("secant_witness_motion")
        self.beat(.54, x.animate.set_value(secant_witness(a, b)), rate_func=linear)
        self.focus_end("secant_witness_motion")
        driver.clear_updaters()
        self.mark("secant_witness_ready")
        self.focus_begin("secant_witness_result")
        self.beat(.58)
        self.focus_end("secant_witness_result")
        plot_objects = [obj for obj in self.mobjects if all(obj is not old for old in heading_objects)]
        self.beat(.62, *(FadeOut(obj) for obj in plot_objects))
        theorem = self.label("整个开区间 I 内可导，且处处 f'(x)>0", 0, 2.05, size=32)
        reason = self.put(r"f(b)-f(a)=f'(c)(b-a)>0,\quad a<c<b", 0, .65, size=37)
        self.beat(.68, FadeIn(theorem), FadeIn(reason),
                  FadeIn(self.label("中值定理：两点连线的斜率，等于区间内某处切线的斜率", 0, -.25, size=25)))
        self.mark("interval_condition_ready")
        self.focus_begin("interval_theorem")
        self.beat(.76, FadeIn(self.put(r"a<b\ \Longrightarrow\ f(a)<f(b)", 0, -1.1, size=37)))
        self.mark("interval_increasing_ready")
        self.beat(.9, FadeIn(self.put(r"f'<0\ \text{on}\ I\quad\Longrightarrow\quad f(a)>f(b)\ (a<b)", 0, -2.15, size=31)))
        self.mark("interval_decreasing_ready")
        self.focus_begin("interval_decreasing")

    def zero_point(self):
        p = lambda x: np.array([2.6*x, .45+.42*cube(x), 0])
        x = ValueTracker(-1.15)
        axes = VGroup(Line([-4.4, .45, 0], [4.4, .45, 0]),
                      Line([0, -1.2, 0], [0, 2.2, 0])).set_stroke(MUTED, 1.5)
        curve = polyline([p(t) for t in np.linspace(-1.5, 1.5, 160)])
        point = Dot(p(x.get_value()), radius=.085, fill_color=CURVE)
        tangent = Line([-1, .45, 0], [1, .45, 0], color=ACCENT, stroke_width=3)
        self.beat(.16, FadeIn(axes), ShowCreation(curve), FadeIn(point),
                  FadeIn(Group(self.put("x", 4.65, .45, size=26),
                               self.put("f(x)", .45, 2.15, size=26, color=CURVE),
                               self.put("0", -.23, .15, size=24))),
                  FadeIn(self.put(r"f(x)=x^3,\quad f'(x)=3x^2", 0, 2.65, size=40)))
        self.mark("cube_graph_ready")
        driver = Group()

        def update(_):
            t = float(x.get_value())
            point.move_to(p(t))
            self.sample("cube_motion", x=t, f=cube(t), df=cube_derivative(t), point=p(t).tolist())

        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("cube_to_zero")
        self.beat(.36, x.animate.set_value(0), rate_func=linear)
        self.focus_end("cube_to_zero")
        self.beat(.41, FadeIn(tangent), FadeIn(self.put(r"f'(0)=0", -4.7, 1.7, size=33, color=ACCENT, width=2.6)))
        self.mark("cube_zero_tangent_ready")
        self.focus_begin("cube_zero_state")
        self.beat(.5)
        self.focus_end("cube_zero_state")
        self.focus_begin("cube_after_zero")
        self.beat(.69, x.animate.set_value(1.15), rate_func=linear)
        self.focus_end("cube_after_zero")
        driver.clear_updaters()
        self.mark("cube_crossed_zero")
        self.beat(.79, FadeIn(self.put(r"b^3-a^3=(b-a)(a^2+ab+b^2)>0\quad(a<b)", 0, -1.75, size=31)))
        self.mark("cube_strict_increase_ready")
        self.focus_begin("cube_interval_reason")
        self.beat(.9, FadeIn(self.label("x³ 在整个实数范围严格递增，原点切线水平", 0, -2.6, size=29)))

    def handoff(self):
        self.beat(.17, FadeIn(self.label("把导数符号放回区间", 0, 1.9, size=43)))
        self.beat(.31, FadeIn(self.put(r"f'>0\Rightarrow\text{增}\qquad f'<0\Rightarrow\text{减}", 0, .75, size=45)))
        self.beat(.46, FadeIn(self.label("前提：在所讨论的整个区间内可导且符号一致", 0, -.35, size=30)))
        self.mark("monotonicity_summary_ready")
        self.focus_begin("monotonicity_summary")
        self.beat(.73, FadeIn(self.label("导数为零的位置，函数的增减一定改变吗？", 0, -1.7, size=33)))
        self.mark("extrema_handoff_ready")
        self.focus_begin("monotonicity_to_extrema")
