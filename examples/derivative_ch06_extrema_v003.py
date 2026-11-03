"""Chapter 06 original-WAV presentation revision; no review authority.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main, native tests,
independent reviewers. Lifecycle: one v003 construct. Source, timing, plan or
geometry changes invalidate evidence. Original author: 01a199e9-7432-7052-96f7-6bd6eb2e63bb.
"""

from derivative_ch06_extrema import DerivativeCh06Extrema, stationary_cubic, graph_point
from manimlib import Dot, FadeIn, Group, Line, ShowCreation, ValueTracker, linear
from derivative_chapter_shared import ACCENT, RATE


AUTHOR_AGENT = "01a19acd-e149-74d0-8a5d-975a3adf45f4"


class DerivativeCh06ExtremaV003(DerivativeCh06Extrema):
    def beat(self, fraction, *animations, **kwargs):
        key = f"{fraction:.2f}"
        end = self._cue["stage_times"][key]
        if animations:
            start = self._cue["animation_starts"].get(key, end-.4)
            absolute = self._cue["start"]+start
            if round(absolute*self.camera.fps) > round(self.get_time()*self.camera.fps):
                self.until(absolute)
        super().beat(fraction, *animations, **kwargs)
        hold = self._cue.get("post_holds", {}).get(key)
        if hold is not None:
            self.until(self._cue["start"]+hold)

    def focus_end(self, identity):
        # The sign row remains visible underneath the later monotonicity row.
        # Original phrases meet at the same estimate: do not erase that real
        # referent at the start of its last words to fit an artificial gap.
        if (identity in self._cue.get("persistent_focuses", [])
                and round(self.get_time()*self.camera.fps)
                < round((self._cue["start"]+self._cue["duration"])*self.camera.fps)):
            return
        super().focus_end(identity)

    def stationary(self, cue):
        self.begin_chapter(cue)
        self.beat(.13, FadeIn(self.graph(stationary_cubic, (-1.5, 1.5))),
                  FadeIn(self.put(r"g(x)=x^3", 3.5, 2, size=43)),
                  FadeIn(self.put(r"g'(x)=3x^2", 3.5, 1.1, size=39, color=RATE)),
                  FadeIn(self.put(r"g'(0)=0", 3.5, .2, size=40, color=ACCENT)))
        self.mark("stationary_zero_ready")
        self.focus_begin("stationary_zero")
        self.beat(.24, ShowCreation(Line(graph_point(-.7, 0), graph_point(.7, 0), color=ACCENT, stroke_width=4)))
        self.mark("stationary_tangent_ready")
        self.beat(.31)
        self.focus_end("stationary_zero")
        self.beat(.36, FadeIn(self.put(r"+\quad 0\quad +", 3.5, -.8, size=42, color=RATE)))
        tracker = ValueTracker(-1.2)
        dot = Dot(graph_point(-1.2, stationary_cubic(-1.2)), color=ACCENT, radius=.08)
        driver = Group()

        def update(_):
            x = tracker.get_value()
            dot.move_to(graph_point(x, stationary_cubic(x)))
            self.sample("stationary_pass", x=x, y=stationary_cubic(x), derivative=3*x*x,
                        point=dot.get_center().tolist())

        update(driver)
        driver.add_updater(update)
        self.add(driver, dot)
        self.mark("stationary_pass_start")
        self.focus_begin("stationary_pass")
        self.beat(.53, tracker.animate.set_value(0), rate_func=linear)
        self.beat(.58)
        self.beat(.73, tracker.animate.set_value(1.2), rate_func=linear)
        self.focus_end("stationary_pass")
        driver.clear_updaters()
        self.beat(.80, FadeIn(self.label("经过原点后继续增：驻点，无极值", 3.5, -1.85, size=27, width=5.5)))
        self.mark("stationary_no_extremum_ready")
        self.focus_begin("stationary_no_extremum")
        self.end_chapter()

    def closing(self, cue):
        self.begin_chapter(cue)
        self.beat(.16, FadeIn(self.label("附近比较，决定局部极值", 0, 2, size=36)),
                  FadeIn(self.put(r"+\to-:\ \mathrm{max}\qquad -\to+:\ \mathrm{min}", 0, .85, size=43, color=RATE)),
                  FadeIn(self.label("可导内点先找驻点，再看两侧增减", 0, -.25, size=31)))
        self.mark("local_method_ready")
        self.focus_begin("local_method")
        self.beat(.65)
        self.focus_end("local_method")
        self.beat(.74, FadeIn(self.label("如果和整个区间比较，端点怎么办？", 0, -1.75, size=33, color=ACCENT)))
        self.mark("whole_interval_question_ready")
        self.focus_begin("whole_interval_question")
        self.beat(.88, FadeIn(self.label("端点不套用“可导内点”的必要条件", 0, -2.65, size=27)))
        self.mark("boundary_scope_ready")
        self.end_chapter()
