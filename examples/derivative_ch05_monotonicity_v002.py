"""Add a disconnected-domain counterexample without changing v001 chapters.

The two branch trackers never cross zero. Each driver owns one visible point
and expires before its readout is removed. Actual runtime journals their states;
new source, axes, text or timing invalidates those observations, not the frozen
baseline. Pixel and content-regression judgments remain independent tasks.
"""

import numpy as np
from manimlib import Circle, DashedLine, Dot, FadeIn, FadeOut, Group, Line, ShowCreation, ValueTracker, VGroup, linear

from derivative_ch05_monotonicity import DerivativeMonotonicityLesson, finite_real, polyline
from derivative_chapter_shared import INK, MUTED, CURVE, RATE, ACCENT


AUTHOR_AGENT = "01a199e9-73ab-7700-8a9f-cd7b5541b0ad"
CUE_IDS = ("opening", "same-x", "sweep", "signs", "interval", "zero-point", "disconnected-domain", "handoff")
CUE_DURATIONS = (24, 42, 70, 42, 66, 50, 72, 30)


def reciprocal(x):
    x = finite_real(x)
    if x == 0:
        raise ValueError("Require x != 0")
    return -1/x


def reciprocal_derivative(x):
    x = finite_real(x)
    if x == 0:
        raise ValueError("Require x != 0")
    return 1/(x*x)


def reciprocal_point(x):
    return (-2.25+1.15*finite_real(x), .1+.75*reciprocal(x), 0.)


def disconnected_pair(a, b):
    a, b = finite_real(a), finite_real(b)
    if not a < 0 < b:
        raise ValueError("Choose a < 0 < b")
    return {"a": a, "b": b, "qa": reciprocal(a), "qb": reciprocal(b),
            "derivative_a": reciprocal_derivative(a), "derivative_b": reciprocal_derivative(b),
            "output_difference": reciprocal(b)-reciprocal(a),
            "gap": 0, "whole_interval_defined": False}


