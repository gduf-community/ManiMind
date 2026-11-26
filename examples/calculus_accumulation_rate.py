"""CA-010: why the rate of an accumulated quantity returns the integrand.

One native clock drives the inflow graph f, the accumulated amount A, the strip,
the rescaled magnifier and every readout. f(t)=t(5-t)/2, A(x)=5x^2/4-x^3/6.
"""

import sys

import numpy as np

_argv = sys.argv
try:
    sys.argv = _argv[:1]
    from manimlib import (Arrow, DashedLine, Dot, FadeIn, FadeOut, Group, Line, Transform, UpdateFromAlphaFunc,
                          ValueTracker, VGroup, VMobject, linear, smooth)
    from manimind.components.formula_motion import SemanticFormula
    from derivative_chapter_shared import ACCENT, ChapterScene, CURVE, INK, MUTED, RATE
finally:
    sys.argv = _argv
del _argv

AMOUNT = "#7FB2FF"
NEGATIVE = "#C77DFF"
X0, SX, YF, SF, YA, SA = -6.25, .98, 1.35, .42, -2.6, .21
PX, PW, PY, PZ = 1.75, 3.3, -1.72, .78
INC = "A(x+h)-A(x)"


def f(t):
    return t*(5-t)/2


def amount(x):
    return 5*x*x/4-x**3/6


def top(t, v):
    return np.array([X0+SX*t, YF+SF*v, 0])


def low(t, v):
    return np.array([X0+SX*t, YA+SA*v, 0])


