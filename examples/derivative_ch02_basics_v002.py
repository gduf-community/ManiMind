"""Only the logarithm bridge changes; all other v001 chapters are inherited.

One cue-local input increment drives the two points, both increment segments
and their approximate readouts. This scene writes that state; geometry and the
motion journal consume it. Drivers expire before each phase is removed and at
cue exit. Any source, model, timing or text change invalidates derived evidence.
"""

import math
import sys

import numpy as np

from derivative_ch02_basics import DerivativeBasicsLesson, finite

_argv = sys.argv
try:
    sys.argv = _argv[:1]
    from manimlib import Dot, FadeIn, FadeOut, Group, Line, ValueTracker, VMobject, linear
finally:
    sys.argv = _argv
del _argv

from derivative_chapter_shared import INK, MUTED, CURVE, RATE, ACCENT


def log_increment_state(x, dx):
    x, dx = finite(x), finite(dx)
    if x <= 0 or x+dx <= 0 or dx == 0:
        raise ValueError("Require x > 0, x+dx > 0 and dx != 0")
    y = math.log(x)
    dy = math.log1p(dx/x)
    return {"x": x, "y": y, "dx": dx, "dy": dy,
            "end_x": x+dx, "end_y": y+dy,
            "inverse_rate": dx/dy, "forward_rate": dy/dx,
            "exp_rate": x*math.expm1(dy)/dy, "limit": 1/x}


def base_change_state(x, dx, a):
    a = finite(a)
    if a <= 0 or a == 1:
        raise ValueError("Require a > 0 and a != 1")
    state = log_increment_state(x, dx)
    k = 1/math.log(a)
    return {**state, "base": a, "k": k, "z": k*state["y"],
            "dz": k*state["dy"], "quotient": k*state["forward_rate"],
            "derivative": k/x}


def increment_point(x, y):
    return (-6.2+2.45*x, .15+1.7*y, 0.)


