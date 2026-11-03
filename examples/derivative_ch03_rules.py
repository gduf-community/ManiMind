"""Chapter 03: derivative rules from signed increments and changing area.

All scientific states are pure functions. A cue owns each tracker/driver: the
scene writes it, geometry/readouts consume it, cue exit removes it. The shared
runtime records actual windows; draft fractions are not speech timestamps.
"""

import math
from numbers import Real
import sys

import numpy as np


def finite(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("A real number is required")
    if not math.isfinite(value):
        raise ValueError("A finite number is required")
    return value


def linear_state(x, h, c=3):
    finite(x)
    finite(c)
    if finite(h) == 0:
        raise ValueError("Difference quotients require h != 0")
    du, dv = 2*x*h+h*h, h
    return {"x": x, "h": h, "du": du, "dv": dv,
            "sum_increment": du+dv, "difference_increment": du-dv,
            "scaled_increment": c*du, "sum_rate": 2*x+h+1,
            "difference_rate": 2*x+h-1, "scaled_rate": c*(2*x+h)}


def product_state(x, h):
    """u=2+x, v=1+x². The identity is exact, including signed h."""
    finite(x)
    finite(h)
    u, v, du, dv = 2+x, 1+x*x, h, 2*x*h+h*h
    return {"x": x, "h": h, "u": u, "v": v, "du": du, "dv": dv,
            "right": v*du, "top": u*dv, "corner": du*dv,
            "increment": v*du+u*dv+du*dv,
            "derivative": v+u*2*x}


def product_quotient(x, h):
    if finite(h) == 0:
        raise ValueError("Difference quotient requires h != 0")
    state = product_state(x, h)
    return {**state, "right_rate": state["right"]/h, "top_rate": state["top"]/h,
            "corner_rate": state["corner"]/h, "rate": state["increment"]/h}


def quotient_increment(u, v, du, dv):
    for value in (u, v, du, dv):
        finite(value)
    if v == 0 or v+dv == 0:
        raise ValueError("Require v != 0 and v+dv != 0")
    return (v*du-u*dv)/(v*(v+dv))


def quotient_derivative(u, v, up, vp):
    for value in (u, v, up, vp):
        finite(value)
    if v == 0:
        raise ValueError("Quotient derivative requires v != 0")
    return (up*v-u*vp)/(v*v)


def average_cost_state(x):
    if finite(x) <= 0:
        raise ValueError("Continuous production model requires x > 0")
    cost = x*x+4
    return {"x": x, "total_cost": cost, "average_cost": cost/x,
            "derivative": quotient_derivative(cost, x, 2*x, 1)}


def average_cost_quotient(x, h):
    finite(h)
    if h == 0:
        raise ValueError("Difference quotient requires h != 0")
    average_cost_state(x)
    average_cost_state(x+h)
    return 1-4/(x*(x+h))


def product_example(x):
    x = finite(x)
    return {"value": x*x*math.sin(x),
            "derivative": 2*x*math.sin(x)+x*x*math.cos(x)}


_argv = sys.argv
try:
    sys.argv = _argv[:1]
    from manimlib import Dot, FadeIn, FadeOut, Group, Line, Polygon, ValueTracker, VMobject, linear
    from manimind.components.formula_motion import SemanticFormula
    from derivative_chapter_shared import ChapterScene, INK, MUTED, CURVE, RATE, ACCENT
finally:
    sys.argv = _argv
del _argv


CUE_IDS = ("opening", "linearity", "product_area", "product_limit", "product_example",
           "quotient_increment", "quotient_limit", "cost_example", "closing")
CUE_DURATIONS = (18, 48, 58, 58, 28, 58, 40, 52, 18)


class DerivativeRulesLesson(ChapterScene):
    def sf(self, latex, y, x=0, tokens=None, size=38, width=12.2):
        obj = SemanticFormula(latex, tokens=tokens or {"statement": latex}, font_size=size)
        obj.set_color(INK)
        if obj.get_width() > width:
            obj.set_width(width)
        return obj.move_to([x, y, 0])

    def ready(self, identity):
        self.mark(identity+"_ready")
        self.focus_begin(identity)

    def driver(self, callback):
        obj = Group()
        obj.add_updater(callback)
        self._drivers.append(obj)
        self.add(obj)
        callback(obj)
        return obj

    def stop_drivers(self):
        for obj in self._drivers:
            obj.clear_updaters()
            self.remove(obj)
        self._drivers = []

    def opening(self):
        self.beat(.18, FadeIn(self.label("导数的运算法则", 0, 1.65, size=56)),
                  FadeIn(self.label("第03课", 0, 2.65, size=29, color=MUTED)))
        self.beat(.34, FadeIn(self.sf(r"x^2\sin x\qquad\frac{x^2+4}{x}", .25)))
        self.ready("opening_combinations")
        self.beat(.66, FadeIn(self.label("组合后的增量，从哪里来？", 0, -1.25, size=34)))
        self.ready("opening_increment")

    def linearity(self):
        first = self.sf(r"\Delta(u\pm v)=\Delta u\pm\Delta v", 2.35,
                        tokens={"du": r"\Delta u", "dv": r"\Delta v"})
        second = self.sf(r"\frac{\Delta(u\pm v)}h=\frac{\Delta u}h\pm\frac{\Delta v}h\to u'\pm v'", 1.10,
                         tokens={"du": r"\Delta u", "dv": r"\Delta v"}, size=35)
        self.beat(.12, FadeIn(first), FadeIn(self.label("u、v 在同一点可微；c 为常数", 0, 2.93, size=24)))
        self.ready("linear_increment")
        self.safe_formula(first, second, .27, pairs=("du", "dv"), stage="linear_divide_h")
        self.ready("linear_limit")
        third = self.sf(r"\Delta(cu)=c\Delta u\quad\Rightarrow\quad(cu)'=cu'", -.15, size=34)
        self.beat(.42, FadeIn(third))
        self.ready("linear_scalar")
        h = ValueTracker(.5)
        stems = [Line([x, -2.25, 0], [x, -1, 0], color=color, stroke_width=8)
                 for x, color in zip((-4.5, 0, 4.5), (CURVE, RATE, ACCENT))]
        labels = Group(*(self.sf(text, -2.72, x=x, size=29, width=3)
                         for x, text in ((-4.5, r"\Delta u"), (0, r"\Delta v"), (4.5, r"\Delta u+\Delta v"))))
        context = self.label("同一输入增量 h：u=x²，v=x，取 x=1", 0, -.88, size=26)

        def update(_):
            state = linear_state(1, float(h.get_value()))
            for line, x, key in zip(stems, (-4.5, 0, 4.5), ("du", "dv", "sum_increment")):
                line.put_start_and_end_on(np.array([x, -2.25, 0]),
                                         np.array([x, -2.25+.55*state[key], 0]))
            self.sample("linear_increments", **state)

        self.driver(update)
        self.beat(.56, FadeIn(Group(*stems, labels, context)))
        self.ready("linear_motion")
        self.beat(.88, h.animate.set_value(.05), rate_func=linear)
        self.focus_end("linear_motion")
        self.beat(.95)

    def area(self, initial=.6):
        h = ValueTracker(initial)
        p = lambda u, v: np.array([-6.1+.85*u, -1.65+.85*v, 0.])
        base = Polygon(p(0, 0), p(3, 0), p(3, 2), p(0, 2), color=MUTED, fill_opacity=.10)
        right, top, corner = [Polygon([0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                                      color=color, fill_opacity=.35, stroke_width=2)
                              for color in (RATE, CURVE, ACCENT)]
        labels = Group(self.sf("u=3", -2.05, x=-4.8, size=28, width=2.5),
                       self.sf("v=2", -.8, x=-6.55, size=26, width=.6),
                       self.sf("uv", -.8, x=-4.8, size=35, width=2),
                       self.label("x=1：u=2+x，v=1+x²", -3.85, 2.15, size=25, width=5.5))
        number = self.number(initial, decimals=2, size=28, color=ACCENT)
        read = Group(self.sf(r"h\approx", -2.65, x=-4.9, size=28, width=1.4), number)

        def update(_):
            s = product_state(1, float(h.get_value()))
            u, v, du, dv = s["u"], s["v"], s["du"], s["dv"]
            for obj, box in ((right, (u, 0, u+du, v)), (top, (0, v, u, v+dv)),
                             (corner, (u, v, u+du, v+dv))):
                x0, y0, x1, y1 = box
                obj.set_points_as_corners([p(x0, y0), p(x1, y0), p(x1, y1), p(x0, y1), p(x0, y0)])
            number.set_value(s["h"]).move_to([-3.7, -2.65, 0])
            self.sample("product_area", **s)

        self.driver(update)
        return Group(base, labels, read), right, top, corner, h

    def product_area(self):
        base, right, top, corner, h = self.area()
        self.beat(.12, FadeIn(base), FadeIn(self.sf(r"(u+\Delta u)(v+\Delta v)", 2.3, x=3.2, width=6.1, size=36)))
        self.ready("product_base")
        self.beat(.28, FadeIn(right), FadeIn(self.sf(r"v\,\Delta u", 1.20, x=3.2, width=6, size=38).set_color(RATE)))
        self.ready("product_right")
        self.beat(.44, FadeIn(top), FadeIn(self.sf(r"u\,\Delta v", .15, x=3.2, width=6, size=38).set_color(CURVE)))
        self.ready("product_top")
        self.beat(.60, FadeIn(corner), FadeIn(self.sf(r"\Delta u\,\Delta v", -.9, x=3.2, width=6, size=38).set_color(ACCENT)))
        self.ready("product_corner")
        self.beat(.77, FadeIn(self.sf(r"\Delta(uv)=v\Delta u+u\Delta v+\Delta u\Delta v", -2.1, x=2.6, width=7.8, size=31)))
        self.ready("product_exact_increment")

    def product_limit(self):
        base, right, top, corner, h = self.area()
        graph = Group(base, right, top, corner)
        self.beat(.13, FadeIn(graph), FadeIn(self.sf(r"\frac{\Delta(uv)}h=v\frac{\Delta u}h+u\frac{\Delta v}h+\frac{\Delta u}h\Delta v", 1.9, x=3.25, width=6.2, size=33)))
        self.ready("product_divided")
        self.beat(.27, FadeIn(self.sf(r"\Delta u/h\to u',\quad\Delta v/h\to v',\quad\Delta v\to0", .7, x=3.25, width=6.2, size=31)))
        self.ready("product_limits")
        corner_rate = self.number(product_quotient(1, .6)["corner_rate"], decimals=3, size=28, color=ACCENT)
        rate_label = self.sf(r"\Delta u\Delta v/h\approx", -.45, x=2.5, size=28, width=3.9)
        self.driver(lambda _: corner_rate.set_value(product_quotient(1, h.get_value())["corner_rate"]).move_to([5.15, -.45, 0]))
        self.beat(.38, FadeIn(rate_label), FadeIn(corner_rate))
        self.ready("product_corner_shrink")
        self.beat(.69, h.animate.set_value(.025), rate_func=linear)
        self.focus_end("product_corner_shrink")
        self.beat(.79, FadeIn(self.sf(r"(uv)'=u'v+uv'", -1.55, x=3.2, width=6.1, size=43)))
        self.ready("product_rule")
        self.beat(.91, FadeIn(self.label("同一点的 u、v；可微保证增量趋零", 2.5, -2.65, size=25, width=7.7)))

    def product_example(self):
        first = self.sf(r"f(x)=x^2\sin x\qquad(x\in\mathbb R,\ \mathrm{rad})", 2.0)
        second = self.sf(r"u=x^2,\quad u'=2x;\qquad v=\sin x,\quad v'=\cos x", .6, size=35)
        third = self.sf(r"f'(x)=2x\sin x+x^2\cos x", -.85, size=42)
        self.beat(.15, FadeIn(first))
        self.ready("product_example_factors")
        self.beat(.38, FadeIn(second))
        self.ready("product_example_derivatives")
        self.beat(.66, FadeIn(third))
        self.ready("product_example_result")
        self.beat(.84, FadeIn(self.label("每一项：一个因子的变化率 × 另一个因子的当前值", 0, -2.25, size=28)))

    def quotient_increment(self):
        rows = [self.sf(r"\Delta\!\left(\frac uv\right)=\frac{u+\Delta u}{v+\Delta v}-\frac uv", 2.2, size=38),
                self.sf(r"=\frac{v(u+\Delta u)-u(v+\Delta v)}{v(v+\Delta v)}", .8, size=38),
                self.sf(r"=\frac{v\Delta u-u\Delta v}{v(v+\Delta v)}", -.65, size=40),
                self.sf(r"v\ne0,\qquad v+\Delta v\ne0", -2.0, size=33)]
        self.beat(.13, FadeIn(rows[0]), FadeIn(rows[3]))
        self.ready("quotient_difference")
        self.beat(.33, FadeIn(rows[1]))
        self.ready("quotient_common_denominator")
        self.beat(.61, FadeIn(rows[2]))
        self.ready("quotient_cancel")
        self.beat(.82, FadeIn(self.label("分子：uv相消；分母：保留两次所在位置的分母", 0, -2.85, size=27)))

    def quotient_limit(self):
        first = self.sf(r"\frac{\Delta(u/v)}h=\frac{v(\Delta u/h)-u(\Delta v/h)}{v(v+\Delta v)}", 2.1, size=39)
        second = self.sf(r"\frac{\Delta u}h\to u',\quad\frac{\Delta v}h\to v',\quad\Delta v\to0", .65, size=36)
        third = self.sf(r"\left(\frac uv\right)'=\frac{u'v-uv'}{v^2}\qquad(v\ne0)", -.9, size=43)
        self.beat(.13, FadeIn(first))
        self.ready("quotient_divide_h")
        condition = self.label("u、v在同一点可微；v连续且非零，附近的分母也能保持非零", 0, -2.3, size=27)
        self.beat(.35, FadeIn(second), FadeIn(condition))
        self.ready("quotient_take_limit")
        self.beat(.63, FadeIn(third))
        self.ready("quotient_rule")
        self.beat(.84)

    def cost_example(self):
        context = self.label("连续产量模型：x 百件，C(x) 百元，A(x) 元/件", 0, 2.6, size=27)
        first = self.sf(r"C=x^2+4,\quad A=\frac{x^2+4}{x}\quad(x>0)", 1.65, x=3.2, width=6.1, size=32)
        second = self.sf(r"A'=\frac{2x\cdot x-(x^2+4)\cdot1}{x^2}", .45, x=3.2, width=6.1, size=35)
        third = self.sf(r"=1-\frac4{x^2}", -.75, x=3.2, width=6.1, size=42)
        self.beat(.12, FadeIn(context), FadeIn(first))
        self.ready("cost_model")
        self.beat(.25, FadeIn(second))
        self.ready("cost_substitute")
        self.beat(.37, FadeIn(third))
        self.ready("cost_derivative")
        p = lambda x, y: np.array([-6.0+1.33*(x-.5), -1.7+.60*(y-3.5), 0.])
        axes = Group(Line(p(.5, 3.5), p(4.45, 3.5), color=MUTED),
                     Line(p(.5, 3.5), p(.5, 8.5), color=MUTED),
                     self.sf("x", -2.05, x=-.55, size=25, width=.5),
                     self.sf("A", 1.55, x=-6.35, size=25, width=.5))
        for x in (1, 2, 3, 4):
            axes.add(self.sf(str(x), -2.05, x=p(x, 3.5)[0], size=25, width=.6))
        for y in (4, 6, 8):
            axes.add(self.sf(str(y), p(.5, y)[1], x=-6.35, size=25, width=.6))
        curve = VMobject().set_points_as_corners([p(x, average_cost_state(float(x))["average_cost"])
                                                for x in np.linspace(.55, 4.4, 150)]).set_stroke(CURVE, 3)
        a = ValueTracker(1)
        dot = Dot(color=ACCENT)
        tangent = Line([0, 0, 0], [1, 0, 0], color=ACCENT, stroke_width=3)
        read = self.number(-3, decimals=2, size=30, color=RATE)
        x_read = self.number(1, decimals=2, size=29, color=ACCENT)

        def update(_):
            s = average_cost_state(float(a.get_value()))
            x, y, slope = s["x"], s["average_cost"], s["derivative"]
            dot.move_to(p(x, y))
            tangent.put_start_and_end_on(p(x-.25, y-.25*slope), p(x+.25, y+.25*slope))
            read.set_value(slope).move_to([4.7, -1.9, 0])
            x_read.set_value(x).move_to([-3.1, -2.72, 0])
            self.sample("average_cost", **s, point=dot.get_center().tolist())

        self.driver(update)
        graph = Group(axes, curve, dot, tangent, read, x_read,
                      self.sf(r"A'(x)\approx", -1.9, x=2.5, size=30, width=2),
                      self.sf(r"x\approx", -2.72, x=-4.4, size=29, width=1.5))
        self.beat(.45, FadeIn(graph))
        self.ready("cost_decreasing")
        self.beat(.61, a.animate.set_value(2), rate_func=linear)
        self.focus_end("cost_decreasing")
        minimum = self.sf(r"x=2:\quad A=4,\quad A'=0", -2.75, x=3.1, size=29, width=6)
        self.beat(.68, FadeIn(minimum))
        self.ready("cost_stationary")
        self.beat(.75)
        self.focus_end("cost_stationary")
        self.beat(.78, FadeOut(minimum))
        self.ready("cost_increasing")
        self.beat(.95, a.animate.set_value(4), rate_func=linear)
        self.focus_end("cost_increasing")

    def closing(self):
        self.beat(.16, FadeIn(self.label("把组合拆回它的增量", 0, 1.8, size=43)))
        self.beat(.35, FadeIn(self.sf(r"(u+v)',\quad(cu)',\quad(uv)',\quad(u/v)'", .45, size=38)))
        self.ready("closing_rules")
        self.beat(.66, FadeIn(self.sf(r"\sin(x^2):\quad x\longmapsto x^2\longmapsto\sin(x^2)", -.85, size=38)),
                  FadeIn(self.label("输入先变一次，再传给外层：变化率怎样传递？", 0, -2.2, size=29)))
        self.ready("closing_chain")

    def construct(self):
        self._drivers = []
        if tuple(cue["id"] for cue in self.cues) != CUE_IDS:
            raise ValueError("This scene requires the chapter 03 cue order")
        for cue in self.cues:
            self.until(cue["start"])
            self.begin_chapter(cue)
            getattr(self, cue["id"])()
            self.end_chapter()
            self.stop_drivers()
