"""Independent superposition production scene; inherited per-scene runtime only."""

import numpy as np
from manimlib import Arrow, DashedVMobject, Dot, FadeIn, FadeOut, Group, Line, ShowCreation, ValueTracker, VGroup

from wave_unit_shared import (
    WaveLessonBase, GUIDE, INK, MUTED, PARTICLE, SECOND, WAVE, model, polyline,
)


class WaveSuperpositionLesson(WaveLessonBase):
    durations = (23.5, 32, 29, 38.5, 30)

    @property
    def chapters(self):
        return (self.encounter, self.addition, self.through, self.cancellation, self.exit_task)

    def pulse_world(self, tracker, second_amplitude=1, rows=True):
        baselines = (1.85, .15, -1.65) if rows else (.05,)
        keys = ("y1_cm", "y2_cm", "y_cm") if rows else ("y_cm",)
        scales = (.46, .46, .6) if rows else (1.0,)
        colors = (WAVE, SECOND, INK) if rows else (INK,)
        points = [lambda x, y, b=b, s=s: self.point(x, y, b, s) for b, s in zip(baselines, scales)]
        xs = np.linspace(0, 10, 501)
        curves, axes, names = VGroup(), VGroup(), Group()
        labels = (r"y_1\,(\mathrm{cm})", r"y_2\,(\mathrm{cm})", r"y_1+y_2\,(\mathrm{cm})") if rows else (r"y\,(\mathrm{cm})",)
        for p, key, color, label, baseline in zip(points, keys, colors, labels, baselines):
            curves.add(polyline([p(x, model.pulse_state(x, tracker.get_value(), second_amplitude)[key]) for x in xs], color))
            axes.add(Line(p(0, 0), p(10, 0), color=GUIDE, stroke_width=2))
            names.add(self.put(label, -4.65, baseline + .75, size=28, color=color, width=3))
        bottom = points[-1]
        x_label = self.put(r"x\,(\mathrm m)", 0, 0, size=26, width=1.1)
        tick_y = -.9 if rows else -.28
        x_label.move_to(bottom(10, 0) + [.45 + x_label.get_width() / 2, tick_y, 0])
        names.add(x_label)
        for x in (0, 2, 4, 6, 8, 10):
            axes.add(Line(bottom(x, -.05), bottom(x, .05), color=MUTED, stroke_width=2))
            names.add(self.put(str(x), *(bottom(x, 0) + [0, tick_y, 0])[:2], size=23))
        if rows:
            names.add(self.label("分量", 4.95, 2.6, 25, WAVE), self.label("分量", 4.95, .9, 25, SECOND),
                      self.label("实际绳形", 4.7, -.9, 27))
        selected = VGroup(*(Dot(p(5, model.pulse_state(5, tracker.get_value(), second_amplitude)[key]),
                               fill_color=color, radius=.065) for p, key, color in zip(points, keys, colors)))
        group = Group(axes, curves, names, selected)
        self.play(FadeIn(group), run_time=1)

        def update(_):
            t = float(tracker.get_value())
            states = [model.pulse_state(float(x), t, second_amplitude) for x in xs]
            for curve, p, key, bead in zip(curves, points, keys, selected):
                curve.set_points_as_corners([p(x, state[key]) for x, state in zip(xs, states)])
                bead.move_to(p(5, model.pulse_state(5, t, second_amplitude)[key]))
            self.sample("pulses", physical_s=t, second_amplitude=second_amplitude,
                        probes=[model.pulse_state(x, t, second_amplitude) for x in (4.5, 5, 5.5)],
                        centers_m=model.pulse_centers(t), screens=[dot.get_center().tolist() for dot in selected])

        self.driver(update)
        self.add(self.clock(tracker, x=4.65, y=2.95))
        return points, selected

    def encounter(self):
        begin = float(self.get_time())
        self.title("两个脉冲相遇，会反弹吗？")
        t = ValueTracker(0)
        points, _ = self.pulse_world(t, rows=False)
        p = points[0]
        arrows = Group(
            Arrow(p(1.5, 1.7), p(2.8, 1.7), buff=0, fill_color=WAVE, thickness=2.5),
            Arrow(p(8.5, 1.7), p(7.2, 1.7), buff=0, fill_color=SECOND, thickness=2.5))
        self.play(FadeIn(arrows), FadeIn(self.label("均匀长绳，小幅扰动；相遇期间没有边界反射", 0, -1.8, 28)), run_time=1)
        self.until(begin + 3.44)
        self.mark("pulses_separate")
        self.focus_begin("pulses_before")
        self.until(begin + 10.9)
        self.focus_end("pulses_before")
        self.until(begin + 11)
        self.focus_begin("pulses_approach")
        self.until(begin + 17.3)
        self.advance(t, 1.5)
        self.mark("pulses_near")
        self.until(begin + 23.5)
        self.focus_end("pulses_approach")

    def addition(self):
        begin = float(self.get_time())
        self.clear_stage()
        self.title("同一位置、同一时刻，位移相加")
        t = ValueTracker(1.5)
        points, _ = self.pulse_world(t)
        column = Line(points[-1](5, -.3), points[0](5, 1.2), color=GUIDE, stroke_width=1.5)
        segments = VGroup(*(Line(p(5, 0), p(5, .001), color=color, stroke_width=5)
                            for p, color in zip(points, (WAVE, SECOND, PARTICLE))))

        def update_segments(_):
            state = model.pulse_state(5, t.get_value())
            for segment, p, key in zip(segments, points, ("y1_cm", "y2_cm", "y_cm")):
                segment.set_points_as_corners([p(5, 0), p(5, state[key])])

        self.driver(update_segments)
        self.play(ShowCreation(column), FadeIn(segments), run_time=1)
        self.until(begin + 4.28)
        self.mark("component_rows_ready")
        self.focus_begin("aligned_components")
        self.until(begin + 13.6)
        self.advance(t, 2.5)
        self.mark("partial_sum_ready")
        self.until(begin + 14.7)
        self.focus_end("aligned_components")
        self.focus_begin("partial_overlap")
        self.until(begin + 20.1)
        self.focus_end("partial_overlap")
        self.focus_begin("complete_addition_motion")
        self.advance(t, 3)
        self.mark("positive_collision")
        self.focus_end("complete_addition_motion")
        self.focus_begin("complete_addition")
        operands = self.put(r"(+1)+(+1)", 0, 0, size=37, color=PARTICLE)
        answer = self.put(r"=+2\,\mathrm{cm}", 0, 0, size=37, color=PARTICLE)
        equation = Group(operands, answer).arrange(np.array([1, 0, 0]), buff=.12).move_to([0, -2.97, 0])
        self.play(FadeIn(operands), run_time=.4)
        self.mark("double_height_ready")
        self.until(begin + 23.8)
        self.play(FadeIn(answer), run_time=.3)
        self.mark("addition_numeric_ready")
        self.until(begin + 25.6)
        self.play(FadeOut(operands), FadeOut(answer), FadeOut(column), FadeOut(segments), run_time=.3)

        # Compare another location in this same frozen snapshot, not another time.
        x = 4.5
        state = model.pulse_state(x, 3)
        local_segments = VGroup(*(Line(p(x, 0), p(x, state[key]), color=color, stroke_width=5)
                                  for p, key, color in zip(points, ("y1_cm", "y2_cm", "y_cm"), (WAVE, SECOND, PARTICLE))))
        local_column = Line(points[-1](x, -.3), points[0](x, 1.2), color=GUIDE, stroke_width=1.5)
        local_label = self.put(r"x=4.5\,\mathrm m", -.55, 2.65, size=27, color=PARTICLE)
        local_operands = self.put(f"{state['y1_cm']:.2f}+{state['y2_cm']:.2f}", 0, 0, size=37, color=PARTICLE)
        local_answer = self.put(r"\approx" + f"{state['y_cm']:.2f}" + r"\,\mathrm{cm}", 0, 0, size=37, color=PARTICLE)
        Group(local_operands, local_answer).arrange(np.array([1, 0, 0]), buff=.12).move_to([0, -2.97, 0])
        self.play(FadeIn(local_segments), FadeIn(local_column), FadeIn(local_label), FadeIn(local_operands), run_time=.5)
        self.mark("addition_local_probe_ready")
        self.until(begin + 29)
        self.play(FadeIn(local_answer), run_time=.4)
        self.mark("addition_local_sum_ready")
        self.until(begin + 32)
        self.focus_end("complete_addition")

    def through(self):
        begin = float(self.get_time())
        self.clear_stage()
        self.title("相遇后，各自通过")
        t = ValueTracker(3)
        points, _ = self.pulse_world(t)
        self.until(begin + 3.38)
        self.mark("through_collision_start")
        self.focus_begin("through_start")
        self.until(begin + 7.5)
        self.focus_end("through_start")
        self.focus_begin("pulses_pass")
        self.until(begin + 7.7)
        self.advance(t, 4)
        self.mark("through_mid")
        self.until(begin + 9.6)
        self.advance(t, 4.5)
        self.until(begin + 13.3)
        self.advance(t, 5)
        self.until(begin + 14)
        self.focus_end("pulses_pass")
        arrows = Group(Arrow(points[0](6.5, 1.5), points[0](7.5, 1.5), buff=0, fill_color=WAVE, thickness=2.5),
                       Arrow(points[1](3.5, 1.5), points[1](2.5, 1.5), buff=0, fill_color=SECOND, thickness=2.5))
        self.driver(lambda _: [arrow.move_to(p(center, 1.5)) for arrow, p, center in
                               zip(arrows, points[:2], model.pulse_centers(t.get_value()))])
        self.play(FadeIn(arrows), run_time=.4)
        self.mark("through_result_ready")
        self.focus_begin("through_result")

        histories, heights = [], []
        for index, (key, color, local_time) in enumerate(zip(("y1_cm", "y2_cm"), (WAVE, SECOND), (15, 16.2))):
            p = points[index]
            old_center = model.pulse_centers(1.5)[index]
            center = model.pulse_centers(5)[index]
            xs = np.linspace(old_center - model.PULSE_HALF_WIDTH_M, old_center + model.PULSE_HALF_WIDTH_M, 101)
            ghost = DashedVMobject(polyline([p(x, model.pulse_state(x, 1.5)[key]) for x in xs], color, 2.5), num_dashes=25)
            ghost.set_stroke(opacity=.6)
            label = self.label("相遇前 t=1.5s", *p(old_center, 1.8)[:2], size=22, color=color, width=3.4)
            histories.append(Group(ghost, label))
            heights.append(Group(
                Line(p(old_center, 0), p(old_center, 1), color=color, stroke_width=3),
                Line(p(center, 0), p(center, 1), color=color, stroke_width=3),
                DashedVMobject(Line(p(old_center, 1), p(center, 1), color=color, stroke_width=2), num_dashes=22),
                self.put(r"1\,\mathrm{cm}", *p((old_center + center) / 2, 1.8)[:2], size=27, color=color)))
            self.until(begin + local_time)
            self.play(FadeIn(histories[-1]), run_time=.4)
            self.mark("through_compare_first" if index == 0 else "through_compare_second")
        for index, (height, local_time) in enumerate(zip(heights, (18, 20))):
            self.until(begin + local_time)
            self.play(FadeIn(height), run_time=.5)
            self.mark("through_height_first" if index == 0 else "through_height_second")
        self.until(begin + 22.2)
        self.play(*(FadeOut(obj) for obj in [*histories, *heights]), run_time=.4)
        self.until(begin + 22.8)
        self.advance(t, 6)
        self.mark("through_after")
        for index, (x, local_time) in enumerate(((8, 24.5), (2, 26))):
            self.until(begin + local_time)
            state = model.pulse_state(x, 6)
            projection = DashedVMobject(Line(points[0](x, state["y1_cm"]), points[-1](x, state["y_cm"]),
                                             color=GUIDE, stroke_width=2), num_dashes=30)
            self.play(FadeIn(projection), run_time=.4)
            self.mark("through_sum_first" if index == 0 else "through_sum_second")
        self.play(FadeIn(self.label("同处同时：实际位移仍是两分量之和", 0, -2.97, 29)), run_time=.4)
        self.until(begin + 29)
        self.focus_end("through_result")

    def cancellation(self):
        begin = float(self.get_time())
        self.clear_stage()
        self.title("一上一下，平直的一刻意味着消失吗？")
        t = ValueTracker(1.5)
        points, _ = self.pulse_world(t, second_amplitude=-1)
        self.until(begin + 3.38)
        self.mark("opposite_separate")
        self.focus_begin("opposite_before")
        self.until(begin + 7.3)
        self.focus_end("opposite_before")
        self.focus_begin("opposite_approach")
        self.advance(t, 2.5)
        self.mark("opposite_partial")
        self.until(begin + 12.4)
        self.advance(t, 3)
        self.mark("zero_displacement")
        self.focus_end("opposite_approach")
        self.mark("flat_result_ready")
        self.focus_begin("flat_result")
        self.until(begin + 16)
        self.focus_end("flat_result")
        p = points[-1]
        velocity_arrows = Group(*(Arrow(p(x, 0), p(x, .5 * model.pulse_state(x, 3, -1)["vy_cm_s"]),
                                        buff=0, fill_color=PARTICLE, thickness=2.5) for x in (4.5, 5.5)))
        equation = self.put(r"y_1+y_2=0", 0, -2.97, size=38, color=PARTICLE)
        velocity_caption = self.label("箭头：这一刻质点的速度方向", .4, 2.65, 26, PARTICLE, width=6)
        self.play(FadeIn(velocity_arrows), FadeIn(equation),
                  FadeIn(velocity_caption), run_time=.4)
        self.mark("cancellation_velocity_ready")
        self.focus_begin("zero_not_rest")
        self.until(begin + 25.8)
        self.focus_end("zero_not_rest")
        self.play(FadeOut(velocity_arrows), FadeOut(equation), FadeOut(velocity_caption), run_time=.4)
        self.until(begin + 26.3)
        self.focus_begin("opposite_pass")
        self.until(begin + 26.6)
        self.advance(t, 4.5)
        self.mark("opposite_reappearing")
        self.advance(t, 6)
        self.mark("opposite_after")
        self.until(begin + 38.5)
        self.focus_end("opposite_pass")

    def exit_task(self):
        begin = float(self.get_time())
        self.clear_stage()
        self.title("上方 1 cm，下方 0.5 cm，相遇时呢？")
        t = ValueTracker(0)
        points, _ = self.pulse_world(t, second_amplitude=-.5)
        self.until(begin + 3.28)
        self.mark("unequal_question")
        self.focus_begin("unequal_prediction")
        self.until(begin + 8.6)
        self.focus_end("unequal_prediction")
        self.focus_begin("unequal_test")
        self.advance(t, 3)
        self.mark("unequal_collision")
        equation = self.put(r"(+1)+(-0.5)=+0.5\,\mathrm{cm}", 0, -2.97, size=37, color=PARTICLE)
        self.play(FadeIn(equation), run_time=.2)
        self.until(begin + 16.3)
        self.focus_end("unequal_test")
        self.remove(equation)
        self.until(begin + 16.6)
        self.focus_begin("unequal_pass")
        self.advance(t, 6)
        self.mark("unequal_after")
        self.until(begin + 19.8)
        self.focus_end("unequal_pass")
        self.play(FadeIn(self.label("若波源连续振动，会出现固定的相消处吗？", 0, -2.97, 28)), run_time=.4)
        self.mark("superposition_closed")
        self.focus_begin("superposition_handoff")
        self.until(begin + 30)
        self.focus_end("superposition_handoff")
