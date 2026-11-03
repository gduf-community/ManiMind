"""Chapter 02: a derivative function records the slopes of the original curve.

Pure model functions are independent of the visual clock. Trackers and drivers
belong to one cue, are written by this scene, consumed by geometry/readouts and
the motion journal, and expire at cue exit. No audio timing is asserted here.
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


def square_state(a):
    a = finite(a)
    return {"x": a, "value": a*a, "slope": 2*a}


def square_quotient(a, h):
    finite(a)
    if finite(h) == 0:
        raise ValueError("h must be nonzero")
    return 2*a+h


def constant_state(x, c=3):
    return {"x": finite(x), "value": finite(c), "slope": 0}


def constant_quotient(c, h):
    finite(c)
    if finite(h) == 0:
        raise ValueError("h must be nonzero")
    return 0


def identity_state(x):
    return {"x": finite(x), "value": x, "slope": 1}


def identity_quotient(x, h):
    finite(x)
    if finite(h) == 0:
        raise ValueError("h must be nonzero")
    return 1


def cubic_quotient(x, h):
    finite(x)
    if finite(h) == 0:
        raise ValueError("h must be nonzero")
    return 3*x*x+3*x*h+h*h


def integer_power_state(x, n):
    finite(x)
    if type(n) is not int:
        raise TypeError("The integer-power exponent must be an integer")
    if n == 0:
        return constant_state(x, 1)
    if n < 0 and x == 0:
        raise ValueError("Negative integer powers require x != 0")
    return {"x": x, "value": x**n, "slope": n*x**(n-1)}


def positive_power_state(x, n):
    finite(x)
    finite(n)
    if x <= 0:
        raise ValueError("Real-power formula here requires x > 0")
    return {"x": x, "value": x**n, "slope": n*x**(n-1)}


def reciprocal_quotient(x, h):
    finite(x)
    finite(h)
    if x == 0 or x+h == 0 or h == 0:
        raise ValueError("Require x != 0, x+h != 0 and h != 0")
    return -1/(x*(x+h))


def root_quotient(x, h):
    finite(x)
    finite(h)
    if x <= 0 or x+h < 0 or h == 0:
        raise ValueError("Require x > 0, x+h >= 0 and h != 0")
    return 1/(math.sqrt(x+h)+math.sqrt(x))


def basic_state(kind, x, base=math.e):
    finite(x)
    if kind == "square":
        return square_state(x)
    if kind == "constant":
        return constant_state(x)
    if kind == "identity":
        return identity_state(x)
    if kind == "cube":
        return integer_power_state(x, 3)
    if kind == "reciprocal":
        return integer_power_state(x, -1)
    if kind == "root":
        return positive_power_state(x, .5)
    if kind in ("exp", "log"):
        finite(base)
        if base <= 0 or (kind == "log" and base == 1):
            raise ValueError("Require base > 0; logarithms also require base != 1")
        if kind == "log" and x <= 0:
            raise ValueError("Logarithms require x > 0")
        value = base**x if kind == "exp" else math.log(x)/math.log(base)
        slope = value*math.log(base) if kind == "exp" else 1/(x*math.log(base))
    elif kind == "sin":
        value, slope = math.sin(x), math.cos(x)
    elif kind == "cos":
        value, slope = math.cos(x), -math.sin(x)
    else:
        raise ValueError("Unknown basic function")
    return {"x": x, "value": value, "slope": slope}


def panel_point(x, y, side, xr, yr):
    """Both panels have explicit axis units; slopes use mathematical coordinates."""
    left = -6.25 if side == 0 else .7
    return (left+5.5*(x-xr[0])/(xr[1]-xr[0]),
            -1.2+2.65*(y-yr[0])/(yr[1]-yr[0]), 0.)


_argv = sys.argv
try:
    sys.argv = _argv[:1]
    from manimlib import Dot, FadeIn, FadeOut, Group, Line, ValueTracker, VMobject, linear
    from manimind.components.formula_motion import SemanticFormula
    from derivative_chapter_shared import ChapterScene, INK, MUTED, CURVE, RATE, ACCENT
finally:
    sys.argv = _argv
del _argv


CUE_IDS = ("opening", "general", "constant", "identity", "power", "reciprocal", "root",
           "exponential", "logarithm", "sine", "cosine", "closing")
CUE_DURATIONS = (18, 52, 22, 18, 68, 46, 44, 44, 46, 44, 32, 18)


class DerivativeBasicsLesson(ChapterScene):
    def sf(self, latex, y, x=0, tokens=None, size=39, width=12.2):
        obj = SemanticFormula(latex, tokens=tokens or {"statement": latex}, font_size=size)
        obj.set_color(INK)
        if obj.get_width() > width:
            obj.set_width(width)
        return obj.move_to([x, y, 0])

    def ready(self, identity):
        self.mark(identity+"_ready")
        self.focus_begin(identity)

    def stop_drivers(self):
        for obj in self._drivers:
            obj.clear_updaters()
            self.remove(obj)
        self._drivers = []

    def pair(self, kind, xr, yr, dr, start, *, base=math.e, segments=None):
        tracker = ValueTracker(start)
        p = lambda x, y, side: np.array(panel_point(x, y, side, xr, yr if side == 0 else dr))
        axes = Group()
        for side, limits in enumerate((yr, dr)):
            zero_y = max(limits[0], min(0, limits[1]))
            zero_x = max(xr[0], min(0, xr[1]))
            axes.add(Line(p(xr[0], zero_y, side), p(xr[1], zero_y, side), color=MUTED),
                     Line(p(zero_x, limits[0], side), p(zero_x, limits[1], side), color=MUTED))
            for x in np.linspace(xr[0], xr[1], 5):
                axes.add(self.sf(f"{x:.2g}", -1.48, x=p(x, 0, side)[0], size=22, width=.8))
            for y in np.linspace(limits[0], limits[1], 3):
                axes.add(self.sf(f"{y:.2g}", p(0, y, side)[1],
                                 x=p(xr[0], y, side)[0]-.26, size=21, width=.45))
            axes.add(self.sf("x", -1.48, x=p(xr[1], 0, side)[0]+.28, size=24, width=.4))
        for lo, hi in segments or [xr]:
            xs = np.linspace(lo, hi, 140)
            for side, key, color in ((0, "value", CURVE), (1, "slope", RATE)):
                curve = VMobject().set_points_as_corners([
                    p(x, basic_state(kind, float(x), base)[key], side) for x in xs])
                axes.add(curve.set_stroke(color, 3))
        left_dot, right_dot = Dot(color=ACCENT), Dot(color=RATE)
        tangent = Line([0, 0, 0], [1, 0, 0], color=ACCENT, stroke_width=3)
        x_read = self.number(start, decimals=2, size=28, color=ACCENT)
        slope_read = self.number(basic_state(kind, start, base)["slope"], decimals=2, size=28, color=RATE)
        reads = Group(self.sf(r"a\approx", -1.98, x=-4.7, size=29, width=1.2),
                      x_read, self.sf(r"f'(a)\approx", -1.98, x=2.15, size=29, width=1.6), slope_read,
                      self.label("原函数：P处的切线", -3.5, 1.95, size=27, color=CURVE, width=5.5),
                      self.label("导函数：同一横坐标的高度", 3.4, 1.95, size=27, color=RATE, width=5.5))
        group = Group(axes, tangent, left_dot, right_dot, reads)

        def update(_):
            state = basic_state(kind, float(tracker.get_value()), base)
            x, y, slope = state["x"], state["value"], state["slope"]
            left_dot.move_to(p(x, y, 0))
            right_dot.move_to(p(x, slope, 1))
            dx = min(.35, .42*(yr[1]-yr[0])/max(abs(slope), .1))
            tangent.put_start_and_end_on(p(x-dx, y-slope*dx, 0), p(x+dx, y+slope*dx, 0))
            x_read.set_value(x).move_to([-3.4, -1.98, 0])
            slope_read.set_value(slope).move_to([3.7, -1.98, 0])
            self.sample("slope_map", function=kind, base=base, **state,
                        point=left_dot.get_center().tolist(), derivative_point=right_dot.get_center().tolist())

        driver = Group()
        driver.add_updater(update)
        self.add(driver)
        self._drivers.append(driver)
        update(driver)
        return group, tracker

    def opening(self):
        self.beat(.18, FadeIn(self.label("基本函数的导数", 0, 1.7, size=57)),
                  FadeIn(self.label("第02课", 0, 2.65, size=29, color=MUTED)))
        self.beat(.30, FadeIn(self.sf(r"f(x)=x^2,\qquad f'(2)=4", .25)))
        self.ready("opening_bridge")
        self.beat(.67, FadeIn(self.label("换一个点，斜率怎样跟着变？", 0, -1.2, size=34)))
        self.ready("opening_question")

    def general(self):
        rows = [self.sf(r"\frac{(a+h)^2-a^2}{h}", 2.25, tokens={"a": ("a", 0), "h": ("h", 0)}),
                self.sf(r"\frac{2ah+h^2}{h}", .95, tokens={"a": "a", "h": ("h", 0)}),
                self.sf(r"2a+h\ \longrightarrow\ 2a", -.35),
                self.sf(r"f'(a)=2a\quad\Rightarrow\quad f'(x)=2x", -1.65)]
        self.beat(.12, FadeIn(rows[0]), FadeIn(self.sf(r"h\ne0", 2.25, x=4.4, size=30, width=2)))
        self.ready("general_quotient")
        self.safe_formula(rows[0], rows[1], .24, pairs=("a", "h"), stage="square_expand")
        self.beat(.34, FadeIn(rows[2]))
        self.ready("general_limit")
        self.beat(.43, FadeIn(rows[3]))
        self.ready("general_function")
        self.beat(.52)
        for identity in ("general_quotient", "general_limit", "general_function"):
            self.focus_end(identity)
        old = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        self.beat(.57, *(FadeOut(obj) for obj in old))
        group, a = self.pair("square", (-2.4, 2.4), (-.5, 6), (-5, 5), -2)
        self.beat(.62, FadeIn(group), FadeIn(self.sf(r"x^2\quad\longmapsto\quad 2x", 2.8)))
        self.ready("general_map")
        self.beat(.76, a.animate.set_value(0), rate_func=linear)
        self.beat(.91, a.animate.set_value(2), rate_func=linear)
        self.focus_end("general_map")
        self.beat(.96, FadeIn(self.label("切线斜率成为右图的高度", 0, -2.72, size=28)))
        self.ready("general_map_result")

    def constant(self):
        graph, a = self.pair("constant", (-2.4, 2.4), (-1, 4), (-1, 1), -2)
        self.beat(.14, FadeIn(graph), FadeIn(self.sf(r"f(x)=c\qquad f'(x)=0", 2.65)))
        self.ready("constant_map")
        self.beat(.56, a.animate.set_value(2), rate_func=linear)
        self.focus_end("constant_map")
        self.beat(.68, FadeIn(self.sf(r"\frac{c-c}{h}=0\quad(h\ne0)", -2.72, size=34)))
        self.ready("constant_increment")

    def power(self):
        rows = [self.sf(r"\frac{(x+h)^3-x^3}{h}\quad(h\ne0)", 2.35, size=35),
                self.sf(r"\frac{3x^2h+3xh^2+h^3}{h}", 1.3, size=35),
                self.sf(r"3x^2+3xh+h^2\ \longrightarrow\ 3x^2", .25, size=35),
                self.sf(r"(x^n)'=nx^{n-1}\quad(n=1,2,3,\ldots;\ x\in\mathbb R)", -.85, size=33),
                self.sf(r"n=0:\ (1)'=0;\qquad n<0,\ n\in\mathbb Z:\ x\ne0", -1.8, size=30),
                self.label("实数幂先在 x > 0 使用；端点另查", 0, -2.65, size=29)]
        self.beat(.13, FadeIn(rows[0]))
        self.ready("power_cubic_expansion")
        self.beat(.24, FadeIn(rows[1]))
        self.beat(.34, FadeIn(rows[2]))
        self.ready("power_cubic_limit")
        self.beat(.46, FadeIn(rows[3]))
        self.beat(.54, FadeIn(rows[4]), FadeIn(rows[5]))
        self.ready("power_rule_domain")
        self.beat(.58)
        self.focus_end("power_cubic_expansion")
        self.focus_end("power_cubic_limit")
        self.focus_end("power_rule_domain")
        self.beat(.62, *(FadeOut(obj) for obj in rows))
        graph, a = self.pair("cube", (-1.5, 1.5), (-3.5, 3.5), (-.5, 7), -1.35)
        self.beat(.67, FadeIn(graph), FadeIn(self.sf(r"x^3\quad\longmapsto\quad3x^2", 2.7)))
        self.ready("power_cubic_map")
        self.beat(.80, a.animate.set_value(0), rate_func=linear)
        self.beat(.95, a.animate.set_value(1.35), rate_func=linear)
        self.focus_end("power_cubic_map")

    def identity(self):
        quotient = self.sf(r"\frac{(x+h)-x}{h}=\frac hh=1\quad(h\ne0)", 2.15, size=37)
        self.beat(.13, FadeIn(quotient))
        self.ready("identity_quotient")
        graph, a = self.pair("identity", (-2.4, 2.4), (-2.5, 2.5), (0, 2), -2)
        self.beat(.27)
        self.focus_end("identity_quotient")
        self.beat(.31, FadeOut(quotient))
        self.beat(.39, FadeIn(graph), FadeIn(self.sf(r"(x)'=1\qquad x\in\mathbb R", 2.65)))
        self.ready("identity_map")
        self.beat(.88, a.animate.set_value(2), rate_func=linear)
        self.focus_end("identity_map")

    def reciprocal(self):
        first = self.sf(r"\frac{1/(x+h)-1/x}{h}", 2.25, size=36)
        common = self.sf(r"=\frac{x-(x+h)}{h\,x(x+h)}=\frac{-h}{h\,x(x+h)}", .95, size=36)
        result = self.sf(r"=\frac{-1}{x(x+h)}\ \longrightarrow\ -\frac1{x^2}", -.4, size=37)
        condition = self.sf(r"x\ne0,\quad h\ne0,\quad x+h\ne0", -1.85, size=31)
        self.beat(.12, FadeIn(first), FadeIn(condition))
        self.ready("reciprocal_quotient")
        self.beat(.24, FadeIn(common))
        self.ready("reciprocal_common_denominator")
        self.beat(.36, FadeIn(result))
        self.ready("reciprocal_limit")
        self.beat(.48)
        self.focus_end("reciprocal_quotient")
        self.focus_end("reciprocal_common_denominator")
        self.focus_end("reciprocal_limit")
        self.beat(.53, FadeOut(first), FadeOut(common), FadeOut(result), FadeOut(condition))
        graph, a = self.pair("reciprocal", (-3, 3), (-2.5, 2.5), (-6, .5), -2.5,
                             segments=[(-3, -.45), (.45, 3)])
        self.beat(.58, FadeIn(graph), FadeIn(self.sf(r"1/x\quad\longmapsto\quad-1/x^2", 2.7)))
        self.ready("reciprocal_negative_branch")
        self.beat(.70, a.animate.set_value(-.65), rate_func=linear)
        self.focus_end("reciprocal_negative_branch")
        self.stop_drivers()
        self.beat(.74, FadeOut(graph))
        graph, a = self.pair("reciprocal", (-3, 3), (-2.5, 2.5), (-6, .5), .65,
                             segments=[(-3, -.45), (.45, 3)])
        self.beat(.78, FadeIn(graph))
        self.ready("reciprocal_positive_branch")
        self.beat(.94, a.animate.set_value(2.5), rate_func=linear)
        self.focus_end("reciprocal_positive_branch")

    def root(self):
        first = self.sf(r"\frac{\sqrt{x+h}-\sqrt x}{h}", 2.35, size=35)
        conjugate = self.sf(r"=\frac{(x+h)-x}{h(\sqrt{x+h}+\sqrt x)}", 1.1, size=35)
        result = self.sf(r"=\frac1{\sqrt{x+h}+\sqrt x}\ \longrightarrow\ \frac1{2\sqrt x}", -.25, size=35)
        condition = self.sf(r"x>0,\quad h\ne0,\quad x+h\ge0", -1.55, size=30)
        note = self.label("原函数 x ≥ 0；x = 0 没有有限的右侧斜率极限", 0, -2.65, size=27)
        self.beat(.12, FadeIn(first), FadeIn(condition))
        self.ready("root_rationalize")
        self.beat(.24, FadeIn(conjugate))
        self.ready("root_conjugate")
        self.beat(.36, FadeIn(result), FadeIn(note))
        self.ready("root_domain")
        self.beat(.49)
        self.focus_end("root_rationalize")
        self.focus_end("root_conjugate")
        self.focus_end("root_domain")
        self.beat(.54, FadeOut(first), FadeOut(conjugate), FadeOut(result), FadeOut(condition), FadeOut(note))
        graph, a = self.pair("root", (.04, 4), (0, 2.2), (0, 3), .09)
        self.beat(.59, FadeIn(graph), FadeIn(self.sf(r"\sqrt x\quad\longmapsto\quad1/(2\sqrt x)", 2.7)))
        self.ready("root_map")
        self.beat(.94, a.animate.set_value(3.7), rate_func=linear)
        self.focus_end("root_map")

    def exponential(self):
        f = self.sf(r"\frac{a^{x+h}-a^x}{h}=a^x\frac{a^h-1}{h}", 2.0)
        limit = self.sf(r"\lim_{h\to0}\frac{a^h-1}{h}=\ln a\quad(a>0)", .65)
        result = self.sf(r"(a^x)'=a^x\ln a;\quad(e^x)'=e^x;\quad x\in\mathbb R", -.8, size=36)
        self.beat(.14, FadeIn(f))
        self.ready("exp_factor")
        self.beat(.28, FadeIn(limit))
        self.ready("exp_standard_limit")
        self.beat(.41, FadeIn(result))
        self.ready("exp_rule")
        self.beat(.50)
        for identity in ("exp_factor", "exp_standard_limit", "exp_rule"):
            self.focus_end(identity)
        self.beat(.55, FadeOut(f), FadeOut(limit), FadeOut(result))
        graph, a = self.pair("exp", (-1.5, 1.5), (0, 5), (0, 5), -1.3)
        self.beat(.60, FadeIn(graph), FadeIn(self.sf(r"e^x\quad\longmapsto\quad e^x", 2.7)))
        self.ready("exp_map")
        self.beat(.90, a.animate.set_value(1.3), rate_func=linear)
        self.focus_end("exp_map")
        self.beat(.95, FadeIn(self.label("e为底：函数值与斜率数值相同；0<a<1 时斜率为负", 0, -2.72, size=26)))
        self.ready("exp_compare")

    def logarithm(self):
        graph, a = self.pair("log", (.2, 4), (-2, 2), (0, 5.5), .25)
        self.beat(.14, FadeIn(graph), FadeIn(self.sf(r"\ln x\quad\longmapsto\quad 1/x\quad(x>0)", 2.7)))
        self.ready("log_map")
        self.beat(.35, a.animate.set_value(3.7), rate_func=linear)
        self.focus_end("log_map")
        self.beat(.41, FadeIn(self.sf(r"\Delta x\approx x\,\Delta y\quad\Rightarrow\quad\Delta y/\Delta x\to1/x", -2.72, size=31)))
        self.ready("log_inverse")
        self.beat(.54)
        self.focus_end("log_inverse")
        self.stop_drivers()
        old = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        self.beat(.59, *(FadeOut(obj) for obj in old))
        self.beat(.66, FadeIn(self.sf(r"y=\ln x\quad\Longleftrightarrow\quad x=e^y", 2.15)),
                  FadeIn(self.sf(r"\log_a x=\frac{\ln x}{\ln a}", .85)))
        self.beat(.78, FadeIn(self.sf(r"(\log_a x)'=\frac1{x\ln a}", -.45)),
                  FadeIn(self.sf(r"x>0,\quad a>0,\quad a\ne1", -1.6, size=34)))
        self.ready("log_base")
        self.beat(.91, FadeIn(self.label("底大于1：递增；底在0与1之间：递减", 0, -2.65, size=29)))

    def sine(self):
        first = self.sf(r"\frac{\sin(x+h)-\sin x}{h}=\sin x\frac{\cos h-1}{h}+\cos x\frac{\sin h}{h}", 1.8, size=34)
        limits = self.sf(r"\frac{\sin h}{h}\to1,\quad\frac{\cos h-1}{h}\to0\quad(h\to0,\ \mathrm{radians})", .25, size=34)
        self.beat(.14, FadeIn(first))
        self.beat(.30, FadeIn(limits))
        self.ready("sine_limits")
        self.beat(.42)
        self.focus_end("sine_limits")
        self.beat(.48, FadeOut(first), FadeOut(limits))
        graph, a = self.pair("sin", (0, 2*math.pi), (-1.25, 1.25), (-1.25, 1.25), 0)
        self.beat(.54, FadeIn(graph), FadeIn(self.sf(r"(\sin x)'=\cos x\qquad x\in\mathbb R\ (\mathrm{rad})", 2.7, size=36)))
        self.ready("sine_map")
        self.beat(.68, a.animate.set_value(math.pi/2), rate_func=linear)
        self.beat(.79, a.animate.set_value(math.pi), rate_func=linear)
        self.beat(.94, a.animate.set_value(2*math.pi), rate_func=linear)
        self.focus_end("sine_map")

    def cosine(self):
        graph, a = self.pair("cos", (0, 2*math.pi), (-1.25, 1.25), (-1.25, 1.25), 0)
        self.beat(.14, FadeIn(graph), FadeIn(self.sf(r"(\cos x)'=-\sin x\qquad x\in\mathbb R\ (\mathrm{rad})", 2.7, size=36)))
        self.ready("cosine_map")
        self.beat(.38, a.animate.set_value(math.pi/2), rate_func=linear)
        self.beat(.55, a.animate.set_value(math.pi), rate_func=linear)
        self.beat(.80, a.animate.set_value(2*math.pi), rate_func=linear)
        self.focus_end("cosine_map")
        self.beat(.89, FadeIn(self.sf(r"-\sin x:\quad 0<x<\pi\Rightarrow f'<0;\quad\pi<x<2\pi\Rightarrow f'>0", -2.72, size=30)))
        self.ready("cosine_sign")

    def closing(self):
        self.beat(.15, FadeIn(self.label("导函数，记录每个位置的斜率", 0, 1.8, size=43)))
        self.beat(.31, FadeIn(self.sf(r"x\ \longmapsto\ f'(x)", .55)))
        self.ready("closing_summary")
        self.beat(.62, FadeIn(self.sf(r"x^2\sin x\ ?\qquad\frac{x^2}{x+1}\ ?", -.85)),
                  FadeIn(self.label("基本函数组合起来，怎样求导？", 0, -2.1, size=31)))
        self.ready("closing_combinations")

    def construct(self):
        self._drivers = []
        if tuple(cue["id"] for cue in self.cues) != CUE_IDS:
            raise ValueError("This scene requires the chapter 02 cue order")
        for cue in self.cues:
            self.until(cue["start"])
            self.begin_chapter(cue)
            getattr(self, cue["id"])()
            self.end_chapter()
            self.stop_drivers()