class DerivativeMonotonicityLessonV002(DerivativeMonotonicityLesson):
    def construct(self):
        self.motion_samples = []
        methods = (self.opening, self.same_x, self.sweep, self.signs, self.interval,
                   self.zero_point, self.disconnected_domain, self.handoff)
        if tuple(c["id"] for c in self.cues) != CUE_IDS:
            raise ValueError("Chapter 05 v002 cue order changed")
        for cue, duration, method in zip(self.cues, CUE_DURATIONS, methods, strict=True):
            if cue["duration"] != duration:
                raise ValueError("Re-author timing before changing a cue duration")
            self.begin_chapter(cue)
            method()
            self.end_chapter()

    def branch_motion(self, initial, color, phase):
        tracker = ValueTracker(initial)
        point = Dot(reciprocal_point(initial), radius=.085, fill_color=color)
        xread = self.number(initial, decimals=2, size=30, color=color).move_to([4.25, 1.2, 0])
        qread = self.number(reciprocal(initial), decimals=2, size=30, color=color).move_to([4.25, .5, 0])
        readouts = Group(self.put("x=", 2.95, 1.2, size=29, color=color), xread,
                         self.put("q(x)=", 2.95, .5, size=29, color=color), qread)
        driver = Group()

        def update(_):
            x = float(tracker.get_value())
            point.move_to(reciprocal_point(x))
            xread.set_value(x).move_to([4.25, 1.2, 0])
            qread.set_value(reciprocal(x)).move_to([4.25, .5, 0])
            self.sample("reciprocal_branch", phase=phase, x=x, q=reciprocal(x),
                        dq=reciprocal_derivative(x), point=point.get_center().tolist())

        return tracker, point, readouts, driver, update

    def disconnected_domain(self):
        formula = self.put(r"q(x)=-\frac1x", -2.5, 2.65, size=40, color=CURVE, width=5.5)
        derivative = self.put(r"q'(x)=\frac1{x^2}>0\ (x\ne0)", 3.45, 2.65, size=33, color=RATE, width=5.7)
        domain = self.put(r"D=(-\infty,0)\cup(0,+\infty)", 0, 2.0, size=31)
        self.beat(.10, FadeIn(formula), FadeIn(derivative), FadeIn(domain))
        self.mark("disconnected_model_ready")
        p = lambda x, y: np.array([-2.25+1.15*x, .1+.75*y, 0.])
        axes = VGroup(Line(p(-3, 0), p(3, 0)),
                      DashedLine(p(0, -2.1), p(0, 2.1), dash_length=.1)).set_stroke(MUTED, 1.5)
        left = polyline([reciprocal_point(float(x)) for x in np.linspace(-2.8, -.5, 120)], CURVE)
        right = polyline([reciprocal_point(float(x)) for x in np.linspace(.5, 2.8, 120)], ACCENT)
        gap = Circle(radius=.095).set_stroke(RATE, 3).set_fill(opacity=0).move_to(p(0, 0))
        axis_labels = Group(self.put("x", 1.5, .1, size=26),
                            self.put("q(x)", -1.65, 1.7, size=26, color=CURVE),
                            self.put("0", -2.5, -.25, size=24),
                            self.label("0 处无定义", -2.25, -1.85, size=24, color=RATE, width=2.1),
                            self.put("-1", -3.4, -.22, size=24),
                            self.put("1", -1.1, .38, size=24))
        self.beat(.16, FadeIn(axes), ShowCreation(left), ShowCreation(right), FadeIn(gap), FadeIn(axis_labels))
        self.mark("disconnected_branches_ready")
        self.focus_begin("disconnected_domain")

        x, a, reads, driver, update = self.branch_motion(-2, CURVE, "left")
        self.beat(.26, FadeIn(a), FadeIn(reads))
        self.add(driver)
        driver.add_updater(update)
        update(driver)
        self.mark("branch_left_start_ready")
        self.focus_begin("branch_left_motion")
        self.beat(.39, x.animate.set_value(-1), rate_func=linear)
        self.focus_end("branch_left_motion")
        driver.clear_updaters()
        self.mark("branch_left_complete")
        self.beat(.41, FadeOut(reads), FadeIn(self.put(r"A=(-1,1)", -4.5, 1.27, size=28, color=CURVE, width=2.7)))

        x, b, reads, driver, update = self.branch_motion(.5, ACCENT, "right")
        self.beat(.43, FadeIn(b), FadeIn(reads))
        self.add(driver)
        driver.add_updater(update)
        update(driver)
        self.mark("branch_right_start_ready")
        self.focus_begin("branch_right_motion")
        self.beat(.56, x.animate.set_value(1), rate_func=linear)
        self.focus_end("branch_right_motion")
        driver.clear_updaters()
        self.mark("branch_right_complete")
        self.beat(.60, FadeOut(reads), FadeIn(self.put(r"B=(1,-1)", .15, -1.07, size=28, color=ACCENT, width=2.7)))
        comparison = Group(self.put("-1<1", 3.65, 1.25, size=37),
                           self.put(r"q(-1)=1>q(1)=-1", 3.65, .4, size=32, width=5.7))
        self.beat(.64, FadeIn(comparison))
        self.mark("cross_gap_comparison_ready")
        self.sample("disconnected_comparison", **disconnected_pair(-1, 1))
        self.focus_begin("cross_gap_comparison")
        self.beat(.76, FadeIn(self.put(r"0\in[-1,1],\quad q(0)\ \text{undefined}", 3.55, -.65, size=29, width=5.7)),
                  FadeIn(self.label("中值定理的区间条件未满足", 3.55, -1.4, size=25, width=5.7)))
        self.mark("gap_interval_condition_ready")
        self.focus_begin("gap_interval_condition")
        self.beat(.90, FadeIn(self.label("分别在 (-∞,0)、(0,+∞) 递增；跨过 0 不能合并", 0, -2.6, size=29)))
        self.mark("separate_intervals_ready")
        self.focus_begin("separate_intervals")
