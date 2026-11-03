"""Bounded supervised visual revision. Render/review/audio remain the lead's work.

All model times are physical seconds, independent of animation run_time.
Local geometry has scene lifetime; only the shared runtime writes evidence.
"""

import math

import numpy as np
from manimlib import *
from manimind.components.formula_motion import SemanticFormula
from manimind.experiments.understanding_support import UnderstandingScene


WHITE = "#EEF3F2"
MUTED = "#9DAAA9"
BLUE = "#69C7FF"
CORAL = "#FF9B87"
VERTICAL = "#F3D978"
GREEN = "#9CE0BD"


def flight_state(height, horizontal_speed, physical_time, gravity=10.0):
    """Downward-positive ideal motion, clamped at the first ground contact."""
    if height <= 0 or gravity <= 0 or horizontal_speed < 0 or physical_time < 0:
        raise ValueError("Expected positive height/g and nonnegative speed/time")
    landing = math.sqrt(2 * height / gravity)
    time = min(physical_time, landing)
    return {"time": time, "x": horizontal_speed * time,
            "drop": gravity * time * time / 2, "vy": gravity * time,
            "landing_time": landing, "range": horizontal_speed * landing}


def slice_positions(physical_time, spread=1.0):
    """Presentation decomposition at fixed model time, not a flight update."""
    origin, scale = np.array([-4.7, 1.65, 0.]), .55
    common = origin + np.array([0., -scale * 5 * physical_time ** 2, 0.])
    return common, [common + np.array([scale * speed * physical_time * spread, 0., 0.])
                    for speed in (4, 8)]


def speed_arrow_ends(physical_time):
    start = np.array([1., 1.35, 0.])
    return start, start + np.array([0., -.095 * 10 * physical_time, 0.])


def time_transfer_point(start, end, alpha):
    """An uncluttered lower corridor carries one T without changing its shape."""
    corners = [np.array(start), np.array([start[0], -.85, 0.]),
               np.array([end[0], -.85, 0.]), np.array(end)]
    stage = min(int(alpha * 3), 2)
    amount = min(1., alpha * 3 - stage)
    return (1 - amount) * corners[stage] + amount * corners[stage + 1]


