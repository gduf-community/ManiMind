"""Chapter 06: local extrema, native neighborhoods, and conditional necessity.

Pure functions below own no state. Scene trackers live for one construct;
ChapterScene journals actual geometry for later independent review. Source,
plan, helper or timing changes invalidate that journal, not other lessons.
"""

import math
from numbers import Real
import sys


def finite(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("Expected a real number")
    if not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def cubic(x):
    return finite(x) ** 3 - 3 * x


def slope(x):
    return 3 * (finite(x) ** 2 - 1)


def stationary_cubic(x):
    return finite(x) ** 3


def local_difference(center, h):
    finite(center)
    finite(h)
    return 3 * (center ** 2 - 1) * h + 3 * center * h ** 2 + h ** 3


def turn(left_sign, right_sign):
    if left_sign not in (-1, 1) or right_sign not in (-1, 1):
        raise ValueError("Use the nonzero signs on adjacent intervals")
    return {(1, -1): "maximum", (-1, 1): "minimum"}.get((left_sign, right_sign), "neither")


def graph_point(x, y):
    return (-3.15 + 1.25 * finite(x), .15 + .48 * finite(y), 0.)


_argv = sys.argv
try:
    sys.argv = _argv[:1]
    import numpy as np
    from manimlib import (
        Circle, Dot, FadeIn, FadeOut, Group, Line, Rectangle,
        ShowCreation, ValueTracker, VGroup, VMobject, linear,
    )
    from derivative_chapter_shared import ChapterScene, INK, MUTED, CURVE, RATE, ACCENT
finally:
    sys.argv = _argv
del _argv


CUE_IDS = ("opening", "neighborhood", "signs", "turns", "stationary", "necessary", "closing")
CUE_DURATIONS = (24, 46, 48, 54, 46, 48, 26)


def path(points, color=CURVE, width=4):
    return VMobject().set_points_as_corners(points).set_stroke(color, width)


class DerivativeCh06Extrema(ChapterScene):
    def graph(self, function=cubic, span=(-2.2, 2.2)):
        p = graph_point
        axes = VGroup(Line(p(-2.35, 0), p(2.35, 0)),
                      Line(p(0, -4.3), p(0, 4.5))).set_stroke(MUTED, 1.3)
        curve = path([p(x, function(x)) for x in np.linspace(*span, 221)])
        labels = Group(self.put("x", -.05, -.18, size=25),
                       self.put("y", -3.42, 2.55, size=25))
        for x in (-2, -1, 1, 2):
            labels.add(self.put(str(x), *np.add(p(x, 0), [0, -.32, 0])[:2], size=23))
        return Group(axes, curve, labels)

    def opening(self, cue):
        self.begin_chapter(cue)
        self.beat(.16, FadeIn(self.graph()),
                  FadeIn(self.put(r"f(x)=x^3-3x", 3.5, 1.9, size=43, width=5.2)),
                  FadeIn(self.put(r"f'(x)=3(x^2-1)", 3.5, .85, size=38, color=RATE, width=5.2)))
        self.mark("familiar_cubic_ready")
        self.focus_begin("familiar_cubic")
        self.beat(.65)
        self.focus_end("familiar_cubic")
        self.beat(.73, FadeIn(self.label("上升与下降，在哪里交接？", 3.5, -.65, size=30, width=5.5)),
                  FadeIn(Circle(radius=.18).move_to(graph_point(-1, 2)).set_stroke(ACCENT, 3)),
                  FadeIn(Circle(radius=.18).move_to(graph_point(1, -2)).set_stroke(ACCENT, 3)))
        self.mark("turn_question_ready")
        self.focus_begin("turn_question")
        self.end_chapter()

    def neighborhood(self, cue):
        self.begin_chapter(cue)
        center = ValueTracker(-1)
        radius = .42
        window = Rectangle(width=2 * radius * 1.25, height=4.45,
                           fill_color=ACCENT, fill_opacity=.09, stroke_color=ACCENT, stroke_width=1.5)
        highlight = path([graph_point(x, cubic(x)) for x in np.linspace(-1-radius, -1+radius, 61)], ACCENT, 6)
        point = Dot(graph_point(-1, 2), color=ACCENT, radius=.08)
        value = self.number(-1, decimals=2, size=34, color=ACCENT).move_to([4.1, 1.65, 0])
        header = self.label("窗口中心", 2.6, 1.65, size=27, width=2.3)
        note = self.label("只和窗口内的附近点比较", 3.5, .65, size=29, width=5.5)
        self.beat(.14, FadeIn(self.graph()), FadeIn(window), FadeIn(highlight), FadeIn(point),
                  FadeIn(header), FadeIn(value), FadeIn(note))
        driver = Group()

        def update(_):
            a = center.get_value()
            window.move_to([graph_point(a, 0)[0], .2, 0])
            highlight.set_points_as_corners([graph_point(x, cubic(x)) for x in np.linspace(a-radius, a+radius, 61)])
            point.move_to(graph_point(a, cubic(a)))
            value.set_value(a)
            self.sample("local_window", center=a, radius=radius, point=point.get_center().tolist(),
                        left=cubic(a-radius), center_value=cubic(a), right=cubic(a+radius))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        max_text = self.put(r"f(-1)=2", 3.5, -.4, color=ACCENT, size=41, width=5.2)
        max_note = self.label("左侧升到这里，右侧从这里降", 3.5, -1.3, size=26, width=5.5)
        self.beat(.20, FadeIn(max_text), FadeIn(max_note))
        self.mark("local_max_window_ready")
        self.focus_begin("local_max_window")
        self.beat(.43)
        self.focus_end("local_max_window")
        self.beat(.48, FadeOut(max_text), FadeOut(max_note))
        self.focus_begin("window_move")
        self.beat(.67, center.animate.set_value(1), rate_func=linear)
        self.focus_end("window_move")
        self.mark("local_min_window_ready")
        self.beat(.72, FadeIn(self.put(r"f(1)=-2", 3.5, -.4, color=ACCENT, size=41, width=5.2)),
                  FadeIn(self.label("左侧降到这里，右侧从这里升", 3.5, -1.3, size=26, width=5.5)))
        self.focus_begin("local_min_window")
        self.beat(.95)
        self.focus_end("local_min_window")
        driver.clear_updaters()
        self.end_chapter()

    def signs(self, cue):
        self.begin_chapter(cue)
        self.beat(.13, FadeIn(self.put(r"f'(x)=3(x-1)(x+1)", 0, 2.15, size=45, color=RATE)),
                  FadeIn(self.put(r"f'(x)=0\quad\Longrightarrow\quad x=-1,\ 1", 0, 1.2, size=37)))
        self.mark("critical_positions_ready")
        self.focus_begin("critical_positions")
        self.beat(.29)
        self.focus_end("critical_positions")
        axis = Line([-5.7, .3, 0], [5.7, .3, 0], color=MUTED)
        self.beat(.34, ShowCreation(axis),
                  FadeIn(self.put("-1", -2, -.08, size=29)), FadeIn(self.put("1", 2, -.08, size=29)))
        sign_rows = Group()
        for x, text in ((-3.9, "+"), (0, "-"), (3.9, "+")):
            sign_rows.add(self.put(text, x, .75, size=47, color=RATE))
        for x in (-2, 2):
            sign_rows.add(Dot([x, .3, 0], radius=.06, color=RATE), self.put("0", x, .75, size=31, color=RATE))
        self.beat(.44, FadeIn(sign_rows), FadeIn(self.label("导数符号", -5.45, 1, size=24, width=1.5)))
        self.mark("three_sign_intervals_ready")
        self.focus_begin("three_sign_intervals")
        self.beat(.67)
        self.focus_end("three_sign_intervals")
        arrows = VGroup(Line([-5, -1.7, 0], [-2.8, -.7, 0], color=CURVE),
                         Line([-1.2, -.7, 0], [1.2, -1.7, 0], color=CURVE),
                         Line([2.8, -1.7, 0], [5, -.7, 0], color=CURVE))
        self.beat(.78, ShowCreation(arrows),
                  FadeIn(self.label("增", -3.9, -2.2, color=CURVE)),
                  FadeIn(self.label("减", 0, -2.2, color=CURVE)),
                  FadeIn(self.label("增", 3.9, -2.2, color=CURVE)))
        self.mark("sign_to_monotonicity_ready")
        self.focus_begin("sign_to_monotonicity")
        self.end_chapter()

    def turns(self, cue):
        self.begin_chapter(cue)
        self.beat(.12, FadeIn(self.graph()))
        probe = ValueTracker(-1.8)
        dot = Dot(graph_point(-1.8, cubic(-1.8)), color=ACCENT, radius=.085)
        driver = Group()

        def update(_):
            x = probe.get_value()
            dot.move_to(graph_point(x, cubic(x)))
            self.sample("cubic_traverse", x=x, y=cubic(x), derivative=slope(x))

        update(driver)
        driver.add_updater(update)
        self.add(driver, dot)
        first = Group(self.put(r"+\ \longrightarrow\ -", 3.4, 1.8, size=43, color=RATE),
                      self.label("先增后减", 3.4, .9, size=30),
                      self.put(r"x=-1:\ f(-1)=2", 3.4, -.2, size=39, color=ACCENT, width=5.4))
        self.beat(.17, FadeIn(first))
        self.mark("max_traverse_start")
        self.focus_begin("max_traverse")
        self.beat(.29, probe.animate.set_value(-1), rate_func=linear)
        self.beat(.43, probe.animate.set_value(-.2), rate_func=linear)
        self.focus_end("max_traverse")
        self.beat(.48, FadeOut(first))
        second = Group(self.put(r"-\ \longrightarrow\ +", 3.4, 1.8, size=43, color=RATE),
                       self.label("先减后增", 3.4, .9, size=30),
                       self.put(r"x=1:\ f(1)=-2", 3.4, -.2, size=39, color=ACCENT, width=5.4))
        self.beat(.54, FadeIn(second))
        self.mark("min_traverse_start")
        self.focus_begin("min_traverse")
        self.beat(.68, probe.animate.set_value(1), rate_func=linear)
        self.beat(.81, probe.animate.set_value(1.8), rate_func=linear)
        self.focus_end("min_traverse")
        driver.clear_updaters()
        self.beat(.87, FadeIn(self.label("极值点是位置，极值是函数值", 3.4, -1.6, size=27, width=5.4)))
        self.mark("point_value_distinction_ready")
        self.focus_begin("point_value_distinction")
        self.end_chapter()

    def stationary(self, cue):
        self.begin_chapter(cue)
        self.beat(.13, FadeIn(self.graph(stationary_cubic, (-1.5, 1.5))),
                  FadeIn(self.put(r"g(x)=x^3", 3.5, 2, size=43)),
                  FadeIn(self.put(r"g'(x)=3x^2", 3.5, 1.1, size=39, color=RATE)),
                  FadeIn(self.put(r"g'(0)=0", 3.5, .2, size=40, color=ACCENT)))
        self.mark("stationary_zero_ready")
        self.focus_begin("stationary_zero")
        self.beat(.31)
        self.focus_end("stationary_zero")
        self.beat(.36, ShowCreation(Line(graph_point(-.7, 0), graph_point(.7, 0), color=ACCENT, stroke_width=4)),
                  FadeIn(self.put(r"+\quad 0\quad +", 3.5, -.8, size=42, color=RATE)))
        tracker = ValueTracker(-1.2)
        dot = Dot(graph_point(-1.2, stationary_cubic(-1.2)), color=ACCENT, radius=.08)
        driver = Group()

        def update(_):
            x = tracker.get_value()
            dot.move_to(graph_point(x, stationary_cubic(x)))
            self.sample("stationary_pass", x=x, y=stationary_cubic(x), derivative=3*x*x)

        update(driver)
        driver.add_updater(update)
        self.add(driver, dot)
        self.mark("stationary_pass_start")
        self.focus_begin("stationary_pass")
        self.beat(.53, tracker.animate.set_value(0), rate_func=linear)
        self.beat(.73, tracker.animate.set_value(1.2), rate_func=linear)
        self.focus_end("stationary_pass")
        driver.clear_updaters()
        self.beat(.80, FadeIn(self.label("经过原点后继续增：驻点，无极值", 3.5, -1.85, size=27, width=5.5)))
        self.mark("stationary_no_extremum_ready")
        self.focus_begin("stationary_no_extremum")
        self.end_chapter()

    def necessary(self, cue):
        self.begin_chapter(cue)
        condition = self.label("可导的内点 a", 0, 2.3, size=33, color=ACCENT)
        implication = Group(self.label("a 是局部极值点", -2.7, 1.35, size=31, width=5),
                            self.put(r"\Longrightarrow\quad f'(a)=0", 2.65, 1.35, size=40, width=5))
        self.beat(.13, FadeIn(condition), FadeIn(implication))
        self.mark("conditional_necessity_ready")
        self.focus_begin("conditional_necessity")
        self.beat(.29)
        self.focus_end("conditional_necessity")
        left = self.put(r"h<0:\ \frac{f(a+h)-f(a)}h\geq0", -3, .25, size=31, width=5.6)
        right = self.put(r"h>0:\ \frac{f(a+h)-f(a)}h\leq0", 3, .25, size=31, width=5.6)
        self.beat(.36, FadeIn(self.label("以局部极大为例", 0, .77, size=25, color=MUTED)),
                  FadeIn(left), FadeIn(right))
        self.mark("one_sided_quotients_ready")
        self.focus_begin("one_sided_quotients")
        self.beat(.55)
        self.focus_end("one_sided_quotients")
        self.beat(.61, FadeIn(self.label("双侧导数相同，只能为 0；极小同理", 0, -.65, size=29)))
        self.focus_begin("common_zero_necessity")
        self.beat(.72)
        self.focus_end("common_zero_necessity")
        cusp = path([[-2.4, -1.3, 0], [-1.2, -2.5, 0], [0, -1.3, 0]], ACCENT)
        self.beat(.79, ShowCreation(cusp), FadeIn(self.put(r"y=|x|", -4, -1.9, size=35, width=2.3)),
                  FadeIn(self.label("0 是尖点极小，导数不存在", 3.1, -1.8, size=28, width=5.7)),
                  FadeIn(self.label("这说明为什么要保留“可导内点”", 3.1, -2.5, size=26, color=MUTED, width=5.7)))
        self.mark("cusp_condition_ready")
        self.focus_begin("cusp_condition")
        self.end_chapter()

    def closing(self, cue):
        self.begin_chapter(cue)
        self.beat(.16, FadeIn(self.label("附近比较，决定局部极值", 0, 2, size=36)),
                  FadeIn(self.put(r"+\to-:\ \mathrm{max}\qquad -\to+:\ \mathrm{min}", 0, .85, size=43, color=RATE)),
                  FadeIn(self.label("可导内点先找驻点，再看两侧增减", 0, -.25, size=31)))
        self.mark("local_method_ready")
        self.focus_begin("local_method")
        self.beat(.65)
        self.focus_end("local_method")
        self.beat(.74, FadeIn(self.label("如果和整个区间比较，端点怎么办？", 0, -1.75, size=33, color=ACCENT)))
        self.mark("whole_interval_question_ready")
        self.focus_begin("whole_interval_question")
        self.end_chapter()

    def construct(self):
        if tuple(c["id"] for c in self.cues) != CUE_IDS:
            raise ValueError("Chapter 06 cue order differs from authored design")
        self.motion_samples = []
        for cue in self.cues:
            self.until(cue["start"])
            getattr(self, cue["id"])(cue)
