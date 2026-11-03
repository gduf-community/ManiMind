"""New first derivative lesson: native geometry, semantic algebra, silent cues."""

import json
import math
from numbers import Real
import sys

import numpy as np


def finite_real(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("A real numeric value is required")
    if not math.isfinite(value):
        raise ValueError("Values must be finite")
    return value


def square(x):
    return finite_real(x) ** 2


def increments(h, base=2):
    finite_real(h)
    finite_real(base)
    return h, 2 * base * h + h * h


def difference_quotient(h, base=2):
    """Stable reduced quotient of x^2, with the original nonzero domain."""
    finite_real(h)
    finite_real(base)
    if h == 0:
        raise ValueError("A difference quotient requires h != 0")
    return 2 * base + h


def two_sided_rates(radius, base=2):
    if finite_real(radius) <= 0:
        raise ValueError("The two-sided radius must be positive")
    return difference_quotient(radius, base), difference_quotient(-radius, base)


def tangent_value(x, base=2):
    finite_real(x)
    finite_real(base)
    return base * base + 2 * base * (x - base)


def local_prediction(h, base=2):
    finite_real(h)
    finite_real(base)
    return base * base + 2 * base * h


def approximation_remainder(h):
    return finite_real(h) ** 2


def plot_point(x, y, local=False):
    finite_real(x)
    finite_real(y)
    if local:
        return (-3.3 + 5.4 * (x - 2), -.5 + 1.25 * (y - 4), 0.)
    return (-6.1 + 2.15 * x, -2.5 + .46 * y, 0.)


# The native library parses argv on import, including a host pytest invocation.
_host_argv = sys.argv
try:
    sys.argv = _host_argv[:1]
    from manimlib import (
        Circle, Dot, FadeIn, FadeOut, Group, Line, ShowCreation,
        ValueTracker, VGroup, VMobject, linear,
    )
    from manimind.components.formula_motion import SemanticFormula, matching_transform
    from manimind.experiments.understanding_support import UnderstandingScene
finally:
    sys.argv = _host_argv
del _host_argv


INK = "#EEF1F4"
MUTED = "#A5AFB3"
CURVE = "#58CFA9"
H_COLOR = "#F1CD68"
DERIVATIVE = "#F08D85"
BG = "#101416"
CUE_IDS = ("opening", "average", "approach", "algebra", "both_sides",
           "definition", "tangent_prediction", "closing")
CUE_DURATIONS = (22, 34, 42, 74, 36, 34, 44, 18)
STAGE_TIMES = {
    "opening": {"0.10": 2.2, "0.46": 10.12, "0.60": 13.2},
    "average": {"0.04": 1.36, "0.08": 2.72, "0.14": 4.76, "0.32": 10.88,
                "0.38": 12.92, "0.44": 14.96, "0.64": 21.76, "0.74": 25.16},
    "approach": {"0.04": 1.68, "0.08": 3.36, "0.12": 5.04, "0.24": 10.08,
                 "0.52": 21.84, "0.58": 24.36, "0.80": 33.6},
    "algebra": {"0.04": 2.96, "0.08": 5.92, "0.10": 7.4, "0.20": 14.8,
                "0.26": 19.24, "0.36": 26.64, "0.42": 31.08, "0.51": 37.74,
                "0.58": 42.92, "0.68": 50.32, "0.73": 54.02, "0.83": 61.42, "0.89": 65.86},
    "both_sides": {"0.04": 1.44, "0.08": 2.88, "0.12": 4.32, "0.34": 12.24,
                   "0.55": 19.8, "0.72": 25.92, "0.78": 28.08},
    "definition": {"0.04": 1.36, "0.08": 2.72, "0.12": 4.08, "0.50": 17, "0.60": 20.4},
    "tangent_prediction": {"0.04": 1.76, "0.08": 3.52, "0.12": 5.28, "0.32": 14.08,
                           "0.42": 18.48, "0.72": 31.68, "0.78": 34.32, "0.80": 35.2},
    "closing": {"0.04": .72, "0.08": 1.44, "0.14": 2.52, "0.53": 9.54, "0.62": 11.16},
}
ALGEBRA = (
    ("substitution", r"\frac{(2+h)^2-4}{h}",
     {"base": ("2", 0), "power": ("2", 1), "sub_four": "4",
      "h_primary": ("h", 0), "h_den": ("h", 1)}),
    ("expanded", r"\frac{4+4h+h^2-4}{h}",
     {"base_four": ("4", 0), "coefficient": ("4", 1), "sub_four": ("4", 2),
      "h_primary": ("h", 0), "h_extra": ("h", 1), "h_den": ("h", 2), "power": "2"}),
    ("combined", r"\frac{4h+h^2}{h}",
     {"coefficient": "4", "h_primary": ("h", 0), "h_extra": ("h", 1),
      "h_den": ("h", 2), "power": "2"}),
    ("factored", r"\frac{h(4+h)}{h}",
     {"h_primary": ("h", 0), "coefficient": "4", "h_extra": ("h", 1), "h_den": ("h", 2)}),
    ("simplified", r"4+h", {"coefficient": "4", "h_extra": "h"}),
)


def path(points, color=CURVE, width=4):
    return VMobject().set_points_as_corners(points).set_stroke(color, width)


class DerivativeIntroLesson(UnderstandingScene):
    def put(self, latex, x, y, size=40, color=INK, width=5.1):
        result = self.formula(latex, size=size, color=color)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def label(self, text, x, y, size=30, color=INK, width=12.6):
        result = self.cn(text, size=size, color=color)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def stage_time(self, fraction):
        if fraction == 1:
            offset = self._cue["duration"]
        else:
            key = f"{fraction:.2f}"
            default = STAGE_TIMES[self._cue["id"]].get(key, fraction * self._cue["duration"])
            offset = self._cue.get("stage_times", {}).get(key, default)
        if not 0 <= offset <= self._cue["duration"]:
            raise ValueError("Local stage time must stay inside its actual cue")
        return self._cue["start"] + offset

    def beat(self, fraction, *animations, **kwargs):
        self.until(self.stage_time(fraction), *animations, **kwargs)

    def begin_chapter(self, cue):
        self._cue = cue
        objects = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        for obj in objects:
            obj.clear_updaters()
        if objects:
            self.beat(.04, *(FadeOut(obj) for obj in objects))
        else:
            self.beat(.04)
        self.beat(.08, FadeIn(self.label(cue["heading"], 0, 3.35, size=39)))

    def sample(self, kind, **values):
        self.motion_samples.append({"kind": kind, "time": float(self.get_time()), **values})

    def graph(self, local=False):
        p = lambda x, y: np.array(plot_point(x, y, local))
        if local:
            guides = VGroup(Line(p(1.45, 4), p(2.55, 4)),
                            Line(p(2, 2.5), p(2, 6.3))).set_stroke(MUTED, 1.5)
            ticks = Group(*(self.put(str(x), *p(x, 2.35)[:2], size=25, width=1)
                            for x in (1.6, 1.8, 2, 2.2, 2.4)),
                          self.put("4", -6.45, -.5, size=26),
                          self.label("P附近的坐标放大图", -3.3, 2.55, size=25, color=MUTED, width=6))
            xs = np.linspace(1.55, 2.5, 120)
        else:
            guides = VGroup(Line(p(0, 0), p(3.2, 0)),
                            Line(p(0, 0), p(0, 10.5))).set_stroke(MUTED, 1.8)
            ticks = Group(*(self.put(str(x), *p(x, -.4)[:2], size=26, width=.7)
                            for x in (0, 1, 2, 3)),
                          *(self.put(str(y), *p(-.15, y)[:2], size=26, width=.7)
                            for y in (4, 8)),
                          self.put("x", *p(3.3, 0)[:2], size=28, width=.5),
                          self.put("y", *p(0, 10.9)[:2], size=28, width=.5))
            xs = np.linspace(0, 3.12, 140)
        curve = path([p(x, square(x)) for x in xs])
        point = Circle(radius=.10, stroke_color=INK, stroke_width=2.5).move_to(p(2, 4))
        point_name = self.put("P=(2,4)", *(p(2, 4) + [-.85, -.43, 0])[:2], size=29, width=2.3)
        return Group(guides, ticks, curve, point, point_name)

    def secant_line(self, h, color=H_COLOR):
        slope = difference_quotient(h)
        return Line(plot_point(1.25, 4 + slope * (1.25 - 2)),
                    plot_point(3.1, 4 + slope * (3.1 - 2)), color=color, stroke_width=3.5)

    def increment_lines(self, h):
        _, dy = increments(h)
        return VGroup(Line(plot_point(2, 4), plot_point(2 + h, 4),
                           color=H_COLOR, stroke_width=4.5),
                      Line(plot_point(2 + h, 4), plot_point(2 + h, 4 + dy),
                           color=CURVE, stroke_width=4.5))

    def opening(self, cue):
        self._cue = cue
        title = self.label("导数入门", 0, 1.65, size=62)
        question = self.label("曲线上，一个点有多陡？", 0, .4, size=38)
        self.beat(.10, FadeIn(title), FadeIn(question))
        self.mark("opening_title_ready")
        self.focus_begin("opening_question")
        self.beat(.46)
        self.focus_end("opening_question")
        self.beat(.60, title.animate.scale(.66).move_to([0, 3.35, 0]),
                  FadeOut(question), FadeIn(self.graph()),
                  FadeIn(self.put(r"f(x)=x^2", 3.8, 1.5, size=48)),
                  FadeIn(self.label("x = 2 附近，变化有多快？", 3.8, .25, size=30, width=5.2)))
        self.mark("opening_point_ready")
        self.focus_begin("opening_point")
        self.beat(1)
        self.focus_end("opening_point")

    def average(self, cue):
        self.begin_chapter(cue)
        q = Dot(plot_point(3, 9), radius=.075, color=H_COLOR)
        name = self.put("Q=(3,9)", -.15, 2.18, size=28, color=H_COLOR, width=2.5)
        function = self.put(r"Q=(2+h,\ f(2+h))", 3.8, 2.25, size=36, color=H_COLOR)
        self.beat(.14, FadeIn(self.graph()), FadeIn(q), FadeIn(name),
                  ShowCreation(self.secant_line(1)), FadeIn(function))
        self.mark("interval_points_ready")
        self.focus_begin("interval_points")
        self.beat(.32)
        self.focus_end("interval_points")
        triangle = self.increment_lines(1)
        dx = self.put(r"\Delta x=h=1", 3.8, 1.15, size=38, color=H_COLOR)
        dy = self.put(r"\Delta y=f(2+h)-4=5", 3.8, .20, size=37, color=CURVE)
        self.beat(.38, ShowCreation(triangle[0]), FadeIn(dx))
        self.beat(.44, ShowCreation(triangle[1]), FadeIn(dy))
        self.mark("increments_ready")
        self.focus_begin("signed_increments")
        self.beat(.64)
        self.focus_end("signed_increments")
        rate = self.put(r"m=\frac{\Delta y}{\Delta x}=\frac{f(2+h)-4}{h}=5", 3.8, -1.15, size=40)
        self.beat(.74, FadeIn(rate),
                  FadeIn(self.label("区间平均变化率 · 割线斜率", 3.8, -2.2, size=27, width=5.4)))
        self.mark("average_quotient_ready")
        self.focus_begin("average_quotient")
        self.beat(1)
        self.focus_end("average_quotient")

    def approach(self, cue):
        self.begin_chapter(cue)
        h = ValueTracker(1)
        q = Dot(plot_point(3, 9), radius=.075, color=H_COLOR)
        secant, triangle = self.secant_line(1), self.increment_lines(1)
        hv = self.number(1, size=42, decimals=2, color=H_COLOR).move_to([4.9, .45, 0])
        mv = self.number(5, size=42, decimals=2).move_to([4.9, -.7, 0])
        self.beat(.12, FadeIn(self.graph()), FadeIn(q), ShowCreation(secant), FadeIn(triangle),
                  FadeIn(self.put(r"Q=(2+h,(2+h)^2)", 3.8, 2.20, size=36, color=H_COLOR)),
                  FadeIn(self.put(r"\Delta x=h", 2.8, .45, size=38, color=H_COLOR)), FadeIn(hv),
                  FadeIn(self.put(r"\frac{\Delta y}{\Delta x}=", 2.8, -.7, size=40)), FadeIn(mv),
                  FadeIn(self.put(r"\Delta y=(2+h)^2-4", 3.8, -1.8, size=35, color=CURVE)))
        self.mark("approach_setup_ready")
        self.focus_begin("approach_setup")
        self.beat(.24)
        self.focus_end("approach_setup")
        driver = Group()

        def update(_):
            value = h.get_value()
            q.move_to(plot_point(2 + value, square(2 + value)))
            secant.become(self.secant_line(value))
            triangle.become(self.increment_lines(value))
            hv.set_value(value)
            mv.set_value(difference_quotient(value))
            self.sample("approach", h=value, slope=difference_quotient(value),
                        delta_y=increments(value)[1], q=q.get_center().tolist())

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("right_approach")
        self.beat(.52, h.animate.set_value(.1), rate_func=linear)
        self.mark("approach_motion_mid")
        self.beat(.58)
        self.beat(.80, h.animate.set_value(.02), rate_func=linear)
        self.mark("approach_near_ready")
        self.focus_end("right_approach")
        self.focus_begin("near_rate")
        self.beat(1)
        self.focus_end("near_rate")
        driver.clear_updaters()

    def algebra(self, cue):
        self.begin_chapter(cue)
        p = lambda x, y: [-5.5 + 1.2 * (x - 2), 1.1 + .36 * (y - 4), 0]
        diagram = VGroup(path([p(x, square(x)) for x in np.linspace(1.7, 2.8, 50)]),
                         Line(p(2, 4), p(2.7, 4), color=H_COLOR, stroke_width=4),
                         Line(p(2.7, 4), p(2.7, square(2.7)), color=CURVE, stroke_width=4),
                         Dot(p(2, 4), color=INK), Dot(p(2.7, square(2.7)), color=H_COLOR))
        small = Group(diagram, self.put("h", -5.1, .8, size=29, color=H_COLOR),
                      self.put(r"\Delta y", -4.2, 1.6, size=29, color=CURVE))
        quotient = self.put(r"m=\frac{\Delta y}{\Delta x}=\frac{f(2+h)-4}{h}",
                            1.8, 1.85, size=37, width=7)
        current = self.algebra_formula(0)
        self.beat(.10, FadeIn(small), FadeIn(quotient), FadeIn(current))
        self.mark("substitution_ready")
        self.focus_begin("quotient_substitution")
        self.beat(.20)
        self.focus_end("quotient_substitution")
        for index, end, hold, focus in (
            (1, .26, .36, "expanded_terms"),
            (2, .42, .51, "combined_terms"),
            (3, .58, .68, "factored_h"),
        ):
            current = self.move_formula(current, index, end)
            self.mark(ALGEBRA[index][0] + "_ready")
            self.focus_begin(focus)
            self.beat(hold)
            self.focus_end(focus)
        condition = self.put(r"h\ne0", 0, -1.85, size=40, color=H_COLOR)
        explanation = self.label("P、Q 仍是两个不同的点", 0, -2.6, size=28, color=MUTED)
        strikes = VGroup(*(Line(current.tag(key).get_corner(np.array([-1, -1, 0])),
                                current.tag(key).get_corner(np.array([1, 1, 0])),
                                color=DERIVATIVE, stroke_width=4)
                            for key in ("h_primary", "h_den")))
        self.beat(.73, FadeIn(condition), FadeIn(explanation), ShowCreation(strikes))
        self.mark("cancellation_condition_ready")
        self.focus_begin("nonzero_cancel")
        self.beat(.83)
        self.focus_end("nonzero_cancel")
        self.remove(strikes)
        self.move_formula(current, 4, .89)
        self.mark("simplified_ready")
        self.focus_begin("simplified_rate")
        self.beat(1)
        self.focus_end("simplified_rate")

    def algebra_formula(self, index):
        _, latex, tokens = ALGEBRA[index]
        colors = {key: H_COLOR for key in tokens if key.startswith("h_")}
        if "coefficient" in tokens:
            colors["coefficient"] = DERIVATIVE
        result = SemanticFormula(latex, tokens=tokens, colors=colors, font_size=66).set_color(INK)
        for key, color in colors.items():
            result.tag(key).set_color(color)
        return result.move_to([0, -.25, 0])

    def move_formula(self, current, index, end):
        target = self.algebra_formula(index)
        start = float(self.get_time())
        driver = Group()

        def update(_):
            self.sample("symbols", stage=ALGEBRA[index][0],
                        centers={key: current.tag(key).get_center().tolist() for key in current.semantic_ids})

        driver.add_updater(update)
        self.add(driver)
        duration = (round(self.stage_time(end) * self.camera.fps)
                    - round(start * self.camera.fps)) / self.camera.fps
        self.beat(end, matching_transform(current, target, run_time=duration,
                                         path_arc=.18, unmatched_in_place=True))
        driver.clear_updaters()
        self.remove(driver)
        self.symbol_transitions.append({"stage": ALGEBRA[index][0], "start": start,
                                        "end": float(self.get_time()),
                                        "source": current.get_tex(), "target": ALGEBRA[index][1]})
        return target

    def both_sides(self, cue):
        self.begin_chapter(cue)
        radius = ValueTracker(.8)
        qr = Dot(plot_point(2.8, square(2.8)), color=H_COLOR, radius=.075)
        ql = Dot(plot_point(1.2, square(1.2)), color=H_COLOR, radius=.075)
        sr, sl = self.secant_line(.8), self.secant_line(-.8)
        columns = (1.9, 3.75, 5.65)
        heading = Group(*(self.put(tex, x, 1.35, size=33, color=color, width=1.3)
                          for tex, x, color in zip(("h", r"\Delta y", "m"), columns,
                                                   (H_COLOR, CURVE, INK))))
        values, rows = [], Group()
        for sign, y in ((1, .5), (-1, -.5)):
            row = [self.number(value, size=34, decimals=2, color=color).move_to([x, y, 0])
                   for value, x, color in zip((sign * .8, increments(sign * .8)[1],
                                               difference_quotient(sign * .8)), columns,
                                              (H_COLOR, CURVE, INK))]
            values.append(row)
            rows.add(*row)
        self.beat(.12, FadeIn(self.graph()), FadeIn(qr), FadeIn(ql),
                  ShowCreation(sr), ShowCreation(sl), FadeIn(heading), FadeIn(rows),
                  FadeIn(self.put("m(h)=4+h", 3.8, 2.3, size=41)))
        self.mark("two_sides_ready")
        self.focus_begin("two_sided_start")
        self.beat(.34)
        self.focus_end("two_sided_start")
        driver = Group()

        def update(_):
            r = radius.get_value()
            for sign, point, secant, row in ((1, qr, sr, values[0]), (-1, ql, sl, values[1])):
                h = sign * r
                point.move_to(plot_point(2 + h, square(2 + h)))
                secant.become(self.secant_line(h))
                for number, value in zip(row, (h, increments(h)[1], difference_quotient(h))):
                    number.set_value(value)
            self.sample("two_sides", radius=r, right=two_sided_rates(r)[0], left=two_sided_rates(r)[1],
                        right_dy=increments(r)[1], left_dy=increments(-r)[1],
                        qr=qr.get_center().tolist(), ql=ql.get_center().tolist())

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("two_sided_motion")
        self.beat(.55, radius.animate.set_value(.1), rate_func=linear)
        self.mark("two_sides_mid")
        self.beat(.72, radius.animate.set_value(.02), rate_func=linear)
        self.mark("two_sides_near")
        self.focus_end("two_sided_motion")
        driver.clear_updaters()
        self.beat(.78, FadeIn(self.put(r"h\to0\quad\Longrightarrow\quad4+h\to4", 3.8, -1.65,
                                     size=36, color=DERIVATIVE)),
                  FadeIn(self.put(r"|m(h)-4|=|h|", 3.8, -2.6, size=34)))
        self.mark("common_limit_ready")
        self.focus_begin("common_four")
        self.beat(1)
        self.focus_end("common_four")

    def definition(self, cue):
        self.begin_chapter(cue)
        height = self.put(r"f(2)=4", -4.5, 1.95, size=35)
        value = self.label("函数值：P 的纵坐标", -.4, 1.95, size=29, color=MUTED)
        specific = SemanticFormula(r"f'(2)=\lim_{h\to0}\frac{f(2+h)-f(2)}{h}=4",
            tokens={"position": ("2", 0), "position_q": ("2", 1), "position_p": ("2", 2),
                    "h_limit": ("h", 0), "h_num": ("h", 1), "h_den": ("h", 2)}, font_size=49)
        specific.move_to([0, .25, 0])
        self.beat(.12, FadeIn(height), FadeIn(value), FadeIn(specific),
                  FadeIn(self.label("本点变化率", 0, -1.15, size=31, color=DERIVATIVE)))
        self.mark("derivative_value_ready")
        self.focus_begin("derivative_at_two")
        self.beat(.50)
        self.focus_end("derivative_at_two")
        general = SemanticFormula(r"f'(a)=\lim_{h\to0}\frac{f(a+h)-f(a)}{h}",
            tokens={"position": ("a", 0), "position_q": ("a", 1), "position_p": ("a", 2),
                    "h_limit": ("h", 0), "h_num": ("h", 1), "h_den": ("h", 2)}, font_size=49)
        general.move_to([0, .25, 0])
        self.beat(.60, matching_transform(specific, general, run_time=cue["duration"] * .10,
                                          unmatched_in_place=True, path_arc=.12),
                  FadeOut(height), FadeOut(value),
                  FadeIn(self.label("a 附近有定义，双侧极限存在且有限", 0, -2.3, size=29, color=MUTED)))
        self.mark("definition_pattern_ready")
        self.focus_begin("definition_pattern")
        self.beat(1)
        self.focus_end("definition_pattern")

    def tangent_prediction(self, cue):
        self.begin_chapter(cue)
        tangent = Line(plot_point(1.63, tangent_value(1.63), True),
                       plot_point(2.45, tangent_value(2.45), True), color=DERIVATIVE, stroke_width=3.5)
        tangent_text = self.put(r"y=4+4(x-2)", 3.8, 2.2, size=41, color=DERIVATIVE)
        self.beat(.12, FadeIn(self.graph(local=True)), ShowCreation(tangent), FadeIn(tangent_text),
                  FadeIn(self.label("P 处的切线斜率：4", 3.8, 1.35, size=29, color=DERIVATIVE, width=5.2)))
        self.mark("tangent_ready")
        self.focus_begin("tangent_geometry")
        self.beat(.32)
        self.focus_end("tangent_geometry")
        h = ValueTracker(.4)
        actual = Dot(plot_point(2.4, square(2.4), True), color=CURVE, radius=.075)
        predicted = Dot(plot_point(2.4, local_prediction(.4), True), color=DERIVATIVE, radius=.065)
        error = Line(predicted.get_center(), actual.get_center(), color=INK, stroke_width=3)
        rows, numbers = Group(), []
        for text, y, initial, color in (("h", .25, .4, H_COLOR),
                                        ("预测", -.5, local_prediction(.4), DERIVATIVE),
                                        ("曲线值", -1.25, square(2.4), CURVE)):
            label = self.put(text, 2.65, y, size=32, color=color) if text == "h" else self.label(text, 2.65, y, size=27, color=color)
            number = self.number(initial, size=35, decimals=3, color=color).move_to([4.9, y, 0])
            numbers.append(number)
            rows.add(label, number)
        self.beat(.42, FadeIn(actual), FadeIn(predicted), FadeIn(error), FadeIn(rows))
        self.mark("prediction_setup_ready")
        driver = Group()

        def update(_):
            value = h.get_value()
            actual.move_to(plot_point(2 + value, square(2 + value), True))
            predicted.move_to(plot_point(2 + value, local_prediction(value), True))
            error.put_start_and_end_on(predicted.get_center(), actual.get_center())
            for number, val in zip(numbers, (value, local_prediction(value), square(2 + value))):
                number.set_value(val)
            self.sample("prediction", h=value, actual=square(2 + value), predicted=local_prediction(value),
                        remainder=approximation_remainder(value),
                        actual_point=actual.get_center().tolist(), predicted_point=predicted.get_center().tolist())

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("local_prediction")
        self.beat(.72, h.animate.set_value(.1), rate_func=linear)
        self.mark("prediction_small_ready")
        self.beat(.78)
        self.focus_end("local_prediction")
        driver.clear_updaters()
        self.beat(.80, FadeIn(self.put(r"f(2+h)=4+4h+h^2", 3.8, -2.1, size=34)),
                  FadeIn(self.put(r"h=0.1:\quad h^2=0.01", 3.8, -2.85, size=31, color=CURVE)))
        self.mark("remainder_ready")
        self.focus_begin("prediction_remainder")
        self.beat(1)
        self.focus_end("prediction_remainder")

    def closing(self, cue):
        self.begin_chapter(cue)
        self.beat(.14, FadeIn(self.put(r"\frac{\Delta y}{\Delta x}\ \longrightarrow\ f'(2)=4", 0, 1.2, size=53,
                                     color=DERIVATIVE, width=11)),
                  FadeIn(self.label("区间缩小，读出本点变化率", 0, -.05, size=33)),
                  FadeIn(self.label("切线的方向，也给出附近变化的预测", 0, -1.0, size=29, color=MUTED)))
        self.mark("lesson_summary_ready")
        self.focus_begin("local_summary")
        self.beat(.53)
        self.focus_end("local_summary")
        self.beat(.62, FadeIn(self.put(r"2\ \longrightarrow\ a:\qquad f'(a)=\ ?", 0, -2.15,
                                     size=45, color=H_COLOR, width=11)))
        self.mark("next_position_question_ready")
        self.focus_begin("next_position")
        self.beat(1)
        self.focus_end("next_position")

    def construct(self):
        if tuple(cue["id"] for cue in self.cues) != CUE_IDS:
            raise ValueError("This scene needs its eight declared cues in order")
        self.motion_samples, self.symbol_transitions, self.chapter_times = [], [], []
        for cue in self.cues:
            self.until(cue["start"])
            getattr(self, cue["id"])(cue)
            self.chapter_times.append({"id": cue["id"], "start": cue["start"], "end": float(self.get_time())})
        report = {"duration": float(self.get_time()), "chapters": self.chapter_times,
                  "samples": self.motion_samples, "symbol_transitions": self.symbol_transitions,
                  "writer": "DerivativeIntroLesson actual native runtime",
                  "consumers": ["lead", "independent reviewer"], "lifecycle": "This exact render",
                  "invalidation": "Source, cue timing, profile, runtime or media change",
                  "limitation": "Native geometry and timing annotations do not prove pixel readability"}
        with (self.out / "derivative-intro-motion.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
