"""Independent formation production scene; inherited per-scene runtime only."""

import numpy as np
from manimlib import Circle, Dot, FadeIn, FadeOut, Group, Line, ShowCreation, ValueTracker

from wave_unit_shared import (
    WaveLessonBase, GUIDE, INK, MUTED, PARTICLE, SECOND, WAVE, model, polyline,
)


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