class DerivativeBasicsLessonV002(DerivativeBasicsLesson):
    def increment_diagram(self):
        dx = ValueTracker(.8)
        p = lambda x, y: np.array(increment_point(x, y))
        axes = Group(Line(p(0, 0), p(2.1, 0), color=MUTED),
                     Line(p(0, -.6), p(0, 1.0), color=MUTED),
                     self.sf("x", -.12, x=-.78, size=24, width=.4),
                     self.sf("y", 2.03, x=-6.2, size=24, width=.4),
                     self.sf("0", -.15, x=-6.42, size=23, width=.4),
                     self.sf("1", -.14, x=p(1, 0)[0], size=23, width=.4),
                     self.sf("2", -.14, x=p(2, 0)[0], size=23, width=.4))
        curve = VMobject().set_points_as_corners([
            p(float(x), math.log(float(x))) for x in np.linspace(.75, 2.05, 100)
        ]).set_stroke(CURVE, 3)
        initial = log_increment_state(1, .8)
        point = Dot(p(1, 0), color=INK, radius=.06)
        other = Dot(p(initial["end_x"], initial["end_y"]), color=ACCENT, radius=.06)
        horizontal = Line(p(1, 0), p(1.8, 0), color=ACCENT, stroke_width=4)
        vertical = Line(p(1.8, 0), p(initial["end_x"], initial["end_y"]), color=CURVE, stroke_width=4)
        dx_read = self.number(.8, decimals=3, size=26, color=ACCENT)
        dy_read = self.number(initial["dy"], decimals=3, size=26, color=CURVE)
        labels = Group(self.label("示例：P=(1,0)，另一点沿 ln x 移动", -3.1, 1.92, size=24, width=4.9),
                       self.label("水平段 Δx；竖直段 Δy", -3.4, -1.45, size=25, width=5.4),
                       self.sf(r"\Delta x\approx", -2.12, x=-5.2, size=26, width=1.4), dx_read,
                       self.sf(r"\Delta y\approx", -2.12, x=-2.7, size=26, width=1.4), dy_read)
        graph = Group(axes, curve, point, other, horizontal, vertical, labels)

        def update(_):
            state = log_increment_state(1, float(dx.get_value()))
            other.move_to(p(state["end_x"], state["end_y"]))
            horizontal.put_start_and_end_on(p(state["x"], state["y"]), p(state["end_x"], state["y"]))
            vertical.put_start_and_end_on(p(state["end_x"], state["y"]), p(state["end_x"], state["end_y"]))
            dx_read.set_value(state["dx"]).move_to([-4.05, -2.12, 0])
            dy_read.set_value(state["dy"]).move_to([-1.52, -2.12, 0])
            self.sample("log_increment_bridge", **state,
                        point=point.get_center().tolist(), other=other.get_center().tolist(),
                        horizontal=horizontal.get_end().tolist(), vertical=vertical.get_end().tolist())

        driver = Group()
        driver.add_updater(update)
        self._drivers.append(driver)
        self.add(driver)
        update(driver)
        return graph, dx

    def clear_log_phase(self, fraction):
        if self._open_focus:
            raise ValueError("Close disappearing logarithm referents before clearing")
        self.stop_drivers()
        old = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        self.beat(fraction, *(FadeOut(obj) for obj in old))

    def logarithm(self):
        relation = self.sf(r"y=\ln x\quad\Longleftrightarrow\quad x=e^y", 2.65, size=36)
        condition = self.sf(r"x>0,\quad\Delta x\ne0,\quad x+\Delta x>0", -2.85, size=28)
        self.beat(.10, FadeIn(relation), FadeIn(condition))
        self.ready("log_variables")

        graph, dx = self.increment_diagram()
        dy = self.sf(r"\Delta y=\ln(x+\Delta x)-y", 1.8, x=3.3, width=6.0, size=32)
        endpoint = self.sf(r"x+\Delta x=e^{y+\Delta y}", .8, x=3.3, width=6.0, size=34)
        self.beat(.16, FadeIn(graph), FadeIn(dy), FadeIn(endpoint))
        self.ready("log_increments")
        increment = self.sf(r"\Delta x=e^y(e^{\Delta y}-1)=x(e^{\Delta y}-1)", -.25, x=3.3, width=6.0, size=30)
        nonzero = self.sf(r"\Delta x\ne0\ \Rightarrow\ \Delta y\ne0", -.8, x=-3.4, width=5.5, size=28)
        self.beat(.22, FadeIn(increment), FadeIn(nonzero))
        self.ready("log_exp_increment")
        self.beat(.27)
        self.ready("log_increment_motion")
        self.beat(.36, dx.animate.set_value(.08), rate_func=linear)
        self.focus_end("log_increment_motion")
        self.beat(.38, FadeOut(nonzero))

        exp_rate = self.sf(r"\frac{\Delta x}{\Delta y}=x\frac{e^{\Delta y}-1}{\Delta y}\longrightarrow x", -1.47, x=3.3, width=6.0, size=32)
        continuity = self.sf(r"\Delta x\to0\ \Rightarrow\ \Delta y\to0", -.8, x=-3.4, width=5.5, size=28)
        self.beat(.40, FadeIn(exp_rate), FadeIn(continuity))
        self.ready("log_exp_rate")
        self.beat(.43)
        self.focus_end("log_increments")
        self.beat(.45, FadeOut(dy), FadeOut(endpoint))
        inverse = self.sf(r"\frac{\Delta y}{\Delta x}\to\frac1x,\qquad(\ln x)'=\frac1x", 1.25, x=3.3, width=6.0, size=34)
        self.beat(.48, FadeIn(inverse))
        self.ready("log_inverse_limit")
        self.beat(.51)
        for identity in ("log_variables", "log_exp_increment", "log_exp_rate", "log_inverse_limit"):
            self.focus_end(identity)
        self.clear_log_phase(.53)

        pair, a = self.pair("log", (.2, 4), (-2, 2), (0, 5.5), .25)
        self.beat(.56, FadeIn(pair), FadeIn(self.sf(r"\ln x\quad\longmapsto\quad1/x\quad(x>0)", 2.7)))
        self.ready("log_map")
        self.beat(.67, a.animate.set_value(3.7), rate_func=linear)
        self.focus_end("log_map")
        self.clear_log_phase(.70)

        base = self.sf(r"k=\frac1{\ln a}\quad\text{(constant)},\qquad x>0,\ a>0,\ a\ne1", 2.65, size=32)
        z = self.sf(r"z=\log_a x=\frac{\ln x}{\ln a}=k\ln x", 1.55, size=36)
        self.beat(.73, FadeIn(base), FadeIn(z))
        self.ready("log_base_definition")
        dz = self.sf(r"\Delta z=k\ln(x+\Delta x)-k\ln x=k\Delta y", .4, size=35)
        self.beat(.80, FadeIn(dz))
        self.ready("log_base_increment")
        quotient = self.sf(r"\frac{\Delta z}{\Delta x}=k\frac{\Delta y}{\Delta x}\longrightarrow k\frac1x", -.75, size=38)
        self.beat(.86, FadeIn(quotient))
        self.ready("log_base_quotient")
        result = self.sf(r"(\log_a x)'=\frac1{x\ln a}", -1.9, x=-3.2, size=38, width=6.1)
        example = self.sf(r"a=2,\ x=2:\quad z'=\frac1{2\ln2}", -1.9, x=3.3, size=32, width=6.1)
        self.beat(.92, FadeIn(result), FadeIn(example))
        self.ready("log_base_derivative")
        self.beat(.96, FadeIn(self.label("a>1 时斜率为正；0<a<1 时斜率为负", 0, -2.85, size=27)))
        self.ready("log_base_sign")
