"""Fresh derivative lesson; native geometry, no inherited lesson or speech clock."""

import json

import numpy as np
from manimlib import (
    Circle, Dot, FadeIn, FadeOut, Group, Line, ShowCreation, VMobject,
    ValueTracker, VGroup, linear,
)

from manimind.components.formula_motion import SemanticFormula, matching_transform
from manimind.experiments.understanding_support import UnderstandingScene


INK = "#EEF1F4"
CURVE = "#53D6B0"
RIGHT_COLOR = "#F3D36A"
LEFT_COLOR = "#FF8F98"
MUTED = "#AAB3B9"
BG = "#101416"
CUE_DURATIONS = (24, 28, 64, 30, 50, 26, 12)
ALGEBRA = (
    ("quotient", r"\frac{f(1+h)-f(1)}{h}",
     {"h_primary": ("h", 0), "h_den": ("h", 1)}),
    ("substitute", r"\frac{(1+h)^2-1}{h}",
     {"h_primary": ("h", 0), "h_den": ("h", 1),
      "base_one": ("1", 0), "sub_one": ("1", 1), "power": "2"}),
    ("expand", r"\frac{1+2h+h^2-1}{h}",
     {"base_one": ("1", 0), "sub_one": ("1", 1), "two": ("2", 0),
      "h_primary": ("h", 0), "h_extra": ("h", 1), "h_den": ("h", 2),
      "power": ("2", 1)}),
    ("reduce", r"\frac{2h+h^2}{h}",
     {"two": ("2", 0), "h_primary": ("h", 0), "h_extra": ("h", 1),
      "h_den": ("h", 2), "power": ("2", 1)}),
    ("factor", r"\frac{h(2+h)}{h}",
     {"h_primary": ("h", 0), "two": "2", "h_extra": ("h", 1),
      "h_den": ("h", 2)}),
    ("simplify", r"2+h", {"two": "2", "h_extra": "h"}),
)


def square(x):
    return x * x


def secant_rate(h):
    if h == 0:
        raise ValueError("A secant requires two distinct points: h != 0")
    return (square(1 + h) - square(1)) / h


def zoom_height(u, s):
    if s <= 0:
        raise ValueError("The common magnification scale must be positive")
    return 2 * u + s * u * u


def corner_rate(h):
    if h == 0:
        raise ValueError("The difference quotient is undefined at h = 0")
    return abs(h) / h


def polyline(points, color=CURVE, width=4):
    return VMobject().set_points_as_corners(points).set_stroke(color, width)


