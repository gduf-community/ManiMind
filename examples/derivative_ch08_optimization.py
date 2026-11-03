"""Chapter 08: one physical cut length, hinged native panels, and feasible optima.

Coordinates in panel_vertices are centimeters, not a physics simulation. Native
polygons use a fixed orthographic basis. Trackers and sampled geometry belong to
one construct; source/model/timing changes invalidate its measured journal.
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


def dimensions(x, allow_degenerate=False):
    finite(x)
    if not 0 <= x <= 6 or (not allow_degenerate and not 0 < x < 6):
        raise ValueError("A box needs 0 < x < 6 cm; only boundary checks allow degeneracy")
    return (12-2*x, 12-2*x, x)


def volume(x):
    length, width, height = dimensions(x, allow_degenerate=True)
    return length*width*height


def derivative(x):
    return 12*(finite(x)-2)*(x-6)


def feasible(x, min_height=0):
    finite(x)
    finite(min_height)
    if not 0 <= min_height < 6:
        raise ValueError("Minimum height must lie in [0,6) cm")
    return bool(0 < x < 6 and x >= min_height)


def optimum(min_height=0):
    feasible(2, min_height)
    x = max(2, min_height)
    return {"x_cm": x, "dimensions_cm": dimensions(x), "volume_cm3": volume(x)}


def panel_vertices(x, angle):
    length, _, height = dimensions(x)
    finite(angle)
    if not 0 <= angle <= math.pi/2:
        raise ValueError("Fold angle must lie between 0 and pi/2")
    reach, z = height*math.cos(angle), height*math.sin(angle)
    return {
        "base": ((0, 0, 0), (length, 0, 0), (length, length, 0), (0, length, 0)),
        "front": ((0, 0, 0), (length, 0, 0), (length, -reach, z), (0, -reach, z)),
        "back": ((0, length, 0), (length, length, 0), (length, length+reach, z), (0, length+reach, z)),
        "left": ((0, 0, 0), (0, length, 0), (-reach, length, z), (-reach, 0, z)),
        "right": ((length, 0, 0), (length, length, 0), (length+reach, length, z), (length+reach, 0, z)),
    }


def projected(point, x):
    length, _, _ = dimensions(x)
    a, b, z = point
    a, b = a-length/2, b-length/2
    return (-3.3+.36*(a-b)/math.sqrt(2), -.35+.36*((a+b)/math.sqrt(6)+z*math.sqrt(2/3)), 0.)


def net_point(x, y):
    return (-3.45+.35*(x-6), .1+.35*(y-6), 0.)


_argv = sys.argv
try:
    sys.argv = _argv[:1]
    import numpy as np
    from manimlib import (
        Dot, FadeIn, FadeOut, Group, Line, Polygon, ShowCreation,
        ValueTracker, VGroup, VMobject, linear,
    )
    from derivative_chapter_shared import ChapterScene, INK, MUTED, CURVE, RATE, ACCENT
finally:
    sys.argv = _argv
del _argv

CUE_IDS = ("opening", "cut", "fold", "objective", "optimize", "boundary", "constraint", "closing")
CUE_DURATIONS = (24, 44, 46, 40, 54, 30, 44, 30)
FACE_ORDER = ("back", "left", "base", "right", "front")


class DerivativeCh08Optimization(ChapterScene):
    def panels(self, x, angle):
        faces = panel_vertices(x, angle)
        return VGroup(*(Polygon(*(projected(p, x) for p in faces[name]),
                                fill_color=CURVE if name == "base" else ACCENT,
                                fill_opacity=.22 if name == "base" else .12,
                                stroke_color=CURVE if name == "base" else ACCENT, stroke_width=2)
                        for name in FACE_ORDER))

    def net(self, x):
        L = 12-x
        base = Polygon(*(net_point(a, b) for a, b in ((x, x), (L, x), (L, L), (x, L))),
                       fill_color=CURVE, fill_opacity=.17, stroke_color=CURVE, stroke_width=2.5)
        sides = VGroup(*(Polygon(*(net_point(a, b) for a, b in coords), fill_color=ACCENT,
                                 fill_opacity=.08, stroke_color=ACCENT, stroke_width=1.5)
                         for coords in (((x, 0), (L, 0), (L, x), (x, x)),
                                        ((x, L), (L, L), (L, 12), (x, 12)),
                                        ((0, x), (x, x), (x, L), (0, L)),
                                        ((L, x), (12, x), (12, L), (L, L)))))
        corners = VGroup(*(Polygon(*(net_point(a, b) for a, b in ((u, v), (u+x, v), (u+x, v+x), (u, v+x))),
                                   fill_color=RATE, fill_opacity=.28, stroke_color=RATE, stroke_width=2)
                           for u, v in ((0, 0), (12-x, 0), (12-x, 12-x), (0, 12-x))))
        return VGroup(base, sides, corners)

    def opening(self, cue):
        self.begin_chapter(cue)
        self.beat(.15, FadeIn(self.net(2)),
                  FadeIn(self.put(r"12\ \mathrm{cm}\ \times\ 12\ \mathrm{cm}", 3.5, 1.95, size=40, width=5.4)),
                  FadeIn(self.label("四角裁方块，折成无盖盒", 3.5, .75, size=30, width=5.5)),
                  FadeIn(self.label("怎样裁，体积才最大？", 3.5, -.6, size=31, color=ACCENT, width=5.5)))
        self.mark("box_problem_ready")
        self.focus_begin("box_problem")
        self.end_chapter()

    def cut(self, cue):
        self.begin_chapter(cue)
        x = ValueTracker(1)
        net = self.net(1)
        x_num = self.number(1, decimals=2, size=37, color=ACCENT).move_to([4.1, 1.65, 0])
        l_num = self.number(10, decimals=2, size=37, color=CURVE).move_to([4.1, -.4, 0])
        self.beat(.12, FadeIn(net), FadeIn(self.put(r"12\ \mathrm{cm}", -3.45, 2.6, size=32)),
                  FadeIn(self.put("x=", 2, 1.65, size=35, color=ACCENT)), FadeIn(x_num),
                  FadeIn(self.put(r"\mathrm{cm}", 5.45, 1.65, size=30)),
                  FadeIn(self.put(r"12-2x=", 2.2, -.4, size=33, color=CURVE, width=2.9)), FadeIn(l_num),
                  FadeIn(self.put(r"\mathrm{cm}", 5.45, -.4, size=30)),
                  FadeIn(self.label("四个角裁去同样大的正方形", 3.5, .7, size=26, width=5.6)))
        driver = Group()

        def update(_):
            size = x.get_value()
            net.become(self.net(size))
            x_num.set_value(size)
            l_num.set_value(12-2*size)
            self.sample("cut_size", x_cm=size, base_cm=12-2*size, removed_area_cm2=4*size*size)

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.mark("same_cut_length_ready")
        self.focus_begin("same_cut_length")
        self.beat(.31, x.animate.set_value(3), rate_func=linear)
        self.beat(.44, x.animate.set_value(2), rate_func=linear)
        self.focus_end("same_cut_length")
        driver.clear_updaters()
        dim = VGroup(Line(net_point(0, -1.35), net_point(2, -1.35), color=ACCENT, stroke_width=3),
                     Line(net_point(2, -1.35), net_point(10, -1.35), color=CURVE, stroke_width=3),
                     Line(net_point(10, -1.35), net_point(12, -1.35), color=ACCENT, stroke_width=3))
        self.beat(.53, ShowCreation(dim), FadeIn(self.label("x       12 − 2x       x", -3.45, -2.85, size=24, width=5.3)),
                  FadeIn(self.label("每个方向都从两端各减去 x", 3.5, -1.35, size=28, width=5.5)))
        self.mark("base_dimension_ready")
        self.focus_begin("base_dimension")
        self.beat(.70)
        self.focus_end("base_dimension")
        self.focus_begin("corners_removed")
        self.beat(.86, *(corner.animate.shift(vector) for corner, vector in zip(net[2],
                  ([-.26, -.26, 0], [.26, -.26, 0], [.26, .26, 0], [-.26, .26, 0]), strict=True)))
        self.beat(.92, FadeOut(net[2]))
        self.focus_end("corners_removed")
        self.mark("net_without_corners_ready")
        self.end_chapter()

    def fold(self, cue):
        self.begin_chapter(cue)
        angle = ValueTracker(0)
        faces = self.panels(2, 0)
        self.beat(.12, FadeIn(faces),
                  FadeIn(self.label("保留同一张裁好的纸板", 3.5, 1.95, size=29, width=5.5)),
                  FadeIn(self.put(r"x=2\ \mathrm{cm}", 3.5, .95, size=39, color=ACCENT, width=5.5)),
                  FadeIn(self.put(r"12-2x=8\ \mathrm{cm}", 3.5, -.05, size=37, color=CURVE, width=5.5)))
        self.mark("flat_panels_ready")
        self.focus_begin("flat_panels")
        self.beat(.26)
        self.focus_end("flat_panels")
        driver = Group()

        def update(_):
            theta = angle.get_value()
            faces.become(self.panels(2, theta))
            self.sample("fold", x_cm=2, angle=theta, panel_vertices_cm=panel_vertices(2, theta))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("hinge_motion")
        self.beat(.62, angle.animate.set_value(math.pi/2), rate_func=linear)
        self.focus_end("hinge_motion")
        driver.clear_updaters()
        self.beat(.69, FadeIn(self.label("裁去的边长 x，折起后成为盒高", 3.5, -1.15, size=28, width=5.6)),
                  FadeIn(self.put(r"8\times8\times2\ \mathrm{cm}", 3.5, -2.15, size=37, width=5.5)))
        self.mark("fold_dimensions_ready")
        self.focus_begin("fold_dimensions")
        self.end_chapter()

    def objective(self, cue):
        self.begin_chapter(cue)
        self.beat(.12, FadeIn(self.panels(2, math.pi/2)),
                  FadeIn(self.put(r"\ell=w=12-2x,\quad h=x", 3.5, 2.15, size=34, width=5.7)),
                  FadeIn(self.label("长度统一用 cm", 3.5, 1.4, size=26, color=MUTED, width=5.5)))
        self.mark("dimensions_to_volume_ready")
        self.focus_begin("dimensions_to_volume")
        self.beat(.31)
        self.focus_end("dimensions_to_volume")
        self.beat(.38, FadeIn(self.put(r"V=\ell w h=x(12-2x)^2", 3.5, .45, size=38, color=CURVE, width=5.7)),
                  FadeIn(self.put(r"V:\ \mathrm{cm}^3", 3.5, -.35, size=32, color=CURVE, width=5.5)))
        self.mark("volume_objective_ready")
        self.focus_begin("volume_objective")
        self.beat(.60)
        self.focus_end("volume_objective")
        self.beat(.68, FadeIn(self.put(r"x>0,\quad12-2x>0", 3.5, -1.35, size=35, width=5.7)),
                  FadeIn(self.put(r"0<x<6\quad(\mathrm{cm})", 3.5, -2.25, size=38, color=ACCENT, width=5.7)))
        self.mark("physical_domain_ready")
        self.focus_begin("physical_domain")
        self.end_chapter()

    def optimize(self, cue):
        self.begin_chapter(cue)
        self.beat(.10, FadeIn(self.put(r"V=x(12-2x)^2,\quad0<x<6", 0, 2.35, size=40)))
        row1 = self.put(r"V'=(12-2x)^2-4x(12-2x)", 0, 1.35, size=40)
        row2 = self.put(r"=(12-2x)(12-6x)", 0, .35, size=40)
        row3 = self.put(r"=12(x-2)(x-6)", 0, -.65, size=42, color=RATE)
        self.beat(.22, FadeIn(row1))
        self.mark("product_derivative_ready")
        self.focus_begin("product_derivative")
        self.beat(.34)
        self.focus_end("product_derivative")
        self.beat(.43, FadeIn(row2))
        self.focus_begin("factor_derivative")
        self.beat(.55, FadeIn(row3))
        self.mark("factor_derivative_ready")
        self.beat(.62)
        self.focus_end("factor_derivative")
        self.beat(.68, FadeOut(row1), FadeOut(row2))
        self.beat(.75, FadeIn(self.put(r"0<x<2:\ V'>0\qquad2<x<6:\ V'<0", 0, 1.2, size=37)),
                  FadeIn(self.label("体积先增后减，x = 2 在可行域内", 0, .25, size=31)),
                  FadeIn(self.put(r"V(2)=2\times8^2=128\ \mathrm{cm}^3", 0, -1.8, size=42, color=CURVE)))
        self.mark("volume_peak_ready")
        self.focus_begin("volume_peak")
        self.end_chapter()

    def boundary(self, cue):
        self.begin_chapter(cue)
        x = ValueTracker(2)
        faces = self.panels(2, math.pi/2)
        x_num = self.number(2, decimals=2, size=34, color=ACCENT).move_to([4.5, 1.5, 0])
        v_num = self.number(128, decimals=2, size=34, color=CURVE).move_to([4.5, .4, 0])
        self.beat(.12, FadeIn(faces), FadeIn(self.put(r"x\ (\mathrm{cm})", 2, 1.5, size=32)), FadeIn(x_num),
                  FadeIn(self.put(r"V\ (\mathrm{cm}^3)", 2, .4, size=32)), FadeIn(v_num))
        driver = Group()

        def update(_):
            size = x.get_value()
            faces.become(self.panels(size, math.pi/2))
            x_num.set_value(size)
            v_num.set_value(volume(size))
            self.sample("boundary_box", x_cm=size, volume_cm3=volume(size), dimensions_cm=dimensions(size))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.mark("boundary_flatten_start")
        self.focus_begin("boundary_flatten")
        self.beat(.32, x.animate.set_value(.08), rate_func=linear)
        self.focus_end("boundary_flatten")
        self.focus_begin("boundary_narrow")
        self.beat(.57, x.animate.set_value(5.92), rate_func=linear)
        self.focus_end("boundary_narrow")
        driver.clear_updaters()
        self.beat(.65, FadeIn(self.put(r"x\to0^+:\ V\to0", 3.5, -.8, size=35, width=5.5)),
                  FadeIn(self.put(r"x\to6^-:\ V\to0", 3.5, -1.65, size=35, width=5.5)),
                  FadeIn(self.label("退化边界不是可做的盒子", 3.5, -2.5, size=26, width=5.5)))
        self.mark("degenerate_limits_ready")
        self.focus_begin("degenerate_limits")
        self.end_chapter()

    def constraint(self, cue):
        self.begin_chapter(cue)
        x = ValueTracker(2)
        faces = self.panels(2, math.pi/2)
        x_num = self.number(2, decimals=2, size=35, color=ACCENT).move_to([4.5, .45, 0])
        v_num = self.number(128, decimals=2, size=35, color=CURVE).move_to([4.5, -.45, 0])
        old = self.label("原解 x = 2：高度不足", 3.5, -1.5, size=28, color=RATE, width=5.5)
        self.beat(.13, FadeIn(faces), FadeIn(self.label("新增要求：盒高至少 3 cm", 3.5, 2.15, size=30, width=5.6)),
                  FadeIn(self.put(r"3\leq x<6\quad(\mathrm{cm})", 3.5, 1.3, size=37, color=ACCENT, width=5.6)),
                  FadeIn(self.put(r"x\ (\mathrm{cm})", 2, .45, size=30)), FadeIn(x_num),
                  FadeIn(self.put(r"V\ (\mathrm{cm}^3)", 2, -.45, size=30)), FadeIn(v_num), FadeIn(old))
        self.mark("height_constraint_ready")
        self.focus_begin("height_constraint")
        self.beat(.32)
        self.focus_end("height_constraint")
        self.beat(.35, FadeOut(old))
        driver = Group()

        def update(_):
            size = x.get_value()
            faces.become(self.panels(size, math.pi/2))
            x_num.set_value(size)
            v_num.set_value(volume(size))
            self.sample("constrained_box", x_cm=size, volume_cm3=volume(size), feasible=feasible(size, 3),
                        dimensions_cm=dimensions(size))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("constraint_enter")
        self.beat(.48, x.animate.set_value(3), rate_func=linear)
        self.focus_end("constraint_enter")
        self.mark("constraint_boundary_ready")
        self.focus_begin("constraint_decrease")
        self.beat(.61, x.animate.set_value(4.5), rate_func=linear)
        self.beat(.73, x.animate.set_value(3), rate_func=linear)
        self.focus_end("constraint_decrease")
        driver.clear_updaters()
        self.beat(.80, FadeIn(self.label("[3,6) 上递减，左边界 x = 3 最优", 3.5, -1.45, size=26, width=5.7)),
                  FadeIn(self.put(r"6\times6\times3=108\ \mathrm{cm}^3", 3.5, -2.4, size=34, color=CURVE, width=5.7)))
        self.mark("constrained_optimum_ready")
        self.focus_begin("constrained_optimum")
        self.end_chapter()

    def closing(self, cue):
        self.begin_chapter(cue)
        self.beat(.13, FadeIn(self.panels(2, math.pi/2)),
                  FadeIn(self.put(r"x=2\ \mathrm{cm},\quad V=128\ \mathrm{cm}^3", 3.5, 2, size=34, color=CURVE, width=5.7)),
                  FadeIn(self.put(r"8\times8\times2\ \mathrm{cm}", 3.5, 1.1, size=35, width=5.7)),
                  FadeIn(self.label("尺寸 → 同一变量 → 目标与可行域", 3.5, -.1, size=27, width=5.7)),
                  FadeIn(self.label("变化率 → 单调性 → 全范围比较", 3.5, -1, size=27, width=5.7)))
        self.mark("chapter_chain_ready")
        self.focus_begin("chapter_chain")
        self.beat(.70)
        self.focus_end("chapter_chain")
        self.beat(.78, FadeIn(self.label("约束改变，沿同一模型重新判断", 3.5, -2.25, size=28, color=ACCENT, width=5.7)))
        self.mark("feasibility_transfer_ready")
        self.focus_begin("feasibility_transfer")
        self.end_chapter()

    def construct(self):
        if tuple(c["id"] for c in self.cues) != CUE_IDS:
            raise ValueError("Chapter 08 cue order differs from authored design")
        self.motion_samples = []
        for cue in self.cues:
            self.until(cue["start"])
            getattr(self, cue["id"])(cue)
