"""A quiet title/question opening; the released lesson body is not rerendered."""

import numpy as np
from manimlib import FadeIn, FadeOut, Group, Line, VMobject

from manimind.experiments.understanding_support import UnderstandingScene


class WaveOpening(UnderstandingScene):
    def construct(self):
        cue = self.cues[0]
        eyebrow = self.cn(cue["eyebrow"], size=25, color="#AAB3B9").move_to([0, 2.18, 0])
        title = self.cn(cue["heading"], size=66).move_to([0, 1.08, 0])
        question = self.cn(cue["question"], size=32, color="#D4DBDF").move_to([0, -.08, 0])
        if max(title.get_width(), question.get_width()) > 12:
            raise ValueError("Opening text must fit without shrinking the lesson title")
        rule = Line([-2.2, 1.73, 0], [2.2, 1.73, 0], color="#46575C", stroke_width=1.5)
        self.add(eyebrow, title, rule)
        self.mark("title_ready")
        self.wait(.6)
        self.play(FadeIn(question), run_time=.4)
        self.mark("question_ready")
        self.focus_begin("opening_question")

        # A low-amplitude wave is a unit identity motif, not a new experiment.
        xs = np.linspace(-4.6, 4.6, 241)
        motif = VMobject().set_stroke("#58D5B0", 2.5)

        def update_wave(_):
            time = self.get_time()
            motif.set_points_as_corners([
                [x, -1.36 + .16 * np.sin(1.6 * x - .7 * time), 0] for x in xs
            ])

        update_wave(motif)
        self.play(FadeIn(motif), run_time=.3)
        motif.add_updater(update_wave)
        self.until(cue["duration"] - .4)
        self.focus_end("opening_question")
        motif.clear_updaters()
        self.play(FadeOut(Group(eyebrow, title, rule, question, motif)), run_time=.4)