class UnderstandingLesson(UnderstandingScene):
    def _cn(self, text, x, y, size=32, color=WHITE):
        return self.cn(text, size=size, color=color).move_to([x, y, 0])

    def _eq(self, latex, x, y, size=46, color=WHITE):
        return self.formula(latex, size=size, color=color).move_to([x, y, 0])

    def _show(self, *objects, seconds=.6):
        self.play(*(FadeIn(obj) for obj in objects), run_time=seconds)

    def _enter(self, cue_id, heading):
        cue = next(cue for cue in self.cues if cue["id"] == cue_id)
        self.until(cue["start"])
        old = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        if old:
            self.play(*(FadeOut(obj) for obj in old), run_time=.4)
        self._show(self._cn(heading, 0, 3.15, 40), seconds=.6)
        return cue["start"]

    def _line(self, a, b, color=MUTED, width=2):
        return Line(np.array(a, dtype=float), np.array(b, dtype=float),
                    stroke_color=color, stroke_width=width)

    def _arrow(self, a, b, color):
        return Arrow(np.array(a, dtype=float), np.array(b, dtype=float),
                     buff=0, fill_color=color, stroke_color=color, thickness=3)

    def _path(self, height, speed, origin, scale, color):
        landing = flight_state(height, speed, 0)["landing_time"]
        return ParametricCurve(
            lambda t: np.array([origin[0] + scale * speed * t,
                                origin[1] - scale * 5 * t * t, 0]),
            t_range=(0, landing, landing / 80), stroke_color=color,
            stroke_width=3)

    def construct(self):
        self.camera.background_rgba = color_to_rgba("#101416")
        self._question()
        self._conditions()
        self._same_height()
        self._directions()
        self._recombine()
        self._landing_rule()
        self._height_steps()
        self._height_compare()
        self._prediction()
        self._resolve()

    def _question(self):
        s = self._enter("question", "抛得更快，会更晚落地吗？")
        origin = np.array([-4.6, 1.0, 0])
        ground = self._line([-5.3, -1.65, 0], [5.2, -1.65, 0])
        ball = Dot(origin, radius=.13, fill_color=WHITE)
        slow = self._arrow(origin + UP * .3, origin + [2, .3, 0], BLUE)
        fast = self._arrow(origin + UP * 1.05, origin + [4, 1.05, 0], CORAL)
        labels = Group(self._eq(r"v_x=4\ \mathrm{m/s}", -.4, 1.3, 36, BLUE),
                       self._eq(r"v_x=8\ \mathrm{m/s}", 1.6, 2.05, 36, CORAL),
                       self._cn("同一个高度，同一刻出发", 0, -2.5, 34))
        self._show(ground, ball, slow, fast, labels)
        self.mark("question_ready")
        self.focus_begin("question_hold")
        self.until(s + 6.8)
        self.focus_end("question_hold")
        self.until(s + 7)

    def _conditions(self):
        s = self._enter("conditions", "先约定一个简单的世界")
        labels = Group(self._cn("无空气阻力 · 小球视为质点", 0, 1.7, 36),
                       self._cn("重力大小和方向保持不变", 0, .65, 36),
                       self._eq(r"g=10\ \mathrm{m/s^2}\qquad v_{y0}=0", 0, -.55, 46, VERTICAL),
                       self._cn("水平抛出，不额外向上或向下推", 0, -1.65, 32),
                       self._cn("接下来是这个模型的数值演示", 0, -2.65, 28, MUTED))
        self._show(labels)
        self.mark("model_conditions_ready")
        self.focus_begin("model_conditions")
        self.until(s + 6.8)
        self.focus_end("model_conditions")
        self.until(s + 7)

    def _same_height(self):
        s = self._enter("same_height", "横着走得不同，竖直过程呢？")
        origin, scale = np.array([-4.8, 1.7, 0]), .55
        ground = self._line([-5.2, -1.05, 0], [.2, -1.05, 0])
        height = Group(self._line([-5.5, 1.7, 0], [-5.5, -1.05, 0], VERTICAL),
                       self._eq(r"h=5\ \mathrm m", -5.45, -1.7, 34, VERTICAL))
        speed = Group(self._eq(r"4\ \mathrm{m/s}", -3.7, 2.35, 34, BLUE),
                      self._eq(r"8\ \mathrm{m/s}", -1.2, 2.35, 34, CORAL))
        clock = self.number(0, size=40, decimals=2).move_to([3.2, 1.4, 0])
        clock_unit = self._eq(r"t\ (\mathrm{s})", 3.2, 2.15, 34)
        balls = Group(Dot(origin, radius=.12, fill_color=BLUE),
                      Circle(radius=.19, stroke_color=CORAL, stroke_width=3).move_to(origin))
        paths = [self._path(5, vx, origin, scale, color) for vx, color in ((4, BLUE), (8, CORAL))]
        self._show(ground, height, speed, clock, clock_unit, balls)
        self.mark("same_height_launch_ready")
        self.focus_begin("same_height_motion")
        self.until(s + 2.5)

        def update(group, alpha):
            for ball, vx in zip(group, (4, 8)):
                state = flight_state(5, vx, alpha)
                ball.move_to(origin + [scale * state["x"], -scale * state["drop"], 0])
            clock.set_value(alpha)

        self.play(UpdateFromAlphaFunc(balls, update),
                  *(ShowCreation(path) for path in paths), run_time=4, rate_func=linear)
        self.mark("same_height_landed")
        self.focus_end("same_height_motion")
        result = Group(self._eq(r"T=1\ \mathrm{s}", 3.2, .3, 54, GREEN),
                       self._eq(r"R_4=4\ \mathrm m", 3.2, -.8, 44, BLUE),
                       self._eq(r"R_8=8\ \mathrm m", 3.2, -1.8, 44, CORAL),
                       self._cn("同时落地，射程不同", -2.5, -2.65, 35))
        self._show(result)
        self.mark("same_height_result_ready")
        self.focus_begin("same_height_result")
        self.until(s + 17.8)
        self.focus_end("same_height_result")
        self.until(s + 18)

    def _directions(self):
        s = self._enter("directions", "不是分走速度，而是在描述两个方向")
        # Horizontal lengths share one scale. Vertical is one common process.
        horizontal = Group(
            self._arrow([-5, 1.8, 0], [-3, 1.8, 0], BLUE),
            self._arrow([-5, .8, 0], [-1, .8, 0], CORAL),
            self._eq(r"v_x=4", -2, 1.8, 38, BLUE),
            self._eq(r"v_x=8", 0, .8, 38, CORAL),
            self._cn("水平：保持匀速", 3.8, 1.3, 33))
        self._show(horizontal)
        self.mark("horizontal_components_ready")
        self.focus_begin("horizontal_component")
        self.until(s + 5.5)
        self.focus_end("horizontal_component")
        vertical = Group(self._arrow([-4.7, -.25, 0], [-4.7, -2.15, 0], VERTICAL),
                         self._eq(r"v_{y0}=0", -2.5, -.45, 38, VERTICAL),
                         self._eq(r"a_y=g\ \downarrow", -2.5, -1.5, 38, VERTICAL),
                         self._cn("竖直：从零开始，向下加速", 3.1, -.8, 30),
                         self._cn("两球的竖直初速度、加速度都相同", .5, -2.65, 31, VERTICAL))
        self._show(vertical)
        self.mark("shared_vertical_components_ready")
        self.focus_begin("vertical_component")
        self.until(s + 17.8)
        self.focus_end("vertical_component")
        self.until(s + 18)

    def _recombine(self):
        s = self._enter("recombine", "给同一段下落，接上不同的水平位移")
        origin, _ = slice_positions(0)
        bottom, _ = slice_positions(1)
        spine = self._line(origin, bottom, VERTICAL, 3)
        projection = Dot(origin, radius=.065, fill_color=VERTICAL)
        interpretation = Group(self._cn("同一时刻的位置分解", 0, 2.4, 31, VERTICAL),
                               self._cn("横向展开是位置分解，不是实际运动", 0, -2.75, 29, MUTED),
                               self._eq(r"v_x=4", 3.4, .4, 36, BLUE),
                               self._eq(r"v_x=8", 3.4, -.35, 36, CORAL),
                               self._eq(r"x=v_x t", 3.4, -1.45, 48))
        self._show(spine, projection, interpretation)
        previous, previous_time, prior_t = None, None, 0.
        samples = ((.25, "slice_025_ready"), (.5, "slice_050_ready"),
                   (.75, "slice_075_ready"), (1., "slice_100_ready"))
        for index, (physical_t, anchor) in enumerate(samples):
            if previous is not None:
                self.play(UpdateFromAlphaFunc(previous, lambda obj, alpha: obj.set_opacity(1 - .62 * alpha)),
                          FadeOut(previous_time), run_time=.2, rate_func=linear)

            def descend(obj, alpha, begin=prior_t, end=physical_t):
                common, _ = slice_positions(begin + (end - begin) * alpha)
                obj.move_to(common)

            self.play(UpdateFromAlphaFunc(projection, descend), run_time=.5, rate_func=linear)
            common, _ = slice_positions(physical_t)
            tick = self._line(common + [-.15, 0, 0], common + [.15, 0, 0], VERTICAL)
            label = self._eq(f"{physical_t:g}\\,\\mathrm s", -5.65, common[1], 25, VERTICAL)
            positions = Group(Dot(common, radius=.09, fill_color=BLUE),
                              Circle(radius=.15, stroke_color=CORAL, stroke_width=3).move_to(common))
            rail = self._line(common, common + [.001, 0, 0], MUTED, 1)
            current_time = self._eq(f"t={physical_t:g}\\,\\mathrm s", 3.4, 1.5, 42, VERTICAL)
            self._show(tick, label, rail, positions, current_time, seconds=.3)

            def expand(group, alpha, time=physical_t, guide=rail):
                start, targets = slice_positions(time, alpha)
                for dot, point in zip(group, targets):
                    dot.move_to(point)
                end = targets[1] if alpha > 0 else start + np.array([.001, 0., 0.])
                guide.put_start_and_end_on(np.array(start), np.array(end))

            self.play(UpdateFromAlphaFunc(positions, expand), run_time=1.2, rate_func=linear)
            self.mark(anchor)
            if index == 0:
                self.focus_begin("shared_time_slices")
            self.until(s + 4.8 + 3.4 * index)
            previous = Group(tick, label, rail, positions)
            previous_time, prior_t = current_time, physical_t
        self.mark("shared_time_slices_ready")
        self.until(s + 19.8)
        self.focus_end("shared_time_slices")
        self.until(s + 20)

    def _landing_rule(self):
        s = self._enter("landing_rule", "落地，是竖直方向先给出的条件")
        vertical = SemanticFormula(r"h=\frac{1}{2}gT^2", tokens={"time": "T"},
                                   colors={"time": GREEN}, font_size=58).move_to([-2.8, .8, 0])
        condition = self._eq(r"d(T)=h", -2.8, 2., 40, VERTICAL)
        prefix = self._eq(r"R=v_x", 0, 0, 58)
        target_time = vertical.tag("time").copy().set_color(MUTED)
        horizontal = Group(prefix, target_time).arrange(RIGHT, buff=.12).move_to([3.2, .8, 0])
        caption = self._cn("先由高度确定时间，再算横向走多远", 0, -2.6, 34)
        self._show(vertical, condition, horizontal, caption)
        self.mark("landing_condition_ready")
        self.focus_begin("landing_condition")
        self.until(s + 4.5)
        carrier = vertical.tag("time").copy()
        start, end = carrier.get_center().copy(), target_time.get_center().copy()
        self.add(carrier)
        self.play(UpdateFromAlphaFunc(carrier, lambda obj, alpha: obj.move_to(time_transfer_point(start, end, alpha))),
                  run_time=1.8, rate_func=linear)
        self.remove(carrier)
        target_time.set_color(GREEN)
        self.mark("shared_landing_time_linked")
        self.until(s + 12.8)
        self.focus_end("landing_condition")
        self.until(s + 13)

    def _height_steps(self):
        s = self._enter("height_steps", "多落一秒，不是再落同样远")
        x, top, scale = -4., 1.7, .19
        ruler = self._line([x, top, 0], [x, top - 20 * scale, 0], VERTICAL, 3)
        zero = self._eq(r"0\ \mathrm m", -5.2, top, 34)
        five = self._eq(r"5\ \mathrm m", -5.2, top - 5 * scale, 34, VERTICAL)
        twenty = self._eq(r"20\ \mathrm m", -5.2, top - 20 * scale, 34, VERTICAL)
        dot = Dot([x, top, 0], radius=.13, fill_color=VERTICAL)
        clock = self.number(0, size=40, decimals=1).move_to([3.5, 2.3, 0])
        speed = self.number(0, size=42, decimals=1, color=VERTICAL).move_to([3.6, .8, 0])
        start, _ = speed_arrow_ends(0)
        velocity = self._arrow(start, start + np.array([0., -.001, 0.]), VERTICAL).set_opacity(0)
        readouts = Group(self._eq(r"t=", 2.4, 2.3, 38), self._eq(r"\mathrm s", 4.45, 2.3, 34),
                         self._cn("向下速度", 3.1, 1.6, 30, VERTICAL),
                         self._eq(r"v_y=", 2.3, .8, 38, VERTICAL),
                         self._eq(r"\mathrm{m/s}", 4.95, .8, 34, VERTICAL),
                         self._eq(r"v_y=10t", 3.2, -1.65, 42, VERTICAL))
        self._show(ruler, zero, five, twenty, dot, clock, speed, readouts, velocity)
        self.until(s + 2)

        def at_time(time):
            state = flight_state(20, 0, time)
            dot.move_to(np.array([x, top - scale * state["drop"], 0.]))
            clock.set_value(state["time"])
            speed.set_value(state["vy"])
            a, b = speed_arrow_ends(state["time"])
            if time > 0:
                velocity.set_points_by_ends(a, b)
                velocity.set_opacity(1)
            else:
                velocity.set_opacity(0)

        self.play(UpdateFromAlphaFunc(dot, lambda _, alpha: at_time(alpha)), run_time=3, rate_func=linear)
        first = Group(self._line([-3.55, top, 0], [-3.55, top - .95, 0], BLUE, 7),
                      self._cn("第1秒：5米", -1.5, 1.15, 33, BLUE))
        self._show(first)
        self.mark("first_second_ready")
        self.focus_begin("first_second")
        self.until(s + 11)
        self.focus_end("first_second")
        self.play(UpdateFromAlphaFunc(dot, lambda _, alpha: at_time(1 + alpha)), run_time=4, rate_func=linear)
        second = Group(self._line([-3.55, top - .95, 0], [-3.55, top - 3.8, 0], CORAL, 7),
                       self._cn("第2秒：再落15米", -1.3, -.7, 33, CORAL),
                       self._eq(r"0\to10\to20", 3.25, -.7, 35, VERTICAL),
                       self._eq(r"20=5+15", -1.8, -2.85, 46),
                       self._cn("向下越落越快", 3.2, -2.65, 30, VERTICAL))
        self._show(second)
        self.mark("second_second_ready")
        self.focus_begin("second_second")
        self.until(s + 25.8)
        self.focus_end("second_second")
        self.until(s + 26)

    def _height_compare(self):
        s = self._enter("height_compare", "高度四倍，时间只要两倍")
        # Equal vertical scales; the low start is one quarter of the high one.
        ground_y, scale = -1.5, .16
        pictures = Group()
        for x, h, color in ((-4.2, 5, BLUE), (-1.6, 20, CORAL)):
            y = ground_y + h * scale
            pictures.add(self._line([x - .6, ground_y, 0], [x + .6, ground_y, 0]),
                         self._line([x, ground_y, 0], [x, y, 0], color, 4),
                         Dot([x, y, 0], radius=.12, fill_color=color),
                         self._eq(f"{h}\\ \\mathrm m", x, -2.1, 38, color))
        relations = Group(self._eq(r"h:\ 5\longrightarrow20", 3, 1.8, 46, VERTICAL),
                          self._eq(r"T:\ 1\longrightarrow2\ \mathrm s", 3, .65, 46, GREEN),
                          self._eq(r"R:\ 4\longrightarrow8\ \mathrm m", 3, -.5, 46),
                          self._eq(r"v_x=4\ \mathrm{m/s} \text{不变}", 3, -1.65, 37),
                          self._cn("下落距离随时间的平方增长", 0, -2.95, 32))
        self._show(pictures, relations)
        self.mark("height_fourfold_ready")
        self.focus_begin("height_fourfold")
        self.until(s + 11.8)
        self.focus_end("height_fourfold")
        self.until(s + 12)

    def _prediction(self):
        s = self._enter("prediction", "换个高度，你会怎样预测？")
        question = Group(self._eq(r"h:\ 5\longrightarrow45\ \mathrm m", 0, 1.65, 55, VERTICAL),
                         self._eq(r"v_x=4\ \mathrm{m/s}\ \text{不变}", 0, .45, 43),
                         self._eq(r"T:\ 1\ \mathrm s\longrightarrow\ ?", -2.9, -1.2, 54, GREEN),
                         self._eq(r"R:\ 4\ \mathrm m\longrightarrow\ ?", 2.9, -1.2, 54, GREEN))
        self._show(question)
        self.mark("ninefold_question_ready")
        self.focus_begin("ninefold_question")
        self.until(s + 6.5)
        self.focus_end("ninefold_question")
        # Deliberate silent prediction space, with no answer or countdown.
        self.focus_begin("prediction_space")
        self.mark("prediction_pause_started")
        self.until(s + 12.8)
        self.focus_end("prediction_space")
        self.until(s + 13)

    def _resolve(self):
        s = self._enter("resolve", "九倍高度，对应三倍时间")
        check = Group(self._eq(r"5\times3^2=45\ \mathrm m", 0, 1.8, 62, VERTICAL),
                      self._eq(r"T=3\ \mathrm s", -3.1, .2, 68, GREEN),
                      self._eq(r"R=12\ \mathrm m", 3.1, .2, 68, GREEN),
                      self._cn("同高改横速：改射程，不改下落时间", 0, -1.45, 34),
                      self._cn("改高度：先看竖直过程，再算水平位移", 0, -2.45, 34))
        self._show(check)
        self.mark("ninefold_answer_ready")
        self.focus_begin("ninefold_check")
        self.until(s + 12.8)
        self.focus_end("ninefold_check")
        self.until(s + 13)
