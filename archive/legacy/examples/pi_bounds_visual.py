"""Fresh silent geometry lesson; render, review and speech belong to the lead.

Numerical bounds use rational interval arithmetic, never trigonometric values.
Scene geometry uses radians only to place actual regular polygon vertices.
All ephemeral geometry is rebuilt per cue; the shared runtime owns evidence.
"""

import math
from fractions import Fraction

import numpy as np
from manimlib import *

from manimind.components.formula_motion import SemanticFormula, matching_transform
from manimind.experiments.understanding_support import UnderstandingScene


WHITE = "#EEF3F2"
MUTED = "#99A8AC"
INNER = "#77DCB0"
OUTER = "#FFAA87"
GOLD = "#F5D978"
BLUE = "#74C9F4"


def root_interval(value, digits=60):
    """Exact rational enclosure of a square root on a decimal lattice."""
    if value < 0 or type(digits) is not int or digits < 12:
        raise ValueError("Nonnegative radicand and at least 12 digits required")
    value = Fraction(value)
    scale = 10 ** digits
    floor = math.isqrt(value.numerator * scale * scale // value.denominator)
    low = Fraction(floor, scale)
    high = low if low * low == value else Fraction(floor + 1, scale)
    return low, high


def geometric_bounds(doublings=9, digits=60):
    """Certified six-gon start, followed by geometric half-angle recurrences.

    a is half an inscribed side / radius, b is its apothem / radius.
    Only endpoints rounded OUTWARD enter subsequent interval operations.
    """
    if type(doublings) is not int or not 0 <= doublings <= 16:
        raise ValueError("Use zero through sixteen geometric doublings")
    a = (Fraction(1, 2), Fraction(1, 2))
    b = root_interval(Fraction(3, 4), digits)
    rows = []
    n = 6
    for step in range(doublings + 1):
        rows.append({"n": n, "a": a, "b": b,
                     "lower": n * a[0], "upper": n * a[1] / b[0]})
        if step < doublings:
            a = (root_interval((1 - b[1]) / 2, digits)[0],
                 root_interval((1 - b[0]) / 2, digits)[1])
            b = (root_interval((1 + b[0]) / 2, digits)[0],
                 root_interval((1 + b[1]) / 2, digits)[1])
            n *= 2
    return rows


def outward_text(row, places=7):
    """Floor the lower endpoint and ceil the upper endpoint, as strings."""
    if type(places) is not int or not 0 <= places <= 20:
        raise ValueError("Expected zero through twenty decimal places")
    scale = 10 ** places
    result = []
    for key in ("lower", "upper"):
        value = row[key] * scale
        count = value.numerator // value.denominator
        if key == "upper" and value.denominator != 1:
            count += 1
        whole, tail = divmod(count, scale)
        result.append(f"{whole}.{tail:0{places}d}" if places else str(whole))
    return tuple(result)


def polygon_points(n, outer=False):
    """Exactly n vertices. Radians here are layout, not numerical evidence."""
    if type(n) is not int or n < 3:
        raise ValueError("A polygon needs at least three vertices")
    angle = math.pi / n
    radius = 1 / math.cos(angle) if outer else 1
    phase = math.pi / 6 - angle if outer else math.pi / 6
    return np.array([[radius * math.cos(2 * angle * k + phase),
                      radius * math.sin(2 * angle * k + phase), 0.] for k in range(n)])


def chord_split(alpha):
    """A-H-B becomes A-M-B, with the same endpoints on the unit circle."""
    b, a = math.sqrt(3) / 2, .5
    return np.array([[b, -a, 0], [b + (1 - b) * alpha, 0, 0], [b, a, 0]])


def corner_cut(alpha):
    """PV+VQ becomes PQ; P,Q are on the new tangent at the arc midpoint."""
    b, a = math.sqrt(3) / 2, .5
    p, q = np.array([1., -(1 - b) / a, 0]), np.array([1., (1 - b) / a, 0])
    vertex = np.array([1 / b, 0., 0.])
    return np.array([p, (1 - alpha) * vertex + alpha * (p + q) / 2, q])


class PiBoundsLesson(UnderstandingScene):
    def cn_at(self, text, x, y, size=32, color=WHITE):
        return self.cn(text, size=size, color=color).move_to([x, y, 0])

    def eq(self, latex, x, y, size=42, color=WHITE):
        return self.formula(latex, size=size, color=color).move_to([x, y, 0])

    def semantic(self, latex, tokens, x, y, size=40):
        return SemanticFormula(latex, tokens=tokens, font_size=size).move_to([x, y, 0])

    def line(self, a, b, color=MUTED, width=3):
        return Line(np.array(a, dtype=float), np.array(b, dtype=float),
                    stroke_color=color, stroke_width=width)

    def right_angle(self, vertex, u, v):
        u, v = np.array(u, dtype=float), np.array(v, dtype=float)
        u, v = .14 * u / np.linalg.norm(u), .14 * v / np.linalg.norm(v)
        return VGroup(self.line(vertex + u, vertex + u + v, GOLD, 2),
                      self.line(vertex + u + v, vertex + v, GOLD, 2))

    def show(self, *objects, seconds=.6):
        self.play(*(FadeIn(obj) for obj in objects), run_time=seconds)

    def enter(self, identity, title):
        cue = next(row for row in self.cues if row["id"] == identity)
        self.until(cue["start"])
        old = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        if old:
            self.play(*(FadeOut(obj) for obj in old), run_time=.4)
        self.show(self.cn_at(title, 0, 3.25, 38))
        return cue["start"]

    def hold(self, identity, end):
        self.focus_begin(identity)
        self.until(end)
        self.focus_end(identity)

    def polygon(self, n, center, radius=2.15, outer=False):
        points = polygon_points(n, outer) * radius + np.array(center)
        return VGroup(*(self.line(points[k], points[(k + 1) % n],
                                  OUTER if outer else INNER, 2.5) for k in range(n)))

    def construct(self):
        self.camera.background_rgba = color_to_rgba("#101416")
        self.ratios()
        self.split_chord()
        self.shave_corner()
        self.side_lengths()
        self.hexagon()
        self.half_angle()
        self.refine()
        self.decimal_cell()

    def ratios(self):
        s = self.enter("ratio", "π不是背出来的")
        center = np.array([-3.15, 0., 0.])
        circle = Circle(radius=2.15, stroke_color=WHITE).move_to(center)
        self.show(circle, self.polygon(6, center), self.polygon(6, center, outer=True))
        self.show(self.eq(r"\pi=\frac{C}{2r}", 2.75, 1.65, 56),
                  self.cn_at("圆周长 ÷ 直径", 2.75, .65, 32),
                  self.cn_at("内接周长 < 圆周长 < 外切周长", 1.9, -.65, 29),
                  self.eq(r"L_n<\pi<U_n", 2.75, -1.65, 46),
                  self.cn_at("用内外多边形夹住圆周长", 0, -2.75, 34))
        self.mark("ratio_ready")
        self.hold("ratio_meaning", s + 15.8)
        self.until(s + 16)

    def split_chord(self):
        s = self.enter("split", "一条弦，折成两段")
        origin, scale = np.array([-7.3, 0., 0.]), 5.
        point = lambda p: origin + scale * np.array(p)
        arc = ParametricCurve(lambda t: point([math.sqrt(1 - t * t), t, 0]),
                              t_range=(-.5, .5, .01), stroke_color=WHITE, stroke_width=3)
        a, h, b = chord_split(0)
        m = chord_split(1)[1]
        lines = VGroup(self.line(point(a), point(h), INNER, 6),
                       self.line(point(h), point(b), INNER, 6))
        labels = Group(*(self.eq(label, *(point(p)[:2] + offset), size=32)
                         for label, p, offset in (("A", a, [-.4, -.15]), ("B", b, [-.4, .15]),
                                                  ("H", h, [-.4, 0]), ("M", m, [.35, 0]))))
        self.show(arc, lines, labels, Dot(point(m), radius=.06, color=WHITE),
                  self.eq(r"AB=AH+HB", 2.7, 1.4, 40))
        self.mark("chord_before")
        self.hold("chord_before", s + 5)

        def bend(group, alpha):
            p, mid, q = [point(p) for p in chord_split(alpha)]
            group[0].put_start_and_end_on(p, mid)
            group[1].put_start_and_end_on(mid, q)

        self.play(UpdateFromAlphaFunc(lines, bend), run_time=4, rate_func=linear)
        self.show(self.eq(r"AM+MB>AB", 2.7, .25, 46, INNER),
                  self.cn_at("三角形的两边之和，大于第三边", 2.3, -1., 27),
                  self.eq(r"L_{2n}>L_n", 2.7, -2., 46, INNER))
        self.mark("chord_split_ready")
        self.hold("chord_growth", s + 27.8)
        self.until(s + 28)

    def shave_corner(self):
        s = self.enter("shave", "外面的凸角，削掉一截")
        origin, scale = np.array([-7.3, 0., 0.]), 5.
        point = lambda p: origin + scale * np.array(p)
        a, _, b = chord_split(0)
        p, v, q = corner_cut(0)
        arc = ParametricCurve(lambda t: point([math.sqrt(1 - t * t), t, 0]),
                              t_range=(-.5, .5, .01), stroke_color=WHITE)
        corner = VGroup(self.line(point(p), point(v), OUTER, 6),
                        self.line(point(v), point(q), OUTER, 6))
        self.show(arc, corner, self.line(point(a), point(p), OUTER), self.line(point(q), point(b), OUTER),
                  self.line(point(p), point(q), MUTED, 1),
                  *(self.eq(label, *(point(pos)[:2] + offset), size=32)
                    for label, pos, offset in (("P", p, [-.35, -.15]), ("Q", q, [-.35, .15]),
                                               ("V", v, [.35, 0]))),
                  self.eq(r"PV+VQ>PQ", 2.6, 1.25, 44, OUTER))
        self.mark("corner_before")
        self.hold("corner_triangle", s + 7)

        def shave(group, alpha):
            p0, mid, q0 = [point(p) for p in corner_cut(alpha)]
            group[0].put_start_and_end_on(p0, mid)
            group[1].put_start_and_end_on(mid, q0)

        self.play(UpdateFromAlphaFunc(corner, shave), run_time=4, rate_func=linear)
        self.show(self.cn_at("其余边段不变，只把凸角换成 PQ", 2.1, -.15, 28),
                  self.cn_at("新的边仍与圆相切", 2.6, -1.05, 29),
                  self.eq(r"U_{2n}<U_n", 2.6, -2.05, 46, OUTER))
        self.mark("corner_cut_ready")
        self.hold("corner_shrink", s + 25.8)
        self.until(s + 26)

    def side_lengths(self):
        s = self.enter("lengths", "把长度除以半径")
        o = np.array([-5.6, -.6, 0.])
        scale, a, b = 3.5, .5, math.sqrt(3) / 2
        h, p, m, t = [o + scale * np.array(v) for v in
                       ((b, 0, 0), (b, a, 0), (1, 0, 0), (1, a / b, 0))]
        self.show(self.line(o, t, WHITE), self.line(o, m, GOLD), self.line(h, p, INNER, 5),
                  self.line(m, t, OUTER, 5), self.line(p, t, MUTED, 1),
                  self.right_angle(h, o - h, p - h), self.right_angle(m, o - m, t - m),
                  self.eq("O", o[0] - .25, o[1] - .3, 30),
                  self.eq("H", h[0] - .15, h[1] - .35, 30),
                  self.eq("B", p[0] - .35, p[1] + .15, 30),
                  self.eq("M", m[0] + .2, m[1] - .35, 30),
                  self.eq("T", t[0] + .25, t[1] + .1, 30),
                  self.eq("a", h[0] - .2, (h[1] + p[1]) / 2, 36, INNER),
                  self.eq("b", (o[0] + h[0]) / 2, h[1] - .3, 36, GOLD),
                  self.eq("1", (o[0] + p[0]) / 2, (o[1] + p[1]) / 2 + .3, 36),
                  self.eq(r"r=1\ \mathrm{u}", -3.7, 2.15, 36),
                  self.eq(r"a^2+b^2=1", 2.75, 1.65, 44))
        self.show(self.eq(r"\triangle OHB\sim\triangle OMT", 2.55, .65, 35),
                  self.eq(r"\frac{MT}{a}=\frac{1}{b}\quad\Rightarrow\quad MT=\frac{a}{b}", 2.5, -.4, 36))
        self.mark("similarity_ready")
        self.hold("side_similarity", s + 16)
        self.show(self.eq(r"P_{\rm in}=2na\ \mathrm{u}\qquad P_{\rm out}=2n\frac{a}{b}\ \mathrm{u}", 0, -1.65, 35),
                  self.eq(r"L_n=na\quad<\quad\frac{C}{2r}=\pi\quad<\quad U_n=\frac{na}{b}", 0, -2.55, 40))
        self.mark("bounds_formula_ready")
        self.hold("normalized_bounds", s + 27.8)
        self.until(s + 28)

    def hexagon(self):
        s = self.enter("hexagon", "六边形给出起点")
        center = np.array([-3.3, 0, 0])
        vertices = polygon_points(6) * 2.1 + center
        self.show(Circle(radius=2.1, stroke_color=MUTED).move_to(center),
                  self.polygon(6, center, 2.1),
                  *(self.line(center, vertex, MUTED, 1) for vertex in vertices),
                  self.cn_at("六个等边三角形，边长都是半径", 2.2, 1.85, 28),
                  self.eq(r"2a_6=1\quad\Rightarrow\quad a_6=\frac12", 2.5, .65, 42, INNER))
        self.mark("hexagon_ready")
        self.hold("hexagon_side", s + 9)
        self.show(self.eq(r"b_6^2=1-\left(\frac12\right)^2=\frac34", 2.5, -.5, 40),
                  self.eq(r"b_6=\frac{\sqrt3}{2}", 2.5, -1.55, 44, GOLD),
                  self.eq(r"3<\pi<2\sqrt3", 0, -2.65, 46))
        self.mark("hexagon_seed_ready")
        self.hold("hexagon_seed", s + 25.8)
        self.until(s + 26)

    def half_angle(self):
        s = self.enter("half", "边数翻倍，新长度从哪里来？")
        # One old edge AB, its midpoint H, arc midpoint M, new chord midpoint K.
        origin, scale = np.array([-5.9, -.85, 0.]), 3.8
        a, b = .5, math.sqrt(3) / 2
        point = lambda x, y: origin + scale * np.array([x, y, 0])
        o, h, p, m, k = origin, point(b, 0), point(b, a), point(1, 0), point((1 + b) / 2, a / 2)
        bottom = point(b, -a)
        arc = ParametricCurve(lambda t: point(math.sqrt(1 - t * t), t),
                              t_range=(-.5, .5, .01), stroke_color=MUTED)
        hm_label = self.eq(r"HM=1-b_n", 2.65, 1.4, 39, GOLD)
        identities = self.eq(r"HB=a_n\qquad OH=b_n\qquad OM=OB=1", 1.9, 2.35, 31)
        self.show(arc, self.line(o, p, WHITE), self.line(o, m, GOLD), self.line(bottom, p, INNER, 4),
                  self.right_angle(h, m - h, p - h),
                  *(self.eq(label, pos[0] + dx, pos[1] + dy, 30)
                    for label, pos, dx, dy in (("O", o, -.3, -.2), ("H", h, -.3, -.3),
                                              ("B", p, -.3, .2), ("A", bottom, -.3, -.2),
                                              ("M", m, .3, -.2))),
                  identities, hm_label)
        self.mark("half_geometry_ready")
        self.hold("half_geometry", s + 8)
        bm = self.line(p, m, BLUE, 5)
        self.play(ShowCreation(bm), run_time=1)
        first = self.semantic(r"BM^2=a_n^2+(1-b_n)^2", {"chord": "BM", "old_a": "a_n"}, 2.45, .4, 36)
        self.show(first)
        self.mark("pythagoras_ready")
        self.hold("half_pythagoras", s + 16)
        second = self.semantic(r"BM^2=1-b_n^2+1-2b_n+b_n^2", {"chord": "BM"}, 2.45, .4, 33)
        self.play(matching_transform(first, second), run_time=1)
        self.play(FadeOut(hm_label), run_time=.4)
        self.show(self.eq(r"a_n^2=1-b_n^2", 2.65, 1.4, 34), seconds=.6)
        self.hold("half_substitution", s + 22)
        third = self.semantic(r"BM^2=2(1-b_n)", {"chord": "BM"}, 2.45, .4, 40)
        self.play(matching_transform(second, third), run_time=1)
        self.play(FadeOut(identities), run_time=.4)
        self.show(self.line(o, k, GOLD, 4), Dot(k, radius=.05, color=GOLD),
                  self.right_angle(k, o - k, p - k),
                  self.eq("K", k[0] + .35, k[1] + .15, 30),
                  self.eq(r"OB=OM,\ BK=KM\ \Rightarrow\ OK\perp BM", 1.9, 2.35, 31),
                  self.eq(r"BK=KM=\frac{BM}{2}=a_{2n}", 2.5, -.55, 37, BLUE),
                  self.eq(r"a_{2n}^2=\frac{BM^2}{4}=\frac{1-b_n}{2}", 2.4, -1.55, 38, BLUE))
        self.mark("half_side_ready")
        self.hold("half_side", s + 32)
        self.play(FadeOut(third), run_time=.4)
        self.show(self.eq(r"OK=b_{2n}\,,\quad OK^2+BK^2=1", 2.5, .4, 36, GOLD),
                  self.eq(r"b_{2n}^2=1-\frac{1-b_n}{2}=\frac{1+b_n}{2}", 2.4, -2.55, 36, GOLD))
        self.mark("half_apothem_ready")
        self.hold("half_apothem", s + 43.8)
        self.until(s + 44)

    def refine(self):
        s = self.enter("refine", "内界升，外界降")
        rows = geometric_bounds(4)
        self.show(self.eq(r"a_{2n}=\sqrt{\frac{1-b_n}{2}}\qquad b_{2n}=\sqrt{\frac{1+b_n}{2}}", 0, 2.45, 37))
        center = np.array([-3.25, -.25, 0])
        circle = Circle(radius=2., stroke_color=WHITE, stroke_width=2).move_to(center)
        self.show(circle, self.line([.45, -.55, 0], [5.9, -.55, 0], MUTED, 2))
        previous = None
        for index, row in enumerate(rows):
            self.until(s + 3 + index * 4.6)
            low, high = outward_text(row, 6)
            x = lambda value: .6 + 5.1 * (float(value) - 3) / .5
            low_x, high_x = x(Fraction(low)), x(Fraction(high))
            state = Group(self.polygon(row["n"], center, 2), self.polygon(row["n"], center, 2, True),
                          self.eq(f"n={row['n']}", -3.25, -2.7, 37),
                          self.eq(low + r"<\pi<" + high, 3., .85, 36),
                          self.line([low_x, -.55, 0], [high_x, -.55, 0], GOLD, 7),
                          Dot([low_x, -.55, 0], color=INNER, radius=.07),
                          Dot([high_x, -.55, 0], color=OUTER, radius=.07),
                          self.cn_at("下界", 1.3, -1.55, 29, INNER),
                          self.cn_at("上界", 4.65, -1.55, 29, OUTER))
            if previous is not None:
                self.play(FadeOut(previous), run_time=.2)
            self.show(state, seconds=.6)
            self.mark(f"polygon_{row['n']}_ready")
            self.hold(f"interval_{row['n']}", s + 7.4 + index * 4.6)
            previous = state
        self.until(s + 28)

    def decimal_cell(self):
        s = self.enter("decimal", "多算几次，能确定哪些小数？")
        self.show(self.cn_at("计算表", -5.1, 2.45, 30),
                  self.cn_at("边数 n", -4.4, 1.7, 28),
                  self.cn_at("向下取的下界", -.9, 1.7, 28, INNER),
                  self.cn_at("向上取的上界", 3.5, 1.7, 28, OUTER))
        for index, row in enumerate(geometric_bounds(9)[5:]):
            low, high = outward_text(row, 7)
            y = 1.05 - index * .58
            self.show(self.eq(str(row["n"]), -4.4, y, 30),
                      self.eq(low, -.9, y, 32, INNER), self.eq(high, 3.5, y, 32, OUTER), seconds=.6)
        self.mark("calculation_table_ready")
        self.hold("calculation_table", s + 11)
        low, high = outward_text(geometric_bounds(9)[-1], 7)
        self.show(self.eq(low + r"<\pi<" + high, 0, -2., 42),
                  self.eq(r"3.141585\ \leq\ x\ <\ 3.141595\quad\longrightarrow\quad 3.14159", 0, -2.85, 35))
        self.mark("rounding_cell_ready")
        self.hold("rounding_cell", s + 21)
        old = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        self.play(*(FadeOut(obj) for obj in old), run_time=.4)
        self.show(self.cn_at("五位小数确定了，π仍在区间里", 0, 1.8, 36),
                  self.eq(low + r"<\pi<" + high, 0, .4, 52),
                  self.eq(r"U_n-L_n=na_n\frac{1-b_n}{b_n}>0", 0, -1.05, 40),
                  self.cn_at("再分细：内接的继续长，外切的继续短", 0, -2.35, 32))
        self.mark("finite_gap_ready")
        self.hold("finite_gap", s + 29.8)
        self.until(s + 30)
