"""Fresh eigenvector lesson: one mathematical map drives all native geometry."""

import json

import numpy as np
from manimlib import (
    Arrow, Dot, FadeIn, FadeOut, Group, Line, ShowCreation,
    ValueTracker, VGroup, linear,
)

from manimind.components.formula_motion import SemanticFormula, matching_transform
from manimind.experiments.understanding_support import UnderstandingScene


INK = "#EEF1F4"
PLUS = "#58D5B0"
MINUS = "#F3D36A"
GENERAL = "#FF8F98"
MUTED = "#899399"
GRID = "#46575C"
CUE_DURATIONS = (26, 22, 26, 24, 26, 40, 26, 20)
A = ((2, 1), (1, 2))
ROTATION = ((0, -1), (1, 0))
GRID_SEGMENTS = tuple(
    segment for k in np.linspace(-1.1, 1.1, 9)
    for segment in (((k, -1.1), (k, 1.1)), ((-1.1, k), (1.1, k))))
PROBES = ((1, 0), (0, 1), (.8, .8), (.95, -.95))
ALGEBRA = {
    "vector": (r"A\binom{x}{y}=\lambda\binom{x}{y}",
               {"x": ("x", 0), "y": ("y", 0), "lambda": r"\lambda"}),
    "components": (r"\begin{aligned}2x+y&=\lambda x\\x+2y&=\lambda y\end{aligned}",
                   {"x": ("x", 0), "y": ("y", 0), "lambda": (r"\lambda", 0)}),
    "subtract": (r"x-y=\lambda(x-y)",
                 {"x": ("x", 0), "y": ("y", 0), "lambda": r"\lambda"}),
    "factor": (r"(\lambda-1)(x-y)=0",
               {"x": "x", "y": "y", "lambda": r"\lambda"}),
    "equal_substitute": (r"2x+x=\lambda x",
                         {"x": ("x", 0), "lambda": r"\lambda"}),
    "equal_combine": (r"3x=\lambda x",
                      {"x": ("x", 0), "lambda": r"\lambda"}),
    "equal_value": (r"\lambda=3", {"lambda": r"\lambda"}),
    "other_substitute": (r"2x+y=x", {"x": ("x", 0), "y": "y"}),
    "other_reduce": (r"x+y=0", {"x": "x", "y": "y"}),
    "other_direction": (r"y=-x", {"x": "x", "y": "y"}),
}
MATCH_IDS = {"factor": ("x", "y"), "other_direction": ("y",)}


def apply_matrix(matrix, vector):
    x, y = vector
    return (matrix[0][0] * x + matrix[0][1] * y,
            matrix[1][0] * x + matrix[1][1] * y)


def transform(vector, t=1):
    """Exactly ((1-t)I+tA)v, not a scalar interpolation of arrow length."""
    image = apply_matrix(A, vector)
    return tuple((1 - t) * value + t * mapped for value, mapped in zip(vector, image))


def decompose(vector):
    x, y = vector
    return ((x + y) / 2, (x - y) / 2)


def recombine(c1, c2, t=0):
    first = transform((c1, c1), t)
    second = transform((c2, -c2), t)
    return tuple(a + b for a, b in zip(first, second))


def cross(left, right):
    return left[0] * right[1] - left[1] * right[0]


def is_eigenvector(vector, matrix=A):
    if vector[0] == 0 and vector[1] == 0:
        return False
    return bool(np.isclose(cross(vector, apply_matrix(matrix, vector)), 0, atol=1e-10, rtol=0))


def rotated(vector, angle):
    x, y = vector
    return (np.cos(angle) * x - np.sin(angle) * y,
            np.sin(angle) * x + np.cos(angle) * y)


