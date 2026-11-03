"""Three fresh native ManimGL lessons sharing one tested travelling-wave model.

Run through understanding_render, which puts the tracked examples directory on
PYTHONPATH even when this scene is copied into its render-attempt directory.
"""

import json

import numpy as np
from manimlib import (
    Arrow, Circle, Dot, FadeIn, FadeOut, Group, Line, ShowCreation,
    ValueTracker, VMobject, VGroup, linear,
)

from manimind.experiments.understanding_support import UnderstandingScene
import wave_unit_model as model


INK = "#EEF1F4"
WAVE = "#58D5B0"
PARTICLE = "#F3D36A"
SECOND = "#FF8F98"
MUTED = "#AAB3B9"
GUIDE = "#46575C"


def polyline(points, color=WAVE, width=4):
    return VMobject().set_points_as_corners(points).set_stroke(color, width)


class WaveLessonBase(UnderstandingScene):
    def label(self, text, x, y, size=32, color=INK, width=12.2):
        obj = self.cn(text, size=size, color=color)
        if obj.get_width() > width:
            obj.set_width(width)
        return obj.move_to([x, y, 0])

    def put(self, latex, x, y, size=38, color=INK, width=11.5):
        obj = self.formula(latex, size=size, color=color)
        if obj.get_width() > width:
            obj.set_width(width)
        return obj.move_to([x, y, 0])

    def title(self, text):
        self.play(FadeIn(self.label(text, 0, 3.35, 39)), run_time=1)

    def clear_stage(self):
        for driver in self.drivers:
            driver.clear_updaters()
        self.drivers = []
        objects = [obj for obj in self.mobjects if obj is not self._subtitle_driver]
        if objects:
            self.play(*(FadeOut(obj) for obj in objects), run_time=1)

    def read(self, identity, seconds, event=None):
        if event:
            self.mark(event)
        self.focus_begin(identity)
        self.wait(seconds)
        self.focus_end(identity)

    def driver(self, callback):
        result = Group()
        result.add_updater(callback)
        self.drivers.append(result)
        self.add(result)
        callback(result)
        return result

    def sample(self, kind, **values):
        self.motion_samples.append({"kind": kind, "render_s": float(self.get_time()), **values})

    def advance(self, tracker, target):
        # One displayed physical second per animated second. Holds freeze the
        # visible clock and all dependent geometry, rather than rescaling it.
        delta = target - tracker.get_value()
        if delta <= 0:
            raise ValueError("Physical time must advance; start a new experiment to reset it")
        self.play(tracker.animate.set_value(target), run_time=delta, rate_func=linear)

    @staticmethod
    def point(x, y, baseline=.25, scale=1.0):
        return np.array([-5.5 + 1.1 * x, baseline + scale * y, 0.])

    def axes(self, point, end, x_name="x", y_name="y", ymax=1.35, ticks=(0, 2, 4, 6, 8, 10)):
        axes = VGroup(Line(point(0, 0), point(end, 0)),
                      Line(point(0, -ymax), point(0, ymax))).set_stroke(GUIDE, 2)
        x_label = self.put(x_name, 0, 0, size=27, width=1.1)
        x_label.move_to(point(end, 0) + [.45 + x_label.get_width() / 2, -.28, 0])
        labels = Group(
            x_label,
            self.put(y_name, *(point(0, ymax) + [.12, .28, 0])[:2], size=27, width=1.5),
        )
        for x in ticks:
            if x <= end:
                axes.add(Line(point(x, -.045), point(x, .045), color=MUTED, stroke_width=2))
                labels.add(self.put(str(x), *(point(x, 0) + [0, -.28, 0])[:2], size=25))
        for y in (-1, 1):
            axes.add(Line(point(-.05, y), point(.05, y), color=MUTED, stroke_width=2))
            labels.add(self.put(str(y), *(point(0, y) + [-.28, 0, 0])[:2], size=24))
        return Group(axes, labels)

    def span(self, start, end, y, text, color=PARTICLE):
        line = VGroup(Line([start, y, 0], [end, y, 0]),
                      Line([start, y - .09, 0], [start, y + .09, 0]),
                      Line([end, y - .09, 0], [end, y + .09, 0])).set_stroke(color, 3)
        return Group(line, self.put(text, (start + end) / 2, y + .32, size=34, color=color))

    def clock(self, tracker, x=4.65, y=-2.65):
        value = self.number(tracker.get_value(), size=29, decimals=1).move_to([x, y, 0])
        result = Group(self.put("t=", x - .72, y, size=29), value,
                       self.put(r"\mathrm{s}", x + .65, y, size=29))
        self.driver(lambda _: value.set_value(tracker.get_value()))
        return result

    def string_world(self, tracker, forming=False, probes=(4,), baseline=.25, scale=1.0):
        p = lambda x, y: self.point(x, y, baseline, scale)
        value = model.forming_wave if forming else model.harmonic
        xs = np.linspace(0, 10, 401)
        curve = polyline([p(x, value(x, tracker.get_value())) for x in xs])
        sites = tuple(np.linspace(0, 10, 21))
        beads = VGroup(*(Dot(p(x, value(x, tracker.get_value())), radius=.035, fill_color=MUTED) for x in sites))
        selected = VGroup(*(Dot(p(x, value(x, tracker.get_value())), radius=.085,
                               fill_color=PARTICLE if i == 0 else SECOND) for i, x in enumerate(probes)))
        guides = VGroup(*(Line(p(x, -1.2), p(x, 1.2), color=GUIDE, stroke_width=1.3) for x in probes))
        axes = self.axes(p, 10, r"x\,(\mathrm m)", r"y\,(\mathrm{cm})")
        group = Group(axes, guides, curve, beads, selected)

        def update(_):
            t = float(tracker.get_value())
            curve.set_points_as_corners([p(x, value(x, t)) for x in xs])
            for bead, x in zip(beads, sites):
                bead.move_to(p(x, value(x, t)))
            for bead, x in zip(selected, probes):
                bead.move_to(p(x, value(x, t)))
            self.sample("string", physical_s=t, forming=forming,
                        particles=[{"x_m": float(x), "y_cm": value(x, t),
                                    "screen": bead.get_center().tolist()} for x, bead in zip(probes, selected)])

        self.play(FadeIn(group), run_time=1)
        self.driver(update)
        return group, selected, p

    def phase_marker(self, tracker, point, initial_x, origin_s):
        ring = Circle(radius=.14).set_stroke(WAVE, 3)
        self.driver(lambda _: ring.move_to(point(model.crest_position(initial_x, tracker.get_value(), origin_s), 1)))
        self.play(FadeIn(ring), run_time=1)
        return ring

    def construct(self):
        self.drivers, self.motion_samples, self.chapter_times = [], [], []
        for cue, method, duration in zip(self.cues, self.chapters, self.durations, strict=True):
            if cue["duration"] != duration:
                raise ValueError("Scene and plan cue durations disagree")
            self.until(cue["start"])
            begin = float(self.get_time())
            method()
            remaining = cue["start"] + duration - self.get_time()
            if remaining > 2.01:
                raise ValueError("Unassigned cue tail; allocate a readable task, not an empty hold")
            self.until(cue["start"] + duration)
            self.chapter_times.append({"id": cue["id"], "start": begin, "end": float(self.get_time())})

    def tear_down(self):
        report = {"duration": float(self.get_time()), "chapters": self.chapter_times,
                  "samples": self.motion_samples, "writer": "WaveLessonBase native updaters",
                  "consumers": ["lead", "independent reviewer"],
                  "lifecycle": "One exact scene execution",
                  "invalidation": "Scene, model, plan, context, profile, runtime, font or timing change",
                  "limitation": "Geometry observations, not pixel, science-review or comprehension approval"}
        with (self.out / "wave-motion.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)
        super().tear_down()


class WaveFormationLesson(WaveLessonBase):
    durations = (26, 30, 32, 34, 30)

    @property
    def chapters(self):
        return (self.contrast, self.formation, self.delay, self.period, self.exit_task)

    def contrast(self):
        self.title("波峰向前，质点呢？")
        self.play(FadeIn(self.label("绷紧的长绳，小幅横向振动；先看反射返回之前", 0, 2.55, 28)), run_time=1)
        t = ValueTracker(12)
        _, _, p = self.string_world(t)
        self.add(self.clock(t))
        self.phase_marker(t, p, 4, 12)
        self.play(FadeIn(self.label("黄色：同一个绳上质点", -2.4, -1.8, 30, PARTICLE)),
                  FadeIn(self.label("绿环：同一个波峰", 2.7, -1.8, 30, WAVE)), run_time=1)
        self.read("particle_and_crest", 6, "identities_ready")
        self.focus_begin("particle_stays_crest_moves")
        self.advance(t, 14)
        self.mark("contrast_mid")
        self.wait(3)
        self.advance(t, 16)
        self.mark("contrast_after")
        self.wait(7)
        self.focus_end("particle_stays_crest_moves")

    def formation(self):
        self.clear_stage()
        self.title("扰动怎样到达邻处？")
        t = ValueTracker(0)
        _, _, p = self.string_world(t, forming=True, probes=(2, 4))
        self.add(self.clock(t))
        source = Dot(p(0, 0), fill_color=WAVE, radius=.09)
        self.driver(lambda _: source.move_to(p(0, model.source_displacement(t.get_value()))))
        self.play(FadeIn(source), FadeIn(self.label("波源", -5.25, 2.2, 30, WAVE)),
                  FadeIn(self.label("局部形变通过相邻部分的相互作用传下去", 0, -1.8, 30)), run_time=1)
        self.read("rest_before_start", 4, "string_at_rest")
        self.focus_begin("causal_start")
        self.advance(t, 2)
        self.mark("disturbance_reaches_two")
        self.wait(4)
        self.advance(t, 4)
        self.mark("disturbance_reaches_four")
        self.wait(4)
        self.advance(t, 6)
        self.mark("formation_after")
        self.wait(8)
        self.focus_end("causal_start")

    def delay(self):
        self.clear_stage()
        self.title("后一处，稍后重复同一个状态")
        t = ValueTracker(6.5)
        _, dots, p = self.string_world(t, forming=True, probes=(2, 4))
        self.add(self.clock(t))
        names = Group(self.put(r"x=2\,\mathrm m", *p(2, -1.65)[:2], size=31, color=PARTICLE),
                      self.put(r"x=4\,\mathrm m", *p(4, -1.65)[:2], size=31, color=SECOND))
        height = model.forming_wave(2, 6.5)
        remembered = Circle(radius=.13).set_stroke(PARTICLE, 3).move_to(p(2, height))
        target = Circle(radius=.13).set_stroke(PARTICLE, 3).move_to(p(4, height))
        level = Line(p(2, height), p(4, height), color=PARTICLE, stroke_width=2)
        self.play(FadeIn(names), FadeIn(remembered), run_time=1)
        self.read("earlier_state", 7, "earlier_state_ready")
        self.focus_begin("delay_transfer")
        self.advance(t, 8.5)
        self.play(ShowCreation(level), FadeIn(target), run_time=1)
        relation = self.put(r"y(4\,\mathrm m,8.5\,\mathrm s)=y(2\,\mathrm m,6.5\,\mathrm s)",
                            0, 2.35, size=35)
        self.play(FadeIn(relation), run_time=1)
        self.mark("later_state_matches")
        self.wait(9)
        self.focus_end("delay_transfer")
        self.play(FadeOut(Group(level, target, remembered, relation)),
                  FadeIn(self.label("同一状态到达另一位置，不是同一个质点走过去", 0, 2.35, 30)), run_time=1)
        self.focus_begin("delayed_not_transported")
        self.advance(t, 10.5)
        self.mark("delay_continues")
        self.wait(5)
        self.focus_end("delayed_not_transported")

    def period(self):
        self.clear_stage()
        self.title("过一个周期：谁回原处，谁前进？")
        t = ValueTracker(12)
        _, _, p = self.string_world(t)
        self.add(self.clock(t))
        self.phase_marker(t, p, 4, 12)
        original = Circle(radius=.18).set_stroke(MUTED, 2).move_to(p(4, 1))
        self.play(FadeIn(original), FadeIn(self.put(r"T=4\,\mathrm s", 0, 2.4, size=39)), run_time=1)
        self.read("period_start", 5, "period_start_ready")
        self.focus_begin("one_period_motion")
        self.advance(t, 14)
        self.mark("period_half")
        self.wait(4)
        self.advance(t, 16)
        self.mark("period_finished")
        self.wait(5)
        self.focus_end("one_period_motion")
        distance = self.span(p(4, 0)[0], p(8, 0)[0], 1.85, r"4\,\mathrm m", WAVE)
        self.play(FadeIn(distance), FadeIn(self.label("质点完成一次振动；同一波峰向前 4 m", 0, -1.8, 31)), run_time=1)
        self.read("period_result", 9, "period_result_ready")

    def exit_task(self):
        self.clear_stage()
        self.title("再过 1 秒，黄色质点到哪里？")
        t = ValueTracker(16)
        _, _, p = self.string_world(t)
        self.add(self.clock(t))
        self.phase_marker(t, p, 8, 16)
        self.play(FadeIn(self.label("波峰再向右 1 m，质点也会向右 1 m 吗？", 0, 2.45, 30)), run_time=1)
        self.read("formation_prediction", 6, "formation_question_ready")
        self.focus_begin("formation_prediction_test")
        self.advance(t, 17)
        self.mark("formation_answer_motion")
        self.play(FadeIn(self.put(r"x=4\,\mathrm m,\qquad y=0\,\mathrm{cm}", 0, -1.75, size=39, color=PARTICLE)), run_time=1)
        self.wait(8)
        self.focus_end("formation_prediction_test")
        self.play(FadeIn(self.label("传播的是振动状态；下一课把空间和时间分开读", 0, -2.45, 29)), run_time=1)
        self.read("formation_handoff", 8, "formation_closed")


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
        self.play(FadeIn(origin), FadeIn(self.put(r"\Delta t=T=4\,\mathrm s", 0, 2.4, size=38)), run_time=1)
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


class WaveSuperpositionLesson(WaveLessonBase):
    durations = (24, 32, 28, 38, 30)

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
        p = points[-1]
        velocity_arrows = Group(*(Arrow(p(x, 0), p(x, .5 * model.pulse_state(x, 3, -1)["vy_cm_s"]),
                                        buff=0, fill_color=PARTICLE, thickness=2.5) for x in (4.5, 5.5)))
        equation = self.put(r"y_1+y_2=0", 0, -2.7, size=38, color=PARTICLE)
        self.play(FadeIn(velocity_arrows), FadeIn(equation),
                  FadeIn(self.label("箭头：这一刻质点的速度方向", .4, 2.65, 26, PARTICLE, width=6)), run_time=1)
        self.read("zero_not_rest", 9, "cancellation_velocity_ready")
        self.play(FadeOut(velocity_arrows), FadeOut(equation), run_time=1)
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
        self.focus_begin("unequal_pass")
        self.advance(t, 6)
        self.mark("unequal_after")
        self.wait(3)
        self.focus_end("unequal_pass")
        self.play(FadeOut(equation), FadeIn(self.label("若波源连续振动，会出现固定的相消处吗？", 0, -2.75, 28)), run_time=1)
        self.read("superposition_handoff", 4, "superposition_closed")
