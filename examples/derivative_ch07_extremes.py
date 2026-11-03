"""Chapter 07: extrema over a whole interval, including moving endpoints."""

import math
from numbers import Real
import sys


def finite(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("Expected a real number")
    if not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def value(x):
    return (finite(x)-1) ** 2


def candidates(a, b):
    finite(a)
    finite(b)
    if a >= b:
        raise ValueError("Use an ordered nondegenerate closed interval")
    xs = [a] + ([1] if a < 1 < b else []) + [b]
    return tuple((x, value(x)) for x in xs)


def closed_extremes(a, b):
    rows = candidates(a, b)
    minimum, maximum = min(y for _, y in rows), max(y for _, y in rows)
    return {"minimum": minimum, "maximum": maximum,
            "argmin": tuple(x for x, y in rows if y == minimum),
            "argmax": tuple(x for x, y in rows if y == maximum)}


def open_extremes(a, b):
    rows = candidates(a, b)
    low, high = min(y for _, y in rows), max(y for _, y in rows)
    # The quadratic is strictly convex; its vertex is the only possible
    # interior extremum. Values at the excluded endpoints give limiting bounds.
    return {"infimum": low, "supremum": high,
            "minimum": 0 if a < 1 < b else None,
            "argmin": (1,) if a < 1 < b else (), "maximum": None, "argmax": ()}


def graph_point(x, y):
    return (-5.7 + 1.9 * finite(x), -1.75 + .8 * finite(y), 0.)


_argv = sys.argv
try:
    sys.argv = _argv[:1]
    import numpy as np
    from manimlib import Circle, Dot, FadeIn, FadeOut, Group, Line, ShowCreation, ValueTracker, VGroup, VMobject, linear
    from derivative_chapter_shared import ChapterScene, INK, MUTED, CURVE, RATE, ACCENT, BG
finally:
    sys.argv = _argv
del _argv

CUE_IDS = ("opening", "candidates", "compare", "parameter", "conditions", "open_interval", "closing")
CUE_DURATIONS = (24, 48, 38, 58, 38, 46, 24)


def path(points, color=CURVE, width=4):
    return VMobject().set_points_as_corners(points).set_stroke(color, width)


class DerivativeCh07Extremes(ChapterScene):
    def graph(self, right=3, closed=True):
        p = graph_point
        axes = VGroup(Line(p(-.15, 0), p(3.3, 0)),
                      Line(p(0, -.2), p(0, 4.65))).set_stroke(MUTED, 1.3)
        curve = path([p(x, value(x)) for x in np.linspace(0, right, 181)])
        labels = Group(self.put("x", .95, -1.95, size=25), self.put("y", -6.1, 2.1, size=25))
        for x in (0, 1, 2, 3):
            labels.add(self.put(str(x), *np.add(p(x, 0), [0, -.32, 0])[:2], size=25))
        ends = VGroup(*(Dot(p(x, value(x)), radius=.075, color=ACCENT) if closed else
                        Circle(radius=.085, stroke_color=ACCENT, stroke_width=3,
                               fill_color=BG, fill_opacity=1).move_to(p(x, value(x))) for x in (0, right)))
        return Group(axes, curve, labels, ends)

    def opening(self, cue):
        self.begin_chapter(cue)
        self.beat(.15, FadeIn(self.graph()),
                  FadeIn(self.put(r"f(x)=(x-1)^2", 3.5, 1.95, size=42, width=5.5)),
                  FadeIn(self.put(r"x\in[0,3]", 3.5, .95, size=42, color=ACCENT, width=5.5)))
        self.mark("closed_problem_ready")
        self.focus_begin("closed_problem")
        self.beat(.62)
        self.focus_end("closed_problem")
        self.beat(.72, FadeIn(self.label("这次和整个区间里的点比较", 3.5, -.4, size=29, width=5.5)),
                  FadeIn(self.label("边界上的点，也在范围内", 3.5, -1.35, size=28, color=ACCENT, width=5.5)))
        self.mark("whole_comparison_ready")
        self.focus_begin("whole_comparison")
        self.end_chapter()

    def candidates(self, cue):
        self.begin_chapter(cue)
        self.beat(.12, FadeIn(self.graph()),
                  FadeIn(self.put(r"f'(x)=2(x-1)", 3.5, 2.05, size=39, color=RATE, width=5.5)),
                  FadeIn(self.put(r"f'(x)=0\ \Longrightarrow\ x=1", 3.5, 1.1, size=34, width=5.5)))
        self.mark("interior_candidate_ready")
        self.focus_begin("interior_candidate")
        self.beat(.31)
        self.focus_end("interior_candidate")
        points = VGroup(*(Circle(radius=.15).move_to(graph_point(x, value(x))).set_stroke(ACCENT, 3)
                          for x in (0, 1, 3)))
        self.beat(.41, FadeIn(points),
                  FadeIn(self.label("端点", 2.15, -.1, size=28, color=ACCENT)),
                  FadeIn(self.put(r"0,\ 3", 4.5, -.1, size=39, color=ACCENT, width=2.5)),
                  FadeIn(self.label("内部驻点", 2.15, -1.05, size=28)),
                  FadeIn(self.put("1", 4.5, -1.05, size=39, width=2.5)))
        self.mark("all_candidates_ready")
        self.focus_begin("all_candidates")
        self.beat(.72)
        self.focus_end("all_candidates")
        self.beat(.81, FadeIn(self.label("本例处处可导，内部极值必在驻点", 3.5, -2.15, size=26, width=5.5)))
        self.mark("candidate_reason_ready")
        self.focus_begin("candidate_reason")
        self.end_chapter()

    def compare(self, cue):
        self.begin_chapter(cue)
        self.beat(.13, FadeIn(self.graph()),
                  FadeIn(self.put("x", 2.25, 2.15, size=34)),
                  FadeIn(self.put("f(x)", 4.65, 2.15, size=34)))
        for index, (x, y) in enumerate(candidates(0, 3)):
            row_y = 1.25 - .9 * index
            self.beat(.23 + index*.11,
                      FadeIn(self.put(str(x), 2.25, row_y, size=39, color=ACCENT)),
                      FadeIn(self.put(str(y), 4.65, row_y, size=39, color=CURVE)),
                      FadeIn(Dot(graph_point(x, y), radius=.09, color=ACCENT)))
        self.mark("candidate_values_ready")
        self.focus_begin("candidate_values")
        self.beat(.62)
        self.focus_end("candidate_values")
        self.beat(.72, FadeIn(self.put(r"\min f=0\quad(x=1)", 3.5, -1.55, size=34, color=CURVE, width=5.5)),
                  FadeIn(self.put(r"\max f=4\quad(x=3)", 3.5, -2.4, size=34, color=ACCENT, width=5.5)))
        self.mark("closed_extremes_ready")
        self.focus_begin("closed_extremes")
        self.end_chapter()

    def parameter(self, cue):
        self.begin_chapter(cue)
        b = ValueTracker(1.25)
        moving_curve = path([graph_point(x, value(x)) for x in np.linspace(0, 1.25, 121)])
        endpoint = Dot(graph_point(1.25, value(1.25)), color=ACCENT, radius=.085)
        boundary = Line(graph_point(1.25, 0), graph_point(1.25, value(1.25)), color=ACCENT, stroke_width=2)
        base = self.graph()
        # Only the faint complete parabola is a reference; the bright curve and
        # yellow moving endpoint encode the current admissible closed interval.
        base[1].set_stroke(MUTED, 1, opacity=.28)
        base[3].set_opacity(0)
        self.beat(.12, FadeIn(base), FadeIn(moving_curve), FadeIn(endpoint), FadeIn(boundary),
                  FadeIn(self.put(r"x\in[0,b],\quad1\leq b\leq3", 3.5, 2.25, size=33, width=5.8)))
        b_num = self.number(1.25, decimals=2, size=33, color=ACCENT).move_to([4.7, 1.35, 0])
        fb_num = self.number(value(1.25), decimals=2, size=33, color=ACCENT).move_to([4.7, -.35, 0])
        self.beat(.18, FadeIn(self.put("b=", 2.15, 1.35, size=33)), FadeIn(b_num),
                  FadeIn(self.put(r"f(0)=1", 3.5, .5, size=35, width=5.5)),
                  FadeIn(self.put("f(b)=", 2.15, -.35, size=33)), FadeIn(fb_num),
                  FadeIn(self.put(r"f(1)=0", 3.5, -1.2, size=35, color=CURVE, width=5.5)))
        driver = Group()

        def update(_):
            right = b.get_value()
            moving_curve.set_points_as_corners([graph_point(x, value(x)) for x in np.linspace(0, right, 121)])
            endpoint.move_to(graph_point(right, value(right)))
            boundary.put_start_and_end_on(np.array(graph_point(right, 0)), np.array(graph_point(right, value(right))))
            b_num.set_value(right)
            fb_num.set_value(value(right))
            self.sample("moving_endpoint", b=right, candidates=[1, 0, value(right)],
                        endpoint=endpoint.get_center().tolist(), **closed_extremes(0, right))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        left_note = self.label("右端点还低于左端点", 3.5, -2.2, size=27, width=5.5)
        self.beat(.23, FadeIn(left_note))
        self.mark("parameter_left_wins_ready")
        self.focus_begin("parameter_left_wins")
        self.beat(.37, b.animate.set_value(1.8), rate_func=linear)
        self.focus_end("parameter_left_wins")
        self.beat(.40, FadeOut(left_note))
        self.focus_begin("parameter_to_tie")
        self.beat(.51, b.animate.set_value(2), rate_func=linear)
        self.focus_end("parameter_to_tie")
        tie = self.label("b = 2：两端同高，最大值都是 1", 3.5, -2.2, size=26, width=5.6)
        self.beat(.55, FadeIn(tie))
        self.mark("parameter_tie_ready")
        self.focus_begin("parameter_tie")
        self.beat(.66)
        self.focus_end("parameter_tie")
        self.beat(.69, FadeOut(tie))
        self.focus_begin("parameter_right_overtakes")
        self.beat(.83, b.animate.set_value(3), rate_func=linear)
        self.focus_end("parameter_right_overtakes")
        driver.clear_updaters()
        self.beat(.87, FadeIn(self.label("右端点升得更高，最大值转到右端", 3.5, -2.2, size=26, width=5.6)))
        self.mark("parameter_right_wins_ready")
        self.focus_begin("parameter_right_wins")
        self.end_chapter()

    def conditions(self, cue):
        self.begin_chapter(cue)
        self.beat(.15, FadeIn(self.graph()),
                  FadeIn(self.label("连续", 2.1, 1.95, size=32, color=CURVE)),
                  FadeIn(self.label("有限闭区间", 4.65, 1.95, size=32, color=ACCENT, width=3.3)),
                  FadeIn(self.label("曲线不断开，两个端点也在其中", 3.5, .85, size=27, width=5.5)))
        self.mark("existence_conditions_ready")
        self.focus_begin("existence_conditions")
        self.beat(.49)
        self.focus_end("existence_conditions")
        self.beat(.58, FadeIn(self.label("保证最大值、最小值都能取到", 3.5, -.3, size=29, width=5.5)),
                  FadeIn(self.label("本例：比较端点与内部驻点的值", 3.5, -1.3, size=27, width=5.5)),
                  FadeIn(self.label("若内部不可导，还需检查那些位置", 3.5, -2.2, size=25, color=MUTED, width=5.5)))
        self.mark("existence_and_search_ready")
        self.focus_begin("existence_and_search")
        self.end_chapter()

    def open_interval(self, cue):
        self.begin_chapter(cue)
        self.beat(.12, FadeIn(self.graph(closed=False)),
                  FadeIn(self.put(r"f(x)=(x-1)^2,\quad x\in(0,3)", 3.5, 2.15, size=32, width=5.7)),
                  FadeIn(self.label("空心端点：位置不属于区间", 3.5, 1.25, size=27, color=ACCENT, width=5.5)),
                  FadeIn(Dot(graph_point(1, 0), color=CURVE, radius=.085)),
                  FadeIn(self.put(r"\min f=0\quad(x=1)", 3.5, .3, size=35, color=CURVE, width=5.5)))
        self.mark("open_minimum_retained_ready")
        self.focus_begin("open_minimum_retained")
        self.beat(.35)
        self.focus_end("open_minimum_retained")
        x = ValueTracker(2.2)
        point = Dot(graph_point(2.2, value(2.2)), color=ACCENT, radius=.075)
        number = self.number(value(2.2), decimals=3, size=33, color=ACCENT).move_to([4.8, -.65, 0])
        self.beat(.40, FadeIn(point), FadeIn(self.put("f(x)=", 2.2, -.65, size=32)), FadeIn(number))
        driver = Group()

        def update(_):
            t = x.get_value()
            point.move_to(graph_point(t, value(t)))
            number.set_value(value(t))
            self.sample("open_approach", x=t, value=value(t), gap=4-value(t), endpoint_included=False)

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.mark("open_approach_start")
        self.focus_begin("open_approach")
        self.beat(.67, x.animate.set_value(2.99), rate_func=linear)
        self.focus_end("open_approach")
        driver.clear_updaters()
        self.beat(.74, FadeIn(self.put(r"x\to3^-:\ f(x)\to4", 3.5, -1.55, size=34, color=ACCENT, width=5.5)),
                  FadeIn(self.label("上确界为 4，无最大值；最小值仍为 0", 3.5, -2.45, size=25, width=5.8)))
        self.mark("unattained_supremum_ready")
        self.focus_begin("unattained_supremum")
        self.end_chapter()

    def closing(self, cue):
        self.begin_chapter(cue)
        self.beat(.15, FadeIn(self.label("先定比较范围，再找候选并比较值", 0, 2.05, size=35)),
                  FadeIn(self.put(r"[0,3]:\quad \min f=0,\quad\max f=4", 0, .85, size=42)),
                  FadeIn(self.put(r"(0,3):\quad \min f=0,\quad\sup f=4", 0, -.25, size=42, color=ACCENT)),
                  FadeIn(self.label("上界能否取到，要回到定义域", 0, -1.15, size=30)))
        self.mark("interval_method_ready")
        self.focus_begin("interval_method")
        self.beat(.66)
        self.focus_end("interval_method")
        self.beat(.76, FadeIn(self.label("下一课：把实际尺寸，变成可比较的函数", 0, -2.3, size=31, color=CURVE)))
        self.mark("modeling_bridge_ready")
        self.focus_begin("modeling_bridge")
        self.end_chapter()

    def construct(self):
        if tuple(c["id"] for c in self.cues) != CUE_IDS:
            raise ValueError("Chapter 07 cue order differs from authored design")
        self.motion_samples = []
        for cue in self.cues:
            self.until(cue["start"])
            getattr(self, cue["id"])(cue)