class EigenDirectionsLesson(UnderstandingScene):
    def put(self, latex, x, y, size=42, color=INK, width=7.0):
        result = self.formula(latex, size=size, color=color)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def label(self, text, x, y, size=32, color=INK, width=12):
        result = self.cn(text, size=size, color=color)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def title(self, text):
        self.play(FadeIn(self.label(text, 0, 3.35, size=39)), run_time=1)

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

    def sample(self, kind, **values):
        self.motion_samples.append({"kind": kind, "time": float(self.get_time()), **values})

    @staticmethod
    def point(vector):
        x, y = vector
        return np.array([-3.5 + .70 * x, -.25 + .70 * y, 0.])

    def axes(self):
        p = self.point
        axes = VGroup(Line(p((-3.6, 0)), p((3.6, 0))),
                      Line(p((0, -3.6)), p((0, 3.6)))).set_stroke(MUTED, 2)
        labels = Group(self.put("x", -1.0, -.55, size=28),
                       self.put("y", -3.8, 2.4, size=28),
                       self.put("0", -3.7, -.5, size=24))
        ticks = VGroup(*(Line(p((k, -.06)), p((k, .06))) for k in (-2, -1, 1, 2)))
        ticks.set_stroke(MUTED, 2)
        labels.add(self.put("1", *p((1, -.32))[:2], size=24))
        return Group(axes, ticks, labels)

    def arrow(self, vector, color, start=(0, 0)):
        return Arrow(self.point(start), self.point(vector), buff=0,
                     fill_color=color, thickness=2.7, tip_width_ratio=3.8)

    def plane(self):
        grid = VGroup(*(Line(self.point(a), self.point(b), stroke_color=GRID, stroke_width=1.4)
                        for a, b in GRID_SEGMENTS))
        arrows = Group(*(self.arrow(vector, color)
                         for vector, color in zip(PROBES, (GENERAL, INK, PLUS, MINUS))))
        return grid, arrows

    def plane_driver(self, tracker, grid, arrows, stage):
        driver = Group()
        fixed_axes = self.axes()

        def update(_):
            t = tracker.get_value()
            for line, (a, b) in zip(grid, GRID_SEGMENTS):
                line.put_start_and_end_on(self.point(transform(a, t)), self.point(transform(b, t)))
            for arrow, vector in zip(arrows, PROBES):
                arrow.put_start_and_end_on(self.point((0, 0)), self.point(transform(vector, t)))
            self.sample("plane", stage=stage, t=t,
                        endpoints=[arrow.get_end().tolist() for arrow in arrows],
                        grid=[[line.get_start().tolist(), line.get_end().tolist()] for line in grid],
                        axes=[[line.get_start().tolist(), line.get_end().tolist()] for line in fixed_axes[0]])

        driver.add_updater(update)
        return fixed_axes, driver

    def semantic(self, stage, y):
        latex, tokens = ALGEBRA[stage]
        result = SemanticFormula(latex, tokens=tokens, font_size=54).set_color(INK)
        if result.get_width() > 11.8:
            result.set_width(11.8)
        return result.move_to([0, y, 0])

    def morph(self, source, stage, y, duration=3):
        target = self.semantic(stage, y)
        source_center = source.get_center().tolist()
        target_center = target.get_center().tolist()
        begin = float(self.get_time())
        driver = Group()

        def update(_):
            self.sample("symbol", stage=stage,
                        centers={key: source.tag(key).get_center().tolist()
                                 for key in source.semantic_ids})

        driver.add_updater(update)
        self.add(driver)
        # Separate vertical lanes leave syntax room during the native replacement.
        pairs = [(key, key) for key in MATCH_IDS.get(stage, target.semantic_ids)
                 if key in source.semantic_ids]
        self.play(matching_transform(source, target, run_time=duration,
                                     pairs=pairs, path_arc=0, unmatched_in_place=True))
        self.remove(driver)
        self.symbol_transitions.append({"stage": stage, "start": begin,
                                        "end": float(self.get_time()),
                                        "source": source.get_tex(), "target": target.get_tex(),
                                        "source_center": source_center, "target_center": target_center})
        return target

    def opening(self):
        self.title("特征向量：矩阵变换中的不变方向")
        grid, arrows = self.plane()
        tracker = ValueTracker(0)
        axes, driver = self.plane_driver(tracker, grid, arrows, "opening")
        matrix = self.put(r"A=\begin{pmatrix}2&1\\1&2\end{pmatrix}", 2.8, 2.1, size=46)
        mapping = self.put(r"(x,y)\longmapsto(2x+y,\ x+2y)", 2.8, .9, size=37)
        e1 = self.put(r"(1,0)\longmapsto(2,1)", 2.8, -.2, size=38, color=GENERAL)
        interp = self.put(r"A_t=(1-t)I+tA,\quad 0\le t\le1", 2.8, -1.4, size=34)
        self.play(FadeIn(Group(grid, axes, arrows, matrix, mapping, e1, interp)), run_time=2)
        self.read("matrix_map", 5, "map_ready")
        self.add(driver)
        self.focus_begin("whole_plane")
        self.play(tracker.animate.set_value(1), run_time=8, rate_func=linear)
        self.mark("plane_transformed")
        self.wait(4)
        self.focus_end("whole_plane")
        self.remove(driver)
        result = self.label("红色向量离开了原来的直线", 2.8, -2.5, size=30)
        self.play(FadeIn(result), run_time=1)
        self.read("general_turn", 5, "turn_ready")

    def directions(self):
        self.clear_stage()
        self.title("哪些向量仍在原来的直线上？")
        grid, arrows = self.plane()
        tracker = ValueTracker(0)
        axes, driver = self.plane_driver(tracker, grid, arrows, "directions")
        lines = VGroup(Line(self.point((-3.3, -3.3)), self.point((3.3, 3.3)), color=PLUS),
                       Line(self.point((-3.3, 3.3)), self.point((3.3, -3.3)), color=MINUS))
        definition = self.put(r"Av=\lambda v,\qquad v\ne0", 2.8, 1.9, size=46)
        words = self.label("变换后仍在原向量所在直线上", 2.8, .9, size=29, width=7)
        candidates = self.put(r"y=x\qquad y=-x", 2.8, -.15, size=43)
        zero = self.label("零向量没有方向，因此排除", 2.8, -1.4, size=29)
        self.play(FadeIn(Group(grid, axes, lines, arrows, definition, words, candidates, zero)), run_time=2)
        self.read("definition", 4, "definition_ready")
        self.add(driver)
        self.focus_begin("candidate_lines")
        self.play(tracker.animate.set_value(1), run_time=7, rate_func=linear)
        self.mark("candidates_ready")
        self.wait(7)
        self.focus_end("candidate_lines")
        self.remove(driver)

    def equations(self):
        self.clear_stage()
        self.title("从定义出发，找齐这些方向")
        condition = self.put(r"v=(x,y)\ne(0,0)", 0, 2.25, size=38)
        source = self.semantic("vector", .85)
        self.play(FadeIn(condition), FadeIn(source), run_time=1)
        self.read("vector_equation", 2, "vector_ready")
        current = self.morph(source, "components", -.7)
        self.read("two_components", 5, "components_ready")
        operation = self.label("上式减下式", 0, 2.25, size=32)
        self.play(FadeOut(condition), run_time=.5)
        self.play(FadeIn(operation), run_time=.5)
        current = self.morph(current, "subtract", 1.0)
        self.read("subtract", 3, "subtract_ready")
        current = self.morph(current, "factor", -1.5)
        self.read("factor", 3, "factor_ready")

    def equal_case(self):
        self.clear_stage()
        self.title("第一种情况：两个分量相等")
        rule = self.put(r"(\lambda-1)(x-y)=0", 0, 2.2, size=39)
        condition = self.put(r"x=y,\quad v\ne0\ \Longrightarrow\ x\ne0", 0, 1.25, size=40)
        self.play(FadeIn(rule), FadeIn(condition), run_time=1)
        self.read("equal_nonzero", 3, "equal_condition_ready")
        source = self.semantic("equal_substitute", .1)
        self.play(FadeIn(source), run_time=1)
        self.read("equal_substitute", 3, "equal_substitute_ready")
        source = self.morph(source, "equal_combine", -1.25, duration=2)
        self.read("equal_combine", 3, "equal_combine_ready")
        source = self.morph(source, "equal_value", .05, duration=2)
        self.read("equal_value", 3, "equal_value_ready")
        direction = self.put(r"v=x(1,1),\quad x\ne0", 0, -1.55, size=45, color=PLUS)
        self.play(FadeIn(direction), run_time=1)
        self.read("plus_direction", 3, "plus_direction_ready")

    def other_case(self):
        self.clear_stage()
        self.title("第二种情况：两个分量不相等")
        condition = self.put(r"(\lambda-1)(x-y)=0,\quad x\ne y\ \Longrightarrow\ \lambda=1",
                             0, 2.15, size=39, width=12)
        self.play(FadeIn(condition), run_time=1)
        self.read("other_value", 4, "other_value_ready")
        source = self.semantic("other_substitute", .8)
        self.play(FadeIn(source), run_time=1)
        self.read("other_substitute", 3, "other_substitute_ready")
        source = self.morph(source, "other_reduce", -.6)
        self.read("other_reduce", 3, "other_reduce_ready")
        source = self.morph(source, "other_direction", .6)
        self.read("other_direction", 3, "other_direction_ready")
        result = self.put(r"v=x(1,-1),\quad x\ne0", 0, -.9, size=44, color=MINUS)
        exhaustive = self.label("相等或不相等，已经覆盖所有非零向量", 0, -2.1, size=31)
        self.play(FadeIn(result), FadeIn(exhaustive), run_time=1)
        self.read("all_directions", 2, "all_directions_ready")

    def decomposition(self):
        self.clear_stage()
        self.title("沿这两个方向分解，再分别变换")
        axes = self.axes()
        lines = VGroup(Line(self.point((-3.4, -3.4)), self.point((3.4, 3.4)), color=PLUS),
                       Line(self.point((-3.4, 3.4)), self.point((3.4, -3.4)), color=MINUS))
        u = (1.5, .5)
        c1, c2 = decompose(u)
        first = self.arrow((c1, c1), PLUS)
        second = self.arrow(u, MINUS, start=(c1, c1))
        total = self.arrow(u, GENERAL)
        direct = Dot(self.point(u), radius=.07, color=INK)
        formula = self.put(r"u=c_1(1,1)+c_2(1,-1)", 2.8, 2.1, size=40)
        coefficients = self.put(r"c_1=\frac{x+y}{2},\quad c_2=\frac{x-y}{2}", 2.8, 1.05, size=38)
        example = self.put(r"u=(1.5,0.5)=(1,1)+0.5(1,-1)", 2.8, -.05, size=35)
        self.play(FadeIn(Group(axes, lines, total, direct, formula, coefficients, example)), run_time=2)
        self.play(ShowCreation(first), run_time=2)
        self.play(ShowCreation(second), run_time=2)
        self.read("decompose", 5, "decomposition_ready")
        image = self.put(r"A_tu=(1+2t)c_1(1,1)+c_2(1,-1)", 2.8, -1.15, size=34)
        self.play(FadeIn(image), run_time=1)
        tracker = ValueTracker(0)
        driver = Group()

        def update(_):
            t = tracker.get_value()
            a = transform((c1, c1), t)
            combined = recombine(c1, c2, t)
            first.put_start_and_end_on(self.point((0, 0)), self.point(a))
            second.put_start_and_end_on(self.point(a), self.point(combined))
            total.put_start_and_end_on(self.point((0, 0)), self.point(transform(u, t)))
            direct.move_to(self.point(transform(u, t)))
            self.sample("decomposition", t=t, first=first.get_end().tolist(),
                        second_start=second.get_start().tolist(), second_end=second.get_end().tolist(),
                        total=total.get_end().tolist(), direct=direct.get_center().tolist())

        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("independent_scaling")
        self.play(tracker.animate.set_value(1), run_time=9, rate_func=linear)
        self.mark("components_transformed")
        self.wait(3)
        self.focus_end("independent_scaling")
        check = self.put(r"Au=(3.5,2.5)=(3,3)+(0.5,-0.5)", 2.8, -2.3, size=35)
        self.play(FadeIn(check), run_time=1)
        self.read("recombine", 5, "recombined_ready")
        self.remove(driver)
        self.play(FadeOut(example), run_time=1)
        direct_check = self.put(r"\begin{pmatrix}2&1\\1&2\end{pmatrix}\binom{1.5}{0.5}=\binom{3.5}{2.5}",
                                2.8, -.05, size=38)
        self.play(FadeIn(direct_check), run_time=1)
        self.read("linearity_check", 6, "direct_check_ready")

    def rotation(self):
        self.clear_stage()
        self.title("实数范围内，未必存在特征方向")
        axes = self.axes()
        original = (2, .7)
        reference = Line(self.point(tuple(-1.6 * x for x in original)),
                         self.point(tuple(1.6 * x for x in original)), color=MUTED)
        arrow = self.arrow(original, GENERAL)
        ghost = self.arrow(original, MUTED).set_opacity(.4)
        angle = ValueTracker(0)
        matrix = self.put(r"R=\begin{pmatrix}0&-1\\1&0\end{pmatrix}", 2.8, 2, size=45)
        mapping = self.put(r"R(x,y)=(-y,x)", 2.8, .85, size=43)
        rule = self.put(r"v\ne0,\quad v\in\mathbb{R}^2", 2.8, -.25, size=38)
        self.play(FadeIn(Group(axes, reference, ghost, arrow, matrix, mapping, rule)), run_time=2)
        self.read("rotation_input", 3, "rotation_input_ready")
        driver = Group()

        def update(_):
            theta = angle.get_value()
            endpoint = rotated(original, theta)
            arrow.put_start_and_end_on(self.point((0, 0)), self.point(endpoint))
            self.sample("rotation", angle=theta, original=list(original), endpoint=arrow.get_end().tolist())

        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("quarter_turn")
        self.play(angle.animate.set_value(np.pi / 2), run_time=5, rate_func=linear)
        self.wait(2)
        self.focus_end("quarter_turn")
        perpendicular = self.put(r"v\cdot Rv=-xy+xy=0", 2.8, -1.25, size=39)
        conclusion = self.label("非零向量转过直角，不可能仍在原直线上", 0, -2.6, size=31)
        self.play(FadeIn(perpendicular), FadeIn(conclusion), run_time=1)
        self.read("no_real_direction", 10, "no_real_direction_ready")
        self.remove(driver)
        self.wait(1)

    def closing(self):
        self.clear_stage()
        self.title("特征向量，找的是变换保留的直线")
        grid, arrows = self.plane()
        tracker = ValueTracker(0)
        axes, driver = self.plane_driver(tracker, grid, arrows, "closing")
        formula = self.put(r"Av=\lambda v,\qquad v\ne0", 2.8, 2.05, size=45)
        plus = self.put(r"A(1,1)=3(1,1)", 2.8, .95, size=43, color=PLUS)
        minus = self.put(r"A(1,-1)=(1,-1)", 2.8, -.15, size=43, color=MINUS)
        result = self.label("特征值给出这条直线上的倍数", 2.8, -1.4, size=30)
        self.play(FadeIn(Group(grid, axes, arrows, formula, plus, minus, result)), run_time=2)
        self.add(driver)
        self.focus_begin("summary")
        self.play(tracker.animate.set_value(1), run_time=6, rate_func=linear)
        self.mark("summary_ready")
        self.wait(4)
        self.play(tracker.animate.set_value(0), run_time=3, rate_func=linear)
        self.play(tracker.animate.set_value(1), run_time=3, rate_func=linear)
        self.focus_end("summary")
        self.remove(driver)

    def construct(self):
        self.motion_samples, self.symbol_transitions, self.chapter_times = [], [], []
        methods = (self.opening, self.directions, self.equations, self.equal_case,
                   self.other_case, self.decomposition, self.rotation, self.closing)
        for cue, duration, method in zip(self.cues, CUE_DURATIONS, methods, strict=True):
            if cue["duration"] != duration:
                raise ValueError("Scene and plan cue durations differ")
            self.until(cue["start"])
            begin = float(self.get_time())
            method()
            self.until(cue["start"] + duration)
            self.chapter_times.append({"id": cue["id"], "start": begin, "end": float(self.get_time())})

    def tear_down(self):
        report = {"duration": float(self.get_time()), "samples": self.motion_samples,
                  "symbol_transitions": self.symbol_transitions, "chapters": self.chapter_times,
                  "writer": "EigenDirectionsLesson actual native updaters",
                  "consumers": ["geometry tests", "independent reviewer"],
                  "lifecycle": "This exact scene execution",
                  "invalidation": "Source, plan, typography, native runtime or timing change",
                  "limitation": "Geometry and clock observations; no pixel or comprehension approval"}
        with (self.out / "eigen-motion.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
        super().tear_down()