class DerivativeLesson(UnderstandingScene):
    def put(self, latex, x, y, size=40, color=INK, width=6.3):
        result = self.formula(latex, size=size, color=color)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def label(self, text, x, y, size=32, color=INK):
        return self.cn(text, size=size, color=color).move_to([x, y, 0])

    def title(self, text):
        result = self.label(text, 0, 3.35, size=40)
        self.play(FadeIn(result), run_time=1)
        return result

    def clear_stage(self):
        objects = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        for obj in objects:
            obj.clear_updaters()
        if objects:
            self.play(*(FadeOut(obj) for obj in objects), run_time=1)

    def read(self, identity, duration, event=None):
        if event:
            self.mark(event)
        self.focus_begin(identity)
        self.wait(duration)
        self.focus_end(identity)

    def axes(self, point, x_range, y_range, x_name, y_name):
        axes = VGroup(
            Line(point(x_range[0], 0), point(x_range[1], 0)),
            Line(point(0, y_range[0]), point(0, y_range[1])),
        ).set_stroke(MUTED, 2)
        names = Group(
            self.put(x_name, *point(x_range[1], 0)[:2], size=30).shift([.25, -.27, 0]),
            self.put(y_name, *point(0, y_range[1])[:2], size=30).shift([-.24, .18, 0]),
        )
        return Group(axes, names)

    @staticmethod
    def original_point(x, y):
        return np.array([-5.25 + 1.65 * x, -2.25 + 1.65 * y, 0.])

    def square_graph(self):
        p = self.original_point
        axes = self.axes(p, (-.2, 1.9), (-.25, 2.85), "x", "y")
        curve = polyline([p(x, square(x)) for x in np.linspace(0, 1.66, 121)])
        base = Dot(p(1, 1), radius=.065, color=INK)
        name = self.put("P=(1,1)", -4.55, -.15, size=30, width=2.6)
        ticks = Group(self.put("1", *p(1, -.16)[:2], size=27),
                      self.put("1", *p(-.13, 1)[:2], size=27))
        return Group(axes, curve, base, name, ticks)

    def slope_line(self, slope, color):
        p = self.original_point
        lo, hi = max(.25, 1 - 1.25 / slope), 1.64
        return Line(p(lo, 1 + slope * (lo - 1)),
                    p(hi, 1 + slope * (hi - 1)), color=color, stroke_width=3)

    def secant(self, h, color):
        if h == 0:
            raise ValueError("A secant still needs h != 0; construct a tangent from its limit slope")
        return self.slope_line(2 + h, color)

    def rate_row(self, y, prefix, color):
        label = self.put(prefix, 1.3, y, size=34, color=color, width=2.5)
        h_value = self.number(.6, size=34, decimals=2, color=color).move_to([2.6, y, 0])
        arrow = self.put(r"\longrightarrow", 3.35, y, size=34)
        m_value = self.number(2.6, size=34, decimals=2, color=color).move_to([4.35, y, 0])
        return Group(label, h_value, arrow, m_value), h_value, m_value

    def sample(self, kind, **values):
        self.motion_samples.append({"kind": kind, "time": float(self.get_time()), **values})

    def opening(self):
        self.title("一个点上，怎样谈变化率？")
        graph = self.square_graph()
        p = self.original_point
        q = Dot(p(1.6, 2.56), color=RIGHT_COLOR, radius=.065)
        q_name = self.put("Q", -2.32, 2.1, size=33, color=RIGHT_COLOR)
        secant = self.secant(.6, RIGHT_COLOR)
        function = self.put(r"f(x)=x^2,\quad a=1", 2.5, 2.35, size=42)
        self.play(FadeIn(graph), FadeIn(q), FadeIn(q_name), ShowCreation(secant),
                  FadeIn(function), run_time=2)
        self.read("two_points", 5, "two_points_ready")
        horizontal = Line(p(1, 1), p(1.6, 1), color=RIGHT_COLOR, stroke_width=4)
        vertical = Line(p(1.6, 1), p(1.6, 2.56), color=CURVE, stroke_width=4)
        dx = self.put(r"\Delta x=h", 2.5, 1.3, size=42, color=RIGHT_COLOR)
        dy = self.put(r"\Delta y=f(1+h)-f(1)", 2.5, .45, size=40, color=CURVE)
        self.play(ShowCreation(horizontal), FadeIn(dx), run_time=1)
        self.play(ShowCreation(vertical), FadeIn(dy), run_time=1)
        rate = self.put(r"m=\frac{\Delta y}{\Delta x}=\frac{f(1+h)-f(1)}{h}",
                        2.5, -1, size=42)
        caption = self.label("一段区间上的平均变化率", 2.5, -2.2, size=31)
        self.play(FadeIn(rate), FadeIn(caption), run_time=2)
        self.read("average_rate", 10, "average_rate_ready")

    def sides(self):
        self.clear_stage()
        self.title("从右边，也从左边靠近")
        graph = self.square_graph()
        radius = ValueTracker(.6)
        right, left = self.secant(.6, RIGHT_COLOR), self.secant(-.6, LEFT_COLOR)
        qr = Dot(self.original_point(1.6, 2.56), color=RIGHT_COLOR, radius=.065)
        ql = Dot(self.original_point(.4, .16), color=LEFT_COLOR, radius=.065)
        row_r, hr, mr = self.rate_row(1.25, r"h_+=", RIGHT_COLOR)
        row_l, hl, ml = self.rate_row(.25, r"h_-=", LEFT_COLOR)
        labels = Group(self.label("水平增量", 2.15, 2.2, size=30),
                       self.label("割线斜率", 4.35, 2.2, size=30))
        formula = self.put(r"m(h)=\frac{(1+h)^2-1}{h},\quad h\ne0", 2.6, -1.2, size=40)
        group = Group(graph, right, left, qr, ql, row_r, row_l, labels, formula)

        def update(_):
            r = radius.get_value()
            right.become(self.secant(r, RIGHT_COLOR))
            left.become(self.secant(-r, LEFT_COLOR))
            qr.move_to(self.original_point(1 + r, square(1 + r)))
            ql.move_to(self.original_point(1 - r, square(1 - r)))
            for h, hv, mv in ((r, hr, mr), (-r, hl, ml)):
                hv.set_value(h)
                mv.set_value(secant_rate(h))
            self.sample("sides", h=r, right=secant_rate(r), left=secant_rate(-r),
                        qr=qr.get_center().tolist(), ql=ql.get_center().tolist())

        self.play(FadeIn(group), run_time=2)
        group.add_updater(update)
        self.mark("both_sides_ready")
        self.focus_begin("both_sides_approach")
        self.wait(3)
        self.play(radius.animate.set_value(.06), run_time=12, rate_func=linear)
        self.mark("both_sides_near")
        self.wait(7)
        self.focus_end("both_sides_approach")
        group.clear_updaters()

    def algebra(self):
        self.clear_stage()
        self.title("先让每一条割线的斜率变简单")
        condition = self.put(r"h\ne0", 0, 2.05, size=42, color=RIGHT_COLOR)
        note = self.label("两个点还没有重合", 0, -2.1, size=32)
        self.play(FadeIn(condition), FadeIn(note), run_time=1)
        name, latex, tokens = ALGEBRA[0]
        current = SemanticFormula(latex, tokens=tokens, font_size=60).move_to([0, .3, 0])
        self.play(FadeIn(current), run_time=1)
        self.read("quotient", 4, "quotient_ready")
        holds = {"substitute": 5, "expand": 7, "reduce": 5, "factor": 7, "simplify": 7}
        moves = {"substitute": 3, "expand": 4, "reduce": 3, "factor": 4, "simplify": 3}
        for name, latex, tokens in ALGEBRA[1:]:
            if name == "simplify":
                strikes = VGroup(*(Line(current.tag(key).get_corner(np.array([-1, -1, 0])),
                                       current.tag(key).get_corner(np.array([1, 1, 0])),
                                       color=LEFT_COLOR, stroke_width=4)
                                   for key in ("h_primary", "h_den")))
                self.play(ShowCreation(strikes), run_time=2)
                self.read("cancel_nonzero", 5, "cancellation_ready")
                self.remove(strikes)
            target = SemanticFormula(latex, tokens=tokens, font_size=60).move_to([0, .3, 0])
            start = float(self.get_time())
            driver = Group()

            def track(_, source=current, stage=name):
                self.sample("symbol", stage=stage,
                            centers={key: source.tag(key).get_center().tolist()
                                     for key in source.semantic_ids})

            driver.add_updater(track)
            self.add(driver)
            self.play(matching_transform(current, target, run_time=moves[name],
                                         path_arc=.25, unmatched_in_place=True))
            self.remove(driver)
            self.symbol_transitions.append({"stage": name, "start": start,
                                            "end": float(self.get_time()),
                                            "source": current.get_tex(), "target": latex})
            current = target
            self.read(name, holds[name], name + "_ready")
        # h != 0 remains present through cancellation and the simplified state.

    def limit(self):
        self.clear_stage()
        self.title("趋近零，和直接等于零，是两件事")
        point = lambda h, m: np.array([-3.8 + 1.7 * h, -.25 + 1.7 * (m - 2), 0.])
        axes = self.axes(lambda x, y: point(x, y + 2), (-1, 1), (-1, 1), "h", "m")
        ticks = Group(self.put("0", -4, -.6, size=28), self.put("2", -4.1, .1, size=28))
        line = Line(point(-1, 1), point(1, 3), color=CURVE, stroke_width=4)
        hole = Circle(radius=.095, stroke_color=INK, stroke_width=3,
                      fill_color=BG, fill_opacity=1).move_to(point(0, 2))
        radius = ValueTracker(.75)
        right = Dot(point(.75, 2.75), color=RIGHT_COLOR, radius=.065)
        left = Dot(point(-.75, 1.25), color=LEFT_COLOR, radius=.065)
        formula = self.put(r"m(h)=2+h\quad(h\ne0)", 2.6, 1.65, size=42)
        missing = self.put(r"h=0:\quad\frac{0}{0}", 2.6, .55, size=42)
        missing_text = self.label("原来的商没有定义", 2.6, -.35, size=31)
        self.play(FadeIn(Group(axes, ticks, line, right, left, hole)), FadeIn(formula),
                  FadeIn(missing), FadeIn(missing_text), run_time=2)
        self.read("punctured_quotient", 6, "hole_ready")
        driver = Group()

        def update(_):
            r = radius.get_value()
            right.move_to(point(r, 2 + r))
            left.move_to(point(-r, 2 - r))
            # Preserve the visible hole above the two approaching dots.
            self.sample("limit", h=r, right=2 + r, left=2 - r)

        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("limit_approach")
        self.play(radius.animate.set_value(.08), run_time=6, rate_func=linear)
        self.focus_end("limit_approach")
        result = self.put(r"f'(1)=\lim_{h\to0}(2+h)=2", 2.6, -1.65, size=44)
        self.play(FadeIn(result), run_time=2)
        self.read("derivative_value", 10, "derivative_ready")
        self.remove(driver)

    def zoom(self):
        self.clear_stage()
        self.title("放大后，为什么越来越像直线？")
        p = lambda u, v: np.array([-3.6 + 1.1 * u, -.35 + 1.1 * v, 0.])
        axes = self.axes(p, (-1.2, 1.2), (-2.15, 2.65), "U", "V")
        scale = ValueTracker(.5)
        curve = polyline([p(u, zoom_height(u, .5)) for u in np.linspace(-1, 1, 121)])
        tangent = Line(p(-1, -2), p(1, 2), color=RIGHT_COLOR, stroke_width=3)
        base = Dot(p(0, 0), color=INK, radius=.055)
        base_name = self.put("P", -3.9, -.1, size=29)
        tick = Group(self.put("1", *p(1, -.18)[:2], size=28),
                     self.put("2", *p(-.19, 2)[:2], size=28))
        coordinates = self.put(r"U=\frac{x-1}{s},\quad V=\frac{y-1}{s},\quad s>0",
                               2.2, 2.15, size=39, width=7.2)
        same = self.label("横纵增量，都除以同一个 s", 2.2, 1.2, size=31)
        self.play(FadeIn(Group(axes, curve, tangent, base, base_name, tick)),
                  FadeIn(coordinates), FadeIn(same), run_time=2)
        self.read("common_scale", 6, "zoom_coordinates_ready")
        mapping = self.put(r"x=1+sU,\quad y=(1+sU)^2", 2.2, .3, size=39, width=7.2)
        self.play(FadeIn(mapping), run_time=1)
        self.read("zoom_substitution", 4, "zoom_substitution_ready")
        exact = self.put(r"V=\frac{(1+sU)^2-1}{s}=2U+sU^2", 2.2, -.75,
                         size=43, width=7.2)
        self.play(FadeIn(exact), run_time=2)
        self.read("zoom_identity", 5, "zoom_identity_ready")
        self.play(FadeOut(mapping), FadeOut(same), run_time=1)
        s_label = self.put("s=", 1.55, 1.1, size=37)
        s_value = self.number(.5, size=37, decimals=2).move_to([2.4, 1.1, 0])
        error = Line(p(1, 2), p(1, 2.5), color=LEFT_COLOR, stroke_width=7)
        bound = self.put(r"|U|\le1:\quad |V-2U|=sU^2\le s", 2.2, -1.9,
                         size=39, color=LEFT_COLOR, width=7.2)
        line_label = self.put("V=2U", 2.2, .2, size=39, color=RIGHT_COLOR)
        self.play(FadeIn(Group(s_label, s_value, error, bound, line_label)), run_time=1)
        driver = Group()

        def update(_):
            s = scale.get_value()
            curve.set_points_as_corners([p(u, zoom_height(u, s)) for u in np.linspace(-1, 1, 121)])
            error.put_start_and_end_on(p(1, 2), p(1, zoom_height(1, s)))
            s_value.set_value(s)
            self.sample("zoom", s=s, u=1., v=zoom_height(1, s),
                        error=float(np.linalg.norm(error.get_end() - error.get_start())),
                        curve_end=curve.get_end().tolist())

        driver.add_updater(update)
        self.add(driver)
        self.mark("zoom_error_ready")
        self.focus_begin("local_linearity")
        self.wait(2)
        self.play(scale.animate.set_value(.1), run_time=6, rate_func=linear)
        self.wait(2)
        self.play(scale.animate.set_value(.01), run_time=6, rate_func=linear)
        self.mark("zoom_near_line")
        self.wait(9)
        self.focus_end("local_linearity")
        self.remove(driver)

    def corner(self):
        self.clear_stage()
        self.title("如果左右靠近，方向不同呢？")
        p = lambda x, y: np.array([-3.7 + 1.7 * x, -1.7 + 1.7 * y, 0.])
        axes = self.axes(p, (-1.2, 1.2), (-.25, 1.5), "x", "y")
        curve = polyline([p(-1.1, 1.1), p(0, 0), p(1.1, 1.1)])
        radius = ValueTracker(.9)
        right, left = Dot(p(.9, .9), color=RIGHT_COLOR), Dot(p(-.9, .9), color=LEFT_COLOR)
        rays = VGroup(Line(p(-.75, -.75), p(1.1, 1.1), color=RIGHT_COLOR, stroke_width=2),
                      Line(p(-1.1, 1.1), p(.75, -.75), color=LEFT_COLOR, stroke_width=2))
        formula = self.put(r"g(x)=|x|,\quad a=0", 2.5, 2.0, size=44)
        quotient = self.put(r"\frac{|h|-0}{h}=\begin{cases}1&h>0\\-1&h<0\end{cases}",
                            2.5, .5, size=47)
        self.play(FadeIn(Group(axes, curve, right, left, rays)), FadeIn(formula),
                  FadeIn(quotient), run_time=2)
        driver = Group()

        def update(_):
            r = radius.get_value()
            right.move_to(p(r, r))
            left.move_to(p(-r, r))
            self.sample("corner", h=r, right=corner_rate(r), left=corner_rate(-r))

        driver.add_updater(update)
        self.add(driver)
        self.mark("corner_sides_ready")
        self.focus_begin("corner_disagreement")
        self.play(radius.animate.set_value(.05), run_time=8, rate_func=linear)
        answer = self.label("斜率没有共同的极限", 2.5, -1.3, size=34)
        no_derivative = self.label("在 0 处不可导", 2.5, -2.2, size=34)
        self.play(FadeIn(answer), FadeIn(no_derivative), run_time=2)
        self.mark("corner_result_ready")
        self.wait(12)
        self.focus_end("corner_disagreement")
        self.remove(driver)

    def closing(self):
        self.clear_stage()
        self.title("导数：平均变化率走向的那个值")
        graph = self.square_graph()
        tangent = self.slope_line(2, RIGHT_COLOR)
        derivative = self.put(r"f'(1)=2", 2.4, 1.7, size=58, color=RIGHT_COLOR)
        equation = self.put(r"y-1=2(x-1)", 2.4, .6, size=46)
        approximation = self.put(r"f(1+h)-f(1)=2h+h^2\ \approx\ 2h", 2.4, -.65, size=39)
        condition = self.put(r"|h|\ll1", 2.4, -1.5, size=34)
        caption = self.label("在这一点附近，每单位输入约带来 2 单位输出", 1.7, -2.5, size=28)
        self.play(FadeIn(Group(graph, tangent, derivative, equation, approximation, condition, caption)), run_time=2)
        self.read("instantaneous_rate", 8, "tangent_summary_ready")

    def construct(self):
        self.motion_samples, self.symbol_transitions, self.chapter_times = [], [], []
        methods = (self.opening, self.sides, self.algebra, self.limit, self.zoom, self.corner, self.closing)
        for cue, duration, method in zip(self.cues, CUE_DURATIONS, methods, strict=True):
            if cue["duration"] != duration:
                raise ValueError("This scene and the selected plan have different cue durations")
            self.until(cue["start"])
            begin = float(self.get_time())
            method()
            self.until(cue["start"] + duration)
            self.chapter_times.append({"id": cue["id"], "start": begin, "end": float(self.get_time())})

    def tear_down(self):
        report = {"duration": float(self.get_time()), "samples": self.motion_samples,
                  "symbol_transitions": self.symbol_transitions, "chapters": self.chapter_times,
                  "writer": "DerivativeLesson native scene updaters",
                  "consumers": ["independent reviewer", "geometry tests"],
                  "lifecycle": "This exact scene execution",
                  "invalidation": "Source, plan, typography, native runtime or timing changes",
                  "limitation": "Native geometry/time observations, not pixel or comprehension approval"}
        with (self.out / "derivative-motion.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
        super().tear_down()