class AccumulationRate(ChapterScene):
    # ---------- helpers ----------
    def begin(self, cue, *keep):
        if self._open_focus:
            raise ValueError("Close every focus first")
        self._cue = cue
        kept = {id(m) for m in keep}
        old = [m for m in self.mobjects if m is not self._subtitle_driver and id(m) not in kept]
        for m in old:
            m.clear_updaters()
        self.beat(.025, *(FadeOut(m) for m in old)) if old else self.beat(.025)
        self.head = self.label(cue["heading"], 0, 3.5, size=34)
        self.until(self.stage_time(.025)+.5, FadeIn(self.head))

    def poly(self, points, color, fill=0, width=0, live=True):
        m = VMobject()
        m.set_points_as_corners(points())
        m.set_fill(color, fill).set_stroke(color, width, 1 if width else 0)
        if live:
            m.add_updater(lambda mob: mob.set_points_as_corners(points()))
        return m

    def text_left(self, text, x, y, size=26, color=INK):
        m = self.label(text, 0, y, size=size, color=color)
        return m.shift([x-m.get_left()[0], 0, 0])

    def reading(self, text, x, y, value, color=INK, size=26, decimals=2, unit=""):
        name = self.text_left(text, x, y, size, color)
        num = self.number(value(), size=size, color=color, decimals=decimals)
        tail = self.text_left(unit, 0, y, size, color) if unit else None
        left = name.get_right()[0]+.12

        def place(mob=None):
            num.set_value(value())
            num.move_to([left+num.get_width()/2, y, 0])
            if tail is not None:
                tail.move_to([num.get_right()[0]+.1+tail.get_width()/2, y, 0])
        place()
        result = Group(name, num, *([tail] if tail is not None else []))
        result.add_updater(lambda mob: place())
        return result

    def carry(self, source, target, end, pairs):
        """Copies leave their real source glyphs; new syntax appears only after landing."""
        start, finish = float(self.get_time()), self.stage_time(end)
        movers = [source.tag(a).copy() for a, _ in pairs]
        landed = [target.tag(b).copy() for _, b in pairs]
        self.add(*movers)
        self.until(start+.7*(finish-start), *(Transform(m, g) for m, g in zip(movers, landed)))
        used = {id(g) for _, b in pairs for g in target.tag(b).family_members_with_points()}
        rest = VGroup(*(g for g in target.family_members_with_points() if id(g) not in used))
        rest.set_opacity(0)
        self.remove(*movers)
        self.add(target)
        self.until(finish, UpdateFromAlphaFunc(rest, lambda m, a: m.set_opacity(a)))
        self.remove(rest)
        self.add(target)
        return target

    @staticmethod
    def leftover(formula, tags):
        used = {id(g) for tag in tags for g in formula.tag(tag).family_members_with_points()}
        return VGroup(*(g for g in formula.family_members_with_points() if id(g) not in used))


    # ---------- shared graphs ----------
    def graphs(self):
        ticks, axes = Group(), VGroup()
        for origin, up, down in ((top, 3.5, -3.2), (low, 11, 0)):
            axes.add(Line(origin(-.1, 0), origin(6.35, 0)).set_stroke(MUTED, 2))
            axes.add(Line(origin(0, down), origin(0, up)).set_stroke(MUTED, 2))
        for k in range(1, 7):
            axes.add(Line(top(k, 0)+[0, -.05, 0], top(k, 0)+[0, .05, 0]).set_stroke(MUTED, 2))
            axes.add(Line(low(k, 0)+[0, -.05, 0], low(k, 0)+[0, .05, 0]).set_stroke(MUTED, 2))
            ticks.add(self.label(str(k), *(top(k, 0)+[0, .2 if k > 4 else -.2, 0])[:2], size=20, color=MUTED))
            ticks.add(self.label(str(k), *(low(k, 0)+[0, -.2, 0])[:2], size=18, color=MUTED))
        self.f_axes, self.a_axes = VGroup(*axes[:2], *axes[4::2]), VGroup(*axes[2:4], *axes[5::2])
        f_values = [self.label(str(v), X0-.22, top(0, v)[1], size=20, color=MUTED) for v in (-2, 1, 2, 3)]
        a_values = [self.label(str(v), X0-.25, low(0, v)[1], size=20, color=MUTED) for v in (5, 10)]
        for v in (-2, 1, 2, 3):
            self.f_axes.add(Line(top(0, v)-[.05, 0, 0], top(0, v)+[.05, 0, 0]).set_stroke(MUTED, 2))
        for v in (5, 10):
            self.a_axes.add(Line(low(0, v)-[.05, 0, 0], low(0, v)+[.05, 0, 0]).set_stroke(MUTED, 2))
        self.f_ticks = Group(*ticks[::2], *f_values, self.label("t（分）", .12, YF-.26, size=22, color=MUTED), self.text_left("净流入速度 f(t)（升/分）", X0+.15, 2.95, 26, CURVE))
        self.a_ticks = Group(*ticks[1::2], *a_values, self.label("x（分）", .12, YA+.3, size=22, color=MUTED), self.text_left("水量 A(x)（升）", X0+.15, -.3, 26, AMOUNT))
        ts = np.linspace(0, 6, 160)
        self.f_curve = self.poly(lambda: [top(t, f(t)) for t in ts], CURVE, width=4, live=False)
        self.x, self.h = ValueTracker(.001), ValueTracker(.001)

    def area(self, a, b, color, opacity=.4):
        def points():
            lo, hi = min(a(), b()), max(a(), b())
            ts = np.linspace(lo, max(hi, lo+1e-4), 50)
            pts = [top(lo, 0)]+[top(t, f(t)) for t in ts]+[top(ts[-1], 0), top(lo, 0)]
            return pts
        return self.poly(points, color, fill=opacity)

    def amount_curve(self, end):
        return self.poly(lambda: [low(t, amount(t)) for t in np.linspace(0, max(end(), .002), 120)], AMOUNT, width=4)

    def follower(self, point, color):
        return Dot(point(), radius=.075).set_fill(color, 1).add_updater(lambda m: m.move_to(point()))

    def tank(self, cx, bottom, scale, level, width=2.4, height=3.0, rate=None):
        wall = self.poly(lambda: [np.array([cx-width/2, bottom+height, 0]), np.array([cx-width/2, bottom, 0]),
                                  np.array([cx+width/2, bottom, 0]), np.array([cx+width/2, bottom+height, 0])],
                         MUTED, width=4, live=False)

        def points():
            y = bottom+max(level()*scale, .004)
            return [np.array(p) for p in ([cx-width/2+.04, bottom+.03, 0], [cx+width/2-.04, bottom+.03, 0],
                                          [cx+width/2-.04, y+.03, 0], [cx-width/2+.04, y+.03, 0],
                                          [cx-width/2+.04, bottom+.03, 0])]
        if rate is None:
            return Group(self.poly(points, AMOUNT, fill=.6), wall)

        def box(x0, y0, x1, y1):
            return [np.array(q) for q in ([x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0], [x0, y0, 0])]

        def stream():
            if rate() < .02:
                return box(cx, bottom+.05, cx+.001, bottom+.051)
            half = .04*rate()
            return box(cx-half, bottom+max(level()*scale, .004)+.03, cx+half, bottom+height+.28)

        def drain():
            if rate() > -.02:
                return box(cx, bottom+.05, cx+.001, bottom+.051)
            return box(cx+width/2, bottom+.22+.04*rate(), cx+width/2+.55, bottom+.22-.04*rate())
        return Group(self.poly(points, AMOUNT, fill=.6), self.poly(stream, CURVE, fill=.9),
                     self.poly(drain, NEGATIVE, fill=.9), wall)

    # ---------- magnifier ----------
    def panel(self):
        ends = lambda: (min(self.x.get_value(), self.x.get_value()+self.h.get_value()),
                        max(self.x.get_value(), self.x.get_value()+self.h.get_value()))
        zx = lambda t: PX+PW*(t-ends()[0])/(ends()[1]-ends()[0])
        z = lambda t, v: np.array([zx(t), PY+PZ*v, 0])
        ts = lambda: np.linspace(*ends(), 50)
        mean = lambda: (amount(ends()[1])-amount(ends()[0]))/(ends()[1]-ends()[0])
        flat = lambda v: (lambda: [np.array([PX, PY+PZ*v(), 0]), np.array([PX+PW, PY+PZ*v(), 0])])
        self.mean = mean
        self.lowest, self.highest = (lambda: f(ends()[0])), (lambda: f(ends()[1]))
        self.z_fill = self.poly(lambda: [z(ends()[0], 0)]+[z(t, f(t)) for t in ts()]+[z(ends()[1], 0), z(ends()[0], 0)],
                                ACCENT, fill=.32)
        self.z_curve = self.poly(lambda: [z(t, f(t)) for t in ts()], CURVE, width=4)
        self.z_base = Line([PX-.3, PY, 0], [PX+PW+.3, PY, 0]).set_stroke(MUTED, 2)
        self.z_sides = VGroup(self.poly(lambda: [z(ends()[0], 0), z(ends()[0], f(ends()[0]))], ACCENT, width=2),
                              self.poly(lambda: [z(ends()[1], 0), z(ends()[1], f(ends()[1]))], ACCENT, width=2))
        self.z_min = self.poly(flat(self.lowest), MUTED, width=2)
        self.z_max = self.poly(flat(self.highest), MUTED, width=2)
        self.z_mean = self.poly(flat(mean), RATE, width=4)
        self.z = z

    def opening(self, cue):
        self.begin(cue)
        self.focus_begin("question")
        title = self.label("累积量的变化率", 0, 2.35, size=62)
        sub = self.label("为什么正好回到原来的函数？", 0, 1.45, size=40, color=ACCENT)
        self.beat(.14, FadeIn(title))
        self.beat(.22, FadeIn(sub))
        self.mark("title_ready")
        t = ValueTracker(.001)
        tank = self.tank(-3.0, -2.95, .25, lambda: amount(t.get_value()), height=2.85, rate=lambda: f(t.get_value()))
        self.beat(.28, FadeIn(tank))
        line1 = self.text_left("水池开始是空的，净流入速度一直在变。", -.6, .2, 34)
        self.beat(.36, FadeIn(line1))
        clock = self.reading("时间", -.6, -.45, lambda: t.get_value() if t.get_value() > .01 else 0, MUTED, 34, 2, "分")
        speed = self.reading("此刻净流入", -.6, -1.05, lambda: f(t.get_value()), CURVE, 34, 2, "升/分")
        water = self.reading("池里的水量", -.6, -1.65, lambda: amount(t.get_value()), AMOUNT, 34, 2, "升")
        self.beat(.42, FadeIn(clock), FadeIn(speed), FadeIn(water))
        self.beat(.82, t.animate.set_value(4), rate_func=smooth)
        ask = self.text_left("水量此刻变得多快，由什么决定？", -.6, -2.4, 36, ACCENT)
        self.beat(.88, FadeIn(ask))
        self.mark("question_ready")
        self.end_chapter()

    def accumulate(self, cue):
        self.begin(cue)
        self.graphs()
        x = self.x.get_value
        self.beat(.10, FadeIn(self.f_axes), FadeIn(self.f_ticks))
        self.beat(.17, FadeIn(self.f_curve))
        self.define = self.put(r"A(x)=\int_0^{x} f(t)\,dt", 3.75, 2.55, size=44)
        note = self.label("把 0 到 x 这段时间的净流入累积起来", 3.75, 1.65, size=28, color=MUTED)
        self.focus_begin("definition")
        self.beat(.25, FadeIn(self.define), FadeIn(note))
        self.mark("definition_ready")
        self.a_curve = self.amount_curve(lambda: x())
        tank = self.tank(3.75, -2.3, .25, lambda: amount(x()), height=2.8, rate=lambda: f(x()))
        self.beat(.33, FadeIn(self.a_axes), FadeIn(self.a_ticks), FadeIn(tank))
        self.fill = self.area(lambda: 0, lambda: min(x(), x()+self.h.get_value()) if self.h.get_value() < 0 else x(), CURVE)
        self.dot_f = self.follower(lambda: top(x(), f(x())), CURVE)
        self.dot_a = self.follower(lambda: low(x(), amount(x())), AMOUNT)
        self.guide = VGroup(self.poly(lambda: [top(x(), 0), top(x(), f(x()))], CURVE, width=2),
                            self.poly(lambda: [low(x(), 0), low(x(), amount(x()))], AMOUNT, width=2))
        clock = self.reading("x =", 1.1, -2.75, x, MUTED, 34, 2, "分")
        value = self.reading("A(x) =", 3.6, -2.75, lambda: amount(x()), AMOUNT, 34, 2, "升")
        self.add(self.fill, self.a_curve, self.f_curve, self.guide, self.dot_f, self.dot_a)
        self.beat(.37, FadeIn(value), FadeIn(clock))
        self.focus_begin("accumulating")
        self.beat(.86, self.x.animate.set_value(4), rate_func=linear)
        self.mark("accumulated")
        self.end_chapter()

    def strip(self, cue):
        self.begin(cue, self.f_axes, self.f_ticks, self.f_curve, self.a_axes, self.a_ticks, self.fill,
                   self.a_curve, self.guide, self.dot_f, self.dot_a)
        x, h = self.x.get_value, self.h.get_value
        self.beat(.14, self.x.animate.set_value(1), rate_func=smooth)
        full = self.poly(lambda: [low(t, amount(t)) for t in np.linspace(0, 6, 120)], AMOUNT, width=2.5, live=False)
        full.set_stroke(AMOUNT, 2.5, .45)
        self.a_full = full
        tx = self.put("x", *(top(1, 0)+[0, -.5, 0])[:2], size=32)
        self.beat(.20, FadeIn(full), FadeIn(tx))
        self.tx = tx
        self.more = self.area(x, lambda: x()+h(), ACCENT, .62)
        self.dot_q = self.follower(lambda: low(x()+h(), amount(x()+h())), ACCENT)
        self.dot_g = self.follower(lambda: top(x()+h(), f(x()+h())), ACCENT)
        self.add(self.more, self.f_curve, self.dot_f, self.dot_q, self.dot_g)
        self.focus_begin("new_strip")
        self.beat(.40, self.h.animate.set_value(1), rate_func=smooth)
        txh = self.put("x+h", *(top(2, 0)+[0, -.5, 0])[:2], size=32, color=ACCENT)
        self.txh = txh
        self.beat(.46, FadeIn(txh))
        self.mark("strip_ready")
        base = self.poly(lambda: [low(x(), amount(x())), low(x()+h(), amount(x()))], MUTED, width=2)
        rise = self.poly(lambda: [low(x()+h(), amount(x())), low(x()+h(), amount(x()+h()))], ACCENT, width=5)
        self.base, self.rise = base, rise
        self.beat(.56, FadeIn(base), FadeIn(rise))
        self.f1 = SemanticFormula(INC+r"\;=\;", tokens={"inc": INC, "eq": "="}, font_size=38)
        self.f1.move_to([.75+self.f1.get_width()/2, 2.5, 0])
        self.f1_text = self.text_left("新增窄条的面积", self.f1.get_right()[0]+.18, 2.5, 30, ACCENT)
        self.focus_begin("increment")
        self.beat(.66, FadeIn(self.f1), FadeIn(self.f1_text))
        self.mark("increment_ready")
        rows = Group(self.text_left("x = 1，h = 1：", .75, 1.45, 32),
                     self.put(r"A(2)-A(1)=\tfrac{11}{3}-\tfrac{13}{12}=\tfrac{31}{12}\approx 2.583", 3.75, .65, size=40, width=6.0),
                     self.text_left("上图新增的面积，就是下图升高的这一段。", .75, -.45, 30, ACCENT))
        self.beat(.74, FadeIn(rows[0]), FadeIn(rows[1]))
        self.beat(.82, FadeIn(rows[2]))
        self.end_chapter()

    def keep_core(self):
        return (self.f_axes, self.f_ticks, self.f_curve, self.a_axes, self.a_ticks, self.fill, self.a_full, self.a_curve,
                self.dot_f, self.dot_a, self.more, self.dot_q, self.dot_g, self.base, self.rise, self.tx)

    def average(self, cue):
        self.begin(cue, *self.keep_core(), self.txh, self.f1, self.f1_text)
        self.panel()
        flying = self.more.copy().clear_updaters()
        edge = self.poly(lambda: [top(t, f(t)) for t in np.linspace(1, 2, 50)], CURVE, width=4, live=False)
        self.add(flying, edge)
        target = self.z_fill.copy().clear_updaters()
        self.beat(.14, Transform(flying, target), Transform(edge, self.z_curve.copy().clear_updaters()))
        self.remove(flying, edge)
        self.add(self.z_fill, self.z_curve)
        names = Group(self.put("x", PX, PY-.28, size=28), self.put("x+h", PX+PW, PY-.28, size=28, color=ACCENT),
                      self.put("h", PX+PW/2, PY-.28, size=30))
        self.z_names = names
        self.focus_begin("magnified_strip")
        self.beat(.19, FadeIn(self.z_base), FadeIn(self.z_sides), FadeIn(names))
        self.mark("magnifier_ready")
        tip = self.label("把这条窄条放大看", PX+PW/2, 1.0, size=30, color=MUTED)
        self.beat(.24, FadeIn(tip))
        # A level raised from the left height to the mean makes the two corner pieces equal in area.
        level = ValueTracker(f(1))
        bar = self.poly(lambda: [np.array([PX, PY+PZ*level.get_value(), 0]),
                                 np.array([PX+PW, PY+PZ*level.get_value(), 0])], RATE, width=4)
        ask = self.label("多高的矩形，面积和它一样？", PX+PW/2, 1.0, size=30, color=RATE)
        self.beat(.27, FadeOut(tip))
        self.beat(.31, FadeIn(ask), FadeIn(bar))
        m = self.mean()
        self.beat(.40, level.animate.set_value(m), rate_func=smooth)
        ts = np.linspace(1, 2, 200)
        cross = ts[np.argmin(abs(np.array([f(t) for t in ts])-m))]
        extra = self.poly(lambda: [self.z(cross, m)]+[self.z(t, f(t)) for t in np.linspace(cross, 2, 40)]
                          + [self.z(2, m), self.z(cross, m)], RATE, fill=.75, live=False)
        gap = self.poly(lambda: [self.z(cross, m)]+[self.z(t, f(t)) for t in np.linspace(cross, 1, 40)]
                        + [self.z(1, m), self.z(cross, m)], RATE, fill=.75, live=False)
        self.focus_begin("equal_area")
        clip = self.poly(lambda: [self.z(1, 0)]+[self.z(t, min(f(t), m)) for t in np.linspace(1, 2, 50)]
                         + [self.z(2, 0), self.z(1, 0)], ACCENT, fill=.32, live=False)
        self.beat(.45, FadeIn(extra))
        self.remove(self.z_fill)
        self.add(clip, self.z_curve, self.z_sides, self.z_base, bar, extra)
        self.beat(.56, Transform(extra, gap, path_arc=-np.pi))
        self.mark("equal_area_ready")
        equal = self.label("高出的部分，恰好补上缺口", PX+PW/2, 1.0, size=30, color=RATE)
        self.beat(.585, FadeOut(ask))
        self.beat(.61, FadeIn(equal))
        self.add(self.z_mean)
        self.remove(bar)
        name_m = self.put("m", PX-.4, PY+PZ*m, size=36, color=RATE)
        mean_tip = Group(self.label("平均高度", PX+PW+.85, PY+PZ*m+.2, size=28, color=RATE),
                         self.label("2.583", PX+PW+.85, PY+PZ*m-.2, size=28, color=RATE))
        self.name_m = name_m
        self.beat(.66, FadeIn(name_m), FadeIn(mean_tip))
        self.f2 = SemanticFormula(INC+r"\;=\;m\cdot h", tokens={"inc": INC, "eq": "=", "m": "m", "h": ("h", 1)},
                                  colors={"m": RATE, "h": ACCENT}, font_size=38)
        self.f2.shift([self.f1.get_left()[0]-self.f2.get_left()[0],
                       self.f1.tag("inc").get_center()[1]-self.f2.tag("inc").get_center()[1], 0])
        self.focus_begin("mean_equation")
        fresh = VGroup(*(g for g in self.f2.family_members_with_points()
                         if not any(g is k for tag in ("inc", "eq") for k in self.f2.tag(tag).family_members_with_points())))
        fresh.set_opacity(0)
        self.remove(self.f1)
        self.add(self.f2)
        self.beat(.72, FadeOut(self.f1_text))
        self.beat(.76, UpdateFromAlphaFunc(fresh, lambda mob, a: mob.set_opacity(a)))
        self.remove(fresh)
        self.add(self.f2)
        divide = self.text_left("两边除以 h", 5.1, 2.5, 28, MUTED)
        self.f3 = SemanticFormula(r"\frac{"+INC+r"}{h}\;=\;m", tokens={"inc": INC, "h": ("h", 1), "eq": "=", "m": "m"},
                                  colors={"m": RATE, "h": ACCENT}, font_size=40)
        self.f3.move_to([.75+self.f3.get_width()/2, 2.35, 0])
        self.until(self.stage_time(.80), FadeOut(equal), FadeIn(divide))
        self.divide_by_h(.92)
        self.until(self.stage_time(.95), FadeOut(divide))
        self.mark("mean_rate_ready")
        self.clip, self.gap = clip, extra
        self.corner = self.poly(lambda: [self.z(cross, m)]+[self.z(t, f(t)) for t in np.linspace(cross, 2, 40)]
                                + [self.z(2, m), self.z(cross, m)], ACCENT, fill=.32, live=False)
        self.end_chapter()

    def divide_by_h(self, end):
        """h leaves the product, passes below the row and becomes the denominator of the whole change."""
        a, b = self.f2, self.f3
        start, finish = float(self.get_time()), self.stage_time(end)
        step = lambda q: start+q*(finish-start)
        parts = {k: a.tag(k).copy() for k in ("inc", "eq", "m", "h")}
        dot = self.leftover(a, ["inc", "eq", "m", "h"]).copy()
        bar = self.leftover(b, ["inc", "eq", "m", "h"]).copy()
        self.remove(a)
        self.add(*parts.values(), dot)
        self.until(step(.12), FadeOut(dot))
        below = b.tag("h").copy().move_to([parts["h"].get_center()[0], b.tag("h").get_center()[1]-.05, 0])
        self.until(step(.38), Transform(parts["h"], below),
                   *(Transform(parts[k], b.tag(k).copy()) for k in ("inc", "eq", "m")))
        self.until(step(.52), FadeIn(bar))
        self.until(finish, Transform(parts["h"], b.tag("h").copy()))
        self.remove(*parts.values(), bar)
        self.add(b)

    def squeeze(self, cue):
        core = self.keep_core()
        self.begin(cue, *core, self.f3, self.clip, self.gap, self.z_base, self.z_curve, self.z_sides, self.z_mean,
                   self.z_names)
        x, h = self.x.get_value, self.h.get_value
        self.add(self.corner)
        self.beat(.06, FadeOut(self.gap), FadeIn(self.corner))
        self.remove(self.clip, self.corner)
        self.add(self.z_fill, self.z_curve, self.z_sides, self.z_mean, self.z_base)
        secant = self.poly(lambda: [low(t, amount(x())+(t-x())*self.mean())
                                    for t in (min(.65, x()+h()-.1), 4.6)], RATE, width=3)
        self.secant = secant
        self.sec_name = self.label("割线斜率 = m", -1.75, -1.95, size=26, color=RATE)
        tag = self.put("x+h", 0, 0, size=32, color=ACCENT)
        tag.add_updater(lambda m: m.move_to([max(top(x()+h(), 0)[0], top(x(), 0)[0]+.6), YF-.5, 0]))
        tag.update()
        self.beat(.10, FadeIn(secant), FadeIn(self.sec_name), FadeIn(tag))
        zoom = self.label("横向放大", PX+PW+1.1, PY+.3, size=24, color=MUTED)
        left_name = self.put("f(x)", PX-.55, PY+PZ*f(1), size=30, color=CURVE)
        right_name = self.put("f(x+h)", 0, 0, size=30, color=CURVE)
        right_name.add_updater(lambda m: m.move_to([PX+PW+.75, PY+PZ*self.highest(), 0]))
        right_name.update()
        self.beat(.14, FadeIn(self.z_min), FadeIn(self.z_max), FadeIn(left_name), FadeIn(right_name), FadeIn(zoom))
        cells = Group(self.reading("最小", .35, -2.65, self.lowest, INK, 31, 3),
                      self.reading("平均 m", 2.4, -2.65, self.mean, RATE, 31, 3),
                      self.reading("最大", 5.0, -2.65, self.highest, INK, 31, 3))
        width = self.reading("h =", 5.05, 2.35, h, ACCENT, 34, 3)
        self.focus_begin("shrinking_strip")
        self.beat(.18, FadeIn(cells), FadeIn(width))
        bound = Group(self.put(r"f(x)\le m\le f(x+h)", 2.55, 1.3, size=38),
                      self.label("（这一段 f 递增）", 5.6, 1.3, size=26, color=MUTED))
        self.beat(.22, FadeIn(bound))
        for end, value in ((.31, .5), (.39, .2), (.48, .05), (.56, .02)):
            self.beat(end-.02, self.h.animate.set_value(value), rate_func=smooth)
            self.beat(end)
        self.mark("heights_squeezed")
        self.focus_end("shrinking_strip")
        why = Group(self.text_left("f 在 x 处连续：最小、最大高度都趋近 f(x)，", .6, 1.25, 29),
                    self.text_left("夹在中间的 m 也趋近 f(x)。", .6, .65, 29))
        self.beat(.585, FadeOut(bound))
        self.focus_begin("limit")
        self.beat(.62, FadeIn(why))
        self.beat(.70)
        self.beat(.725, FadeOut(why), FadeOut(width))
        self.f4 = SemanticFormula(r"\lim_{h\to 0^+}\frac{"+INC+r"}{h}\;=\;f(x)",
                                  tokens={"lim": r"\lim_{h\to 0^+}", "inc": INC, "h": ("h", 2), "eq": "=", "fx": "f(x)"},
                                  colors={"fx": CURVE, "h": ACCENT}, font_size=38)
        self.f4.move_to([.6+self.f4.get_width()/2, 2.35, 0])
        # The same f(x) seen on the squeezed strip travels to the place m leaves.
        a, b = self.f3, self.f4
        parts = {k: a.tag(k).copy() for k in ("inc", "h", "eq", "m")}
        bar = self.leftover(a, ["inc", "h", "eq", "m"]).copy()
        bar_to = self.leftover(b, ["lim", "inc", "h", "eq", "fx"]).copy()
        limit, rising = b.tag("lim").copy(), left_name.copy()
        self.remove(a)
        self.add(*parts.values(), bar)
        self.beat(.738, FadeOut(parts["m"]))
        self.beat(.765, *(Transform(parts[k], b.tag(k).copy()) for k in ("inc", "h", "eq")), Transform(bar, bar_to))
        self.beat(.79, FadeIn(limit))
        self.add(rising)
        self.beat(.84, Transform(rising, b.tag("fx").copy()))
        self.remove(parts["inc"], parts["h"], parts["eq"], bar, limit, rising)
        self.add(b)
        self.mark("limit_ready")
        away = [self.z_fill, self.z_base, self.z_curve, self.z_sides, self.z_mean, self.z_min, self.z_max, self.z_names,
                cells, left_name, right_name, zoom, tag]
        for mob in away:
            mob.clear_updaters()
        self.beat(.87, *(FadeOut(mob) for mob in away), FadeOut(self.sec_name))
        self.beat(.90, FadeIn(self.label("这是从右边靠近，左边也要看", 3.4, .6, size=34, color=ACCENT)))
        self.mark("right_limit_ready")
        self.end_chapter()

    def left(self, cue):
        core = self.keep_core()
        self.begin(cue, *core, self.secant)
        x, h = self.x.get_value, self.h.get_value
        self.beat(.07)
        self.remove(self.secant)
        self.panel()
        tag = self.put("x+h", 0, 0, size=32, color=ACCENT)
        tag.add_updater(lambda m: m.move_to([min(top(x()+h(), 0)[0], top(x(), 0)[0]-.6), YF-.5, 0]))
        hide = [self.more, self.dot_q, self.dot_g, self.base, self.rise]
        self.remove(*hide)
        self.h.set_value(-.6)
        for mob in (*hide, tag):
            mob.update()
        self.secant.update()
        names = Group(self.put("x+h", PX, PY-.28, size=28, color=ACCENT), self.put("x", PX+PW, PY-.28, size=28),
                      self.put("|h|", PX+PW/2, PY-.28, size=30, color=ACCENT))
        say = self.text_left("从左边取窄条：h < 0", .6, 2.75, 32)
        self.focus_begin("left_strip")
        self.beat(.15, FadeIn(say), *(FadeIn(mob) for mob in hide), FadeIn(tag))
        self.add(self.f_curve, self.dot_f, self.dot_a)
        less = self.text_left("A(x+h) 比 A(x) 少了这一条，面积是 m|h|", .6, 2.15, 29, ACCENT)
        for mob in (self.z_fill, self.z_curve, self.z_sides, self.z_mean, self.z_min, self.z_max, self.secant):
            mob.update()
        cells = Group(self.reading("最小", .35, -2.65, self.lowest, INK, 31, 3),
                      self.reading("平均 m", 2.4, -2.65, self.mean, RATE, 31, 3),
                      self.reading("最大", 5.0, -2.65, self.highest, INK, 31, 3))
        self.beat(.22, *(FadeIn(mob) for mob in (less, self.z_fill, self.z_base, self.z_curve, self.z_sides, self.z_mean,
                                                 self.z_min, self.z_max, names, self.secant, cells)))
        one = SemanticFormula(INC+r"\;=\;-m\,|h|", tokens={"inc": INC, "eq": "=", "minus": ("-", 1), "m": "m", "abs": "|h|"},
                              colors={"m": RATE, "abs": ACCENT}, font_size=38)
        one.move_to([.6+one.get_width()/2, 1.35, 0])
        self.beat(.30, FadeIn(one))
        self.mark("left_ready")
        self.beat(.40)
        two = SemanticFormula(r"\frac{"+INC+r"}{h}\;=\;\frac{-m\,|h|}{-|h|}\;=\;m",
                              tokens={"inc": INC, "h": ("h", 1), "eq": ("=", 0), "minus": ("-", 1), "m": ("m", 0), "abs": ("|h|", 0),
                                      "low": ("|h|", 1), "eq2": ("=", 1), "m2": ("m", 1)},
                              colors={"m": RATE, "abs": ACCENT, "h": ACCENT, "low": ACCENT, "m2": RATE}, font_size=38)
        two.move_to([.6+two.get_width()/2, 1.2, 0])
        divide = self.text_left("除以 h = −|h|，负号约去", .6, 2.15, 29, MUTED)
        self.beat(.44, FadeOut(less))
        self.beat(.47, FadeIn(divide))
        parts = {k: one.tag(k).copy() for k in ("inc", "eq", "minus", "m", "abs")}
        tail = VGroup(two.tag("eq2").copy(), two.tag("m2").copy())
        fresh = self.leftover(two, ["inc", "eq", "minus", "m", "abs", "eq2", "m2"]).copy()
        self.remove(one)
        self.add(*parts.values())
        self.beat(.53, *(Transform(parts[k], two.tag(k).copy()) for k in parts))
        self.beat(.56, FadeIn(fresh))
        self.beat(.59, FadeIn(tail))
        self.remove(*parts.values(), fresh, tail)
        self.add(two)
        width = self.reading("h =", 5.0, 2.75, h, ACCENT, 32, 3)
        self.beat(.61, FadeIn(width))
        self.beat(.85, self.h.animate.set_value(-.02), rate_func=smooth)
        end = self.text_left("左右都趋近 f(1) = 2：", .6, .3, 32, ACCENT)
        self.beat(.88, FadeIn(end))
        result = SemanticFormula(r"A'(x)\;=\;f(x)", tokens={"da": "A'(x)", "eq": "=", "fx": "f(x)"},
                                 colors={"fx": CURVE, "da": AMOUNT}, font_size=44).move_to([5.3, .3, 0])
        slope = self.label("割线趋向切线，斜率 = f(x)", -1.95, -1.95, size=24, color=RATE)
        self.beat(.92, FadeIn(result), FadeIn(slope))
        self.mark("derivative_ready")
        self.mark("two_sided_ready")
        self.end_chapter()

    def trace(self, cue):
        self.begin(cue, self.f_axes, self.f_ticks, self.f_curve, self.a_axes, self.a_ticks, self.a_full, self.dot_f,
                   self.dot_a)
        x = self.x.get_value
        plus = self.area(lambda: 0, lambda: min(x(), 5), CURVE)
        minus = self.area(lambda: 5, lambda: max(x(), 5), NEGATIVE, .6)
        tangent = self.poly(lambda: [low(t, amount(x())+(t-x())*f(x())) for t in (x()-.8, x()+.8)], RATE, width=4)
        stem = self.poly(lambda: [top(x(), 0), top(x(), f(x()))], RATE, width=4)
        tank = self.tank(5.35, -2.7, .24, lambda: amount(x()), width=1.7, height=2.7, rate=lambda: f(x()))
        height = self.reading("上图高度 f(x) =", .75, 2.6, lambda: f(x()), CURVE, 34, 3)
        slope = self.reading("下图切线斜率 =", .75, 1.9, lambda: f(x()), RATE, 34, 3)
        water = self.reading("水量", .75, 1.2, lambda: amount(x()), AMOUNT, 34, 2, "升")
        self.add(plus, minus, self.f_curve, self.dot_f)
        self.focus_begin("height_is_slope")
        self.beat(.12, FadeIn(tangent), FadeIn(stem), FadeIn(tank), FadeIn(height), FadeIn(slope), FadeIn(water))
        self.mark("trace_ready")
        self.beat(.26, self.x.animate.set_value(2.5), rate_func=smooth)
        one = Group(self.text_left("f 最高：", .75, -.1, 32, ACCENT), self.text_left("水量涨得最快", .75, -.75, 32))
        self.beat(.31, FadeIn(one))
        self.beat(.40)
        self.beat(.43, FadeOut(one))
        self.beat(.58, self.x.animate.set_value(5), rate_func=smooth)
        two = Group(self.text_left("f = 0：", .75, -.1, 32, ACCENT), self.text_left("切线水平，水量最大", .75, -.75, 32))
        self.beat(.63, FadeIn(two))
        self.mark("zero_ready")
        self.beat(.71)
        self.beat(.74, FadeOut(two))
        self.focus_end("height_is_slope")
        self.focus_begin("negative_rate")
        self.beat(.86, self.x.animate.set_value(5.8), rate_func=smooth)
        three = Group(self.text_left("f < 0：", .75, -.1, 32, NEGATIVE), self.text_left("新增面积记作负，", .75, -.75, 32),
                      self.text_left("水量减少，池里还有水", .75, -1.4, 32))
        self.beat(.90, FadeIn(three))
        self.mark("negative_ready")
        self.end_chapter()

    def jump(self, cue):
        self.begin(cue)
        def g(t):
            return 1. if t < 3 else 2.5
        big = lambda t, v: np.array([X0+SX*t, .55+.72*v, 0])
        small = lambda t, v: np.array([X0+SX*t, -2.6+.21*v, 0])
        axes = VGroup(*(Line(a, b).set_stroke(MUTED, 2) for a, b in (
            (big(-.1, 0), big(6.3, 0)), (big(0, 0), big(0, 3.2)), (small(-.1, 0), small(6.3, 0)), (small(0, 0), small(0, 11)))))
        names = Group(self.text_left("净流入速度（升/分），t = 3 处跳变", X0+.15, 2.95, 26, CURVE),
                      self.text_left("水量（升）", X0+.15, -.3, 26, AMOUNT),
                      self.label("3", *big(3, 0)[:2]-np.array([0, .2]), size=18, color=MUTED),
                      self.label("3", *small(3, 0)[:2]-np.array([0, .2]), size=20, color=MUTED),
                      self.label("1", X0-.25, big(0, 1)[1], size=22, color=MUTED),
                      self.label("2.5", X0-.32, big(0, 2.5)[1], size=22, color=MUTED))
        low_part = self.poly(lambda: [big(0, 1), big(3, 1)], CURVE, width=4, live=False)
        high_part = self.poly(lambda: [big(3, 2.5), big(6, 2.5)], CURVE, width=4, live=False)
        line = self.poly(lambda: [small(0, 0), small(3, 3), small(6, 10.5)], AMOUNT, width=4, live=False)
        self.focus_begin("jump")
        ends = Group(Dot(big(3, 2.5), radius=.08).set_fill(CURVE, 1),
                     Dot(big(3, 1), radius=.08).set_fill("#101416", 1).set_stroke(CURVE, 3, 1))
        self.beat(.18, FadeIn(axes), FadeIn(names), FadeIn(low_part), FadeIn(high_part), FadeIn(ends), FadeIn(line))
        self.mark("jump_ready")
        k = ValueTracker(1.2)
        strip_l = self.poly(lambda: [big(3-k.get_value(), 0), big(3-k.get_value(), 1), big(3, 1), big(3, 0),
                                     big(3-k.get_value(), 0)], ACCENT, fill=.6)
        strip_r = self.poly(lambda: [big(3, 0), big(3, 2.5), big(3+k.get_value(), 2.5), big(3+k.get_value(), 0),
                                     big(3, 0)], RATE, fill=.6)
        tl = self.text_left("左边窄条的平均高度：1", .75, 2.3, 34, ACCENT)
        tr = self.text_left("右边窄条的平均高度：2.5", .75, 1.5, 34, RATE)
        self.beat(.28, FadeIn(strip_l), FadeIn(tl))
        self.add(low_part, ends)
        self.beat(.38, FadeIn(strip_r), FadeIn(tr))
        self.add(low_part, high_part, ends)
        self.beat(.60, k.animate.set_value(.12), rate_func=smooth)
        slope_l = self.poly(lambda: [small(1, 1), small(5, 5)], ACCENT, width=3, live=False)
        slope_r = self.poly(lambda: [small(2, .5), small(5, 8)], RATE, width=3, live=False)
        self.add(strip_l, strip_r, low_part, high_part, ends)
        self.beat(.68, FadeIn(slope_l), FadeIn(slope_r), FadeIn(self.label("斜率 1", *(small(5, 5)+[.45, .1, 0])[:2], size=24, color=ACCENT)),
                  FadeIn(self.label("斜率 2.5", *(small(5, 8)+[-.85, .12, 0])[:2], size=24, color=RATE)))
        end = Group(self.text_left("窄条再窄，两边仍然不同：", .75, .1, 32),
                    self.text_left("水量图在这里有折角，没有导数。", .75, -.6, 32),
                    self.text_left("刚才的 A'(x) = f(x)，用到了 f 在 x 处连续。", .75, -1.75, 28, ACCENT))
        self.beat(.76, FadeIn(end[0]), FadeIn(end[1]))
        self.beat(.84, FadeIn(end[2]))
        self.mark("corner_ready")
        self.end_chapter()

    def ending(self, cue):
        self.begin(cue)
        steps = Group(self.label("新增面积", -4.6, 2.55, size=38, color=ACCENT),
                      self.label("除以宽度 = 平均高度", 0, 2.55, size=38, color=RATE),
                      self.label("趋近当前高度", 4.8, 2.55, size=38, color=CURVE))
        arrows = VGroup(Arrow([-3.5, 2.55, 0], [-2.2, 2.55, 0], buff=.05).set_color(MUTED),
                        Arrow([2.2, 2.55, 0], [3.3, 2.55, 0], buff=.05).set_color(MUTED))
        a = SemanticFormula(r"A'(x)\;=\;f(x)", tokens={"da": "A'(x)", "eq": "=", "fx": "f(x)"},
                            colors={"fx": CURVE, "da": AMOUNT}, font_size=54).move_to([0, 1.35, 0])
        self.focus_begin("summary")
        self.beat(.06, FadeIn(steps[0]), FadeIn(a))
        self.beat(.12, FadeIn(arrows[0]), FadeIn(steps[1]))
        self.beat(.18, FadeIn(arrows[1]), FadeIn(steps[2]))
        b = SemanticFormula(r"\frac{d}{dx}\int_0^{x} f(t)\,dt\;=\;f(x)", tokens={"eq": "=", "fx": "f(x)"},
                            colors={"fx": CURVE}, font_size=54).move_to([-1.2, 1.35, 0])
        parts = {k: a.tag(k).copy() for k in ("eq", "fx")}
        old, fresh = self.leftover(a, ["eq", "fx"]).copy(), self.leftover(b, ["eq", "fx"]).copy()
        self.beat(.22)
        self.remove(a)
        self.add(*parts.values(), old)
        self.beat(.25, FadeOut(old))
        self.beat(.28, *(Transform(parts[k], b.tag(k).copy()) for k in parts))
        self.beat(.31, FadeIn(fresh))
        self.remove(*parts.values(), fresh)
        self.add(b)
        need = self.label("f 在 x 处连续", b.get_right()[0]+1.35, 1.35, size=32, color=INK)
        self.beat(.34, FadeIn(need))
        reply = self.label("水量此刻变得多快，等于此刻的净流入速度。", 0, .2, size=36, color=ACCENT)
        self.beat(.40, FadeIn(reply))
        self.mark("summary_ready")
        self.beat(.46)
        self.focus_begin("exit_question")
        ask = self.label("换一个起点：", -2.6, -.9, size=34, color=ACCENT)
        change = self.put(r"B(x)=\int_1^{x} f(t)\,dt", 1.1, -.9, size=42)
        q1 = self.label("B 的图像和 A 的图像差在哪里？", 0, -1.85, size=34)
        q2 = self.label("B 的变化率会不会改变？用窄条说明理由。", 0, -2.6, size=34)
        self.beat(.51, FadeIn(ask), FadeIn(change))
        self.beat(.58, FadeIn(q1), FadeIn(q2))
        self.mark("exit_ready")
        self.end_chapter()

    def construct(self):
        steps = (self.opening, self.accumulate, self.strip, self.average, self.squeeze, self.left, self.trace,
                 self.jump, self.ending)
        for cue, step in zip(self.cues, steps, strict=True):
            if cue["id"] != step.__name__:
                raise ValueError("Plan and scene cue order disagree")
            step(cue)
