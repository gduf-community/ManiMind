"""Independent reading production scene; inherited per-scene runtime only."""

import numpy as np
from manimlib import Arrow, Circle, Dot, FadeIn, FadeOut, Group, Line, ShowCreation, ValueTracker, VGroup

from wave_unit_shared import (
    WaveLessonBase, GUIDE, INK, MUTED, PARTICLE, SECOND, WAVE, model, polyline,
)


class WaveReadingLesson(WaveLessonBase):
    durations = (24, 30, 38, 32, 30, 28)

    @property
    def chapters(self):
        return (self.snapshot, self.wavelength, self.time_record, self.speed, self.direction, self.exit_task)

    def snapshot(self):
        self.title("同一根绳，两种读法")
        t = ValueTracker(0)
        _, _, p = self.string_world(t)
        self.add(self.clock(t))
        self.play(FadeIn(self.label("从这张已建立的波形重新计时：t = 0", 0, 2.45, 30)), run_time=1)
        self.read("time_origin", 6, "reading_origin_ready")
        sample = VGroup(*(Line(p(x, 0), p(x, model.harmonic(x, 0)), color=color, stroke_width=4)
                          for x, color in ((4, PARTICLE), (6, SECOND))))
        self.play(ShowCreation(sample), FadeIn(self.label("同一时刻，不同位置", 0, -1.8, 34)), run_time=1)
        self.read("spatial_slice", 14, "spatial_slice_ready")

    def wavelength(self):
        self.clear_stage()
        self.title("空间快照：相邻同相位点相隔多远？")
        t = ValueTracker(0)
        _, _, p = self.string_world(t, probes=(4, 8))
        self.add(self.clock(t))
        self.read("snapshot_peaks", 6, "two_spatial_peaks")
        bracket = self.span(p(4, 0)[0], p(8, 0)[0], 1.9, r"\lambda=4\,\mathrm m", WAVE)
        self.play(FadeIn(bracket), FadeIn(self.label("波形图 y-x：横轴是位置", 0, -1.8, 33)), run_time=1)
        self.read("lambda_in_space", 10, "wavelength_ready")
        half = self.span(p(4, 0)[0], p(6, 0)[0], -2.5, r"2\,\mathrm m=\lambda/2", SECOND)
        self.play(FadeIn(half), run_time=1)
        self.read("crest_trough_not_lambda", 9, "half_wavelength_ready")

    def time_record(self):
        self.clear_stage()
        self.title("固定 x = 4 m，把位移按时间留下来")
        t = ValueTracker(0)
        _, selected, p = self.string_world(t, baseline=1.25, scale=.6)
        q = lambda time, y: np.array([-5.5 + 1.1 * time, -1.5 + .6 * y, 0.])
        axes = self.axes(q, 8, r"t\,(\mathrm s)", r"y\,(\mathrm{cm})", ticks=(0, 2, 4, 6, 8))
        graph = polyline([q(0, 1), q(.0001, model.harmonic(4, .0001))], PARTICLE)
        pen = Dot(q(0, 1), fill_color=PARTICLE, radius=.075)
        self.play(FadeIn(axes), FadeIn(graph), FadeIn(pen),
                  FadeIn(self.label("同一质点的时间记录", 1.9, -.45, 30, PARTICLE)), run_time=1)
        self.add(self.clock(t, x=4.65, y=2.7))

        def update(_):
            end = max(.0001, t.get_value())
            pairs = model.temporal_record(4, np.linspace(0, end, 241))
            graph.set_points_as_corners([q(time, y) for time, y in pairs])
            pen.move_to(q(t.get_value(), model.harmonic(4, t.get_value())))
            self.sample("record", physical_s=float(t.get_value()), fixed_x_m=4,
                        bead_y_cm=model.harmonic(4, t.get_value()),
                        bead=selected[0].get_center().tolist(), pen=pen.get_center().tolist())

        self.driver(update)
        self.read("fixed_place_record", 5, "temporal_axes_ready")
        self.focus_begin("record_first_cycle")
        self.advance(t, 1)
        self.mark("record_quarter")
        self.wait(3)
        self.advance(t, 2)
        self.mark("record_half")
        self.wait(3)
        self.advance(t, 4)
        self.mark("record_cycle")
        self.wait(3)
        self.focus_end("record_first_cycle")
        bracket = self.span(q(0, 0)[0], q(4, 0)[0], -2.45, r"T=4\,\mathrm s", PARTICLE)
        self.play(FadeIn(bracket), run_time=1)
        self.focus_begin("period_in_time")
        self.advance(t, 8)
        self.mark("record_two_cycles")
        self.wait(10)
        self.focus_end("period_in_time")

    def speed(self):
        self.clear_stage()
        self.title("把空间的 4 m，接到时间的 4 s")
        t = ValueTracker(0)
        _, _, p = self.string_world(t)
        self.add(self.clock(t))
        self.phase_marker(t, p, 4, 0)
        origin = Circle(radius=.17).set_stroke(MUTED, 2).move_to(p(4, 1))
        self.play(FadeIn(origin), FadeIn(self.put(r"\Delta t=T=4\,\mathrm s", -2.7, 2.4, size=38)), run_time=1)
        self.read("speed_start", 5, "speed_start_ready")
        self.focus_begin("speed_crest_motion")
        self.advance(t, 2)
        self.mark("speed_mid")
        self.wait(3)
        self.advance(t, 4)
        self.mark("speed_one_cycle")
        self.wait(4)
        self.focus_end("speed_crest_motion")
        distance = self.span(p(4, 0)[0], p(8, 0)[0], 1.85, r"\Delta x=\lambda=4\,\mathrm m", WAVE)
        self.play(FadeIn(distance), run_time=1)
        self.read("distance_is_wavelength", 4, "speed_distance_ready")
        self.play(FadeIn(self.put(r"v=\frac{\Delta x}{\Delta t}=\frac{\lambda}{T}=1\,\mathrm{m/s}", 0, -1.8, size=43)), run_time=1)
        self.read("speed_ratio", 5, "speed_relation_ready")

    def direction(self):
        self.clear_stage()
        self.title("波向右，质点此刻向上还是向下？")
        t = ValueTracker(0)
        _, _, p = self.string_world(t, probes=(5,))
        self.add(self.clock(t))
        location = self.put(r"x=5\,\mathrm m", 0, 2.45, size=37, color=PARTICLE)
        self.play(FadeIn(location),
                  FadeIn(self.label("下一小段时间，左侧的形状会接替到这里", 0, -1.8, 31)), run_time=1)
        self.read("slope_prediction", 6, "direction_question_ready")
        prior = Dot(p(4.5, model.harmonic(4.5, 0)), fill_color=WAVE, radius=.075)
        height = model.harmonic(4.5, 0)
        shift = Arrow(p(4.5, height), p(5, height), buff=0, fill_color=WAVE, thickness=2.5)
        self.play(FadeIn(prior), FadeIn(shift), run_time=1)
        self.read("left_shape_arrives", 5, "left_shape_ready")
        self.focus_begin("particle_rises")
        self.advance(t, .5)
        self.mark("direction_shifted")
        self.play(FadeOut(location), FadeIn(self.label("黄色质点向上；横坐标仍是 5 m", 0, 2.45, 31, PARTICLE)), run_time=1)
        self.wait(7.5)
        self.focus_end("particle_rises")
        self.play(FadeOut(Group(prior, shift)), run_time=1)
        self.read("direction_limit", 4, "direction_result_ready")

    def exit_task(self):
        self.clear_stage()
        self.title("先看横轴，再读重复的距离")
        p = lambda x, y: self.point(x, y, 1.2, .6)
        q = lambda time, y: np.array([-5.5 + 1.1 * time, -1.45 + .6 * y, 0.])
        upper = Group(self.axes(p, 10, r"x\,(\mathrm m)", r"y\,(\mathrm{cm})"),
                      polyline([p(x, y) for x, y in model.spatial_snapshot(0, np.linspace(0, 10, 401))]))
        lower = Group(self.axes(q, 8, r"t\,(\mathrm s)", r"y\,(\mathrm{cm})", ticks=(0, 2, 4, 6, 8)),
                      polyline([q(t, y) for t, y in model.temporal_record(4, np.linspace(0, 8, 321))], PARTICLE))
        self.play(FadeIn(upper), FadeIn(lower), run_time=1)
        self.read("reading_exit_question", 6, "reading_exit_ready")
        spans = Group(self.span(p(4, 0)[0], p(8, 0)[0], 2.05, r"\lambda=4\,\mathrm m", WAVE),
                      self.span(q(0, 0)[0], q(4, 0)[0], -2.35, r"T=4\,\mathrm s", PARTICLE))
        self.play(FadeIn(spans), run_time=1)
        self.read("reading_exit_answer", 8, "reading_exit_answer_ready")
        self.play(FadeIn(self.label("同一位置、同一时刻，若有两列波呢？", 2.2, -.25, 30)), run_time=1)
        self.read("reading_handoff", 9, "reading_closed")
