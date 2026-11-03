"""Independent superposition production scene; inherited per-scene runtime only."""

import numpy as np
from manimlib import Arrow, Dot, FadeIn, FadeOut, Group, Line, ShowCreation, ValueTracker, VGroup

from wave_unit_shared import (
    WaveLessonBase, GUIDE, INK, MUTED, PARTICLE, SECOND, WAVE, model, polyline,
)


class WaveSuperpositionLesson(WaveLessonBase):
    durations = (24, 32, 28, 44, 30)

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
        x_label.move_to(bottom(10, 0) + [.45 + x_label.get_width() / 2, -.28, 0])
        names.add(x_label)
        for x in (0, 2, 4, 6, 8, 10):
            axes.add(Line(bottom(x, -.05), bottom(x, .05), color=MUTED, stroke_width=2))
            names.add(self.put(str(x), *(bottom(x, 0) + [0, -.28, 0])[:2], size=23))
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
        self.title("两个脉冲相遇，会反弹吗？")
        t = ValueTracker(0)
        points, _ = self.pulse_world(t, rows=False)
        p = points[0]
        arrows = Group(
            Arrow(p(1.5, 1.7), p(2.8, 1.7), buff=0, fill_color=WAVE, thickness=2.5),
            Arrow(p(8.5, 1.7), p(7.2, 1.7), buff=0, fill_color=SECOND, thickness=2.5))
        self.play(FadeIn(arrows), FadeIn(self.label("均匀长绳，小幅扰动；相遇期间没有边界反射", 0, -1.8, 28)), run_time=1)
        self.read("pulses_before", 7, "pulses_separate")
        self.focus_begin("pulses_approach")
        self.advance(t, 1.5)
        self.mark("pulses_near")
        self.wait(11.5)
        self.focus_end("pulses_approach")

    def addition(self):
        self.clear_stage()
        self.title("同一位置、同一时刻，位移相加")
        t = ValueTracker(1.5)
        points, _ = self.pulse_world(t)
        column = Line(points[-1](5, -.3), points[0](5, 1.2), color=GUIDE, stroke_width=1.5)
        self.play(ShowCreation(column), run_time=1)
        self.read("aligned_components", 6, "component_rows_ready")
        self.focus_begin("partial_overlap")
        self.advance(t, 2.5)
        self.mark("partial_sum_ready")
        self.wait(7)
        self.focus_end("partial_overlap")
        self.focus_begin("complete_addition_motion")
        self.advance(t, 3)
        self.mark("positive_collision")
        self.focus_end("complete_addition_motion")
        segments = VGroup(*(Line(p(5, 0), p(5, model.pulse_state(5, 3)[key]),
                                  color=color, stroke_width=5)
                            for p, key, color in zip(points, ("y1_cm", "y2_cm", "y_cm"), (WAVE, SECOND, PARTICLE))))
        self.play(ShowCreation(segments), FadeIn(self.put(r"(+1)+(+1)=+2\,\mathrm{cm}", 0, -2.75, size=37, color=PARTICLE)), run_time=1)
        self.read("complete_addition", 12.5, "double_height_ready")

    def through(self):
        self.clear_stage()
        self.title("相遇后，各自通过")
        t = ValueTracker(3)
        points, _ = self.pulse_world(t)
        self.read("through_start", 5, "through_collision_start")
        self.focus_begin("pulses_pass")
        self.advance(t, 4)
        self.mark("through_mid")
        self.wait(4)
        self.advance(t, 6)
        self.mark("through_after")
        self.focus_end("pulses_pass")
        arrows = Group(Arrow(points[0](7.5, 1.5), points[0](8.5, 1.5), buff=0, fill_color=WAVE, thickness=2.5),
                       Arrow(points[1](2.5, 1.5), points[1](1.5, 1.5), buff=0, fill_color=SECOND, thickness=2.5))
        self.play(FadeIn(arrows), FadeIn(self.label("分量延续原方向；实际位移始终是两者之和", 0, -2.75, 29)), run_time=1)
        self.read("through_result", 12, "through_result_ready")

    def cancellation(self):
        self.clear_stage()
        self.title("一上一下，平直的一刻意味着消失吗？")
        t = ValueTracker(0)
        points, _ = self.pulse_world(t, second_amplitude=-1)
        self.read("opposite_before", 5, "opposite_separate")
        self.focus_begin("opposite_approach")
        self.advance(t, 2.5)
        self.mark("opposite_partial")
        self.wait(4)
        self.advance(t, 3)
        self.mark("zero_displacement")
        self.focus_end("opposite_approach")
        self.read("flat_result", 6, "flat_result_ready")
        p = points[-1]
        velocity_arrows = Group(*(Arrow(p(x, 0), p(x, .5 * model.pulse_state(x, 3, -1)["vy_cm_s"]),
                                        buff=0, fill_color=PARTICLE, thickness=2.5) for x in (4.5, 5.5)))
        equation = self.put(r"y_1+y_2=0", 0, -2.7, size=38, color=PARTICLE)
        velocity_caption = self.label("箭头：这一刻质点的速度方向", .4, 2.65, 26, PARTICLE, width=6)
        self.play(FadeIn(velocity_arrows), FadeIn(equation),
                  FadeIn(velocity_caption), run_time=1)
        self.read("zero_not_rest", 9, "cancellation_velocity_ready")
        self.play(FadeOut(velocity_arrows), FadeOut(equation), FadeOut(velocity_caption), run_time=1)
        self.focus_begin("opposite_pass")
        self.advance(t, 4.5)
        self.mark("opposite_reappearing")
        self.advance(t, 6)
        self.mark("opposite_after")
        self.wait(9)
        self.focus_end("opposite_pass")

    def exit_task(self):
        self.clear_stage()
        self.title("上方 1 cm，下方 0.5 cm，相遇时呢？")
        t = ValueTracker(0)
        points, _ = self.pulse_world(t, second_amplitude=-.5)
        self.read("unequal_prediction", 6, "unequal_question")
        self.focus_begin("unequal_test")
        self.advance(t, 3)
        self.mark("unequal_collision")
        equation = self.put(r"(+1)+(-0.5)=+0.5\,\mathrm{cm}", 0, -2.75, size=37, color=PARTICLE)
        self.play(FadeIn(equation), run_time=1)
        self.wait(6)
        self.focus_end("unequal_test")
        self.remove(equation)
        self.focus_begin("unequal_pass")
        self.advance(t, 6)
        self.mark("unequal_after")
        self.wait(3)
        self.focus_end("unequal_pass")
        self.play(FadeIn(self.label("若波源连续振动，会出现固定的相消处吗？", 0, -2.75, 28)), run_time=1)
        self.read("superposition_handoff", 4, "superposition_closed")
