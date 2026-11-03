"""not_reviewed: original chapter-07 content with cue-local audio timing.

The quadratic, graph, candidate model and both tracker paths are inherited.
The table and condition captions are only separated into their existing parts
so their native reveals can follow the unedited continuous original speech.
Timing data expires on cue exit; no focus event substitutes for pixel review.
"""

from derivative_ch07_extremes import (
    DerivativeCh07Extremes, Dot, FadeIn, ACCENT, CURVE, MUTED,
    candidates, graph_point,
)


class DerivativeCh07ExtremesV003(DerivativeCh07Extremes):
    def beat(self, fraction, *animations, **kwargs):
        key = f"{fraction:.2f}"
        if key not in self._cue.get("stage_times", {}):
            raise ValueError("Chapter 07 v003 requires an explicit authored stage time: " + key)
        target = self.stage_time(fraction)
        if animations:
            start = self._cue["start"] + self._cue.get("animation_starts", {}).get(
                key, self._cue["stage_times"][key] - .4)
            finish = self._cue["start"] + self._cue.get("animation_ends", {}).get(
                key, self._cue["stage_times"][key])
            if not self._cue["start"] <= start < finish <= target + 1e-8:
                raise ValueError("Native motion must finish inside its authored stage and cue")
            if round(start*self.camera.fps) > round(self.get_time()*self.camera.fps):
                self.until(start)
            self.until(finish, *animations, **kwargs)
            self.until(target)
        else:
            self.until(target)

    def compare(self, cue):
        self.begin_chapter(cue)
        self.beat(.13, FadeIn(self.graph()),
                  FadeIn(self.put("x", 2.25, 2.15, size=34)),
                  FadeIn(self.put("f(x)", 4.65, 2.15, size=34)))
        # This reference describes the real table-building process, not only
        # the completed table. Each original coordinate/value still appears.
        self.focus_begin("candidate_values")
        for index, (x, y) in enumerate(candidates(0, 3)):
            row_y = 1.25 - .9 * index
            self.beat(.21 + index*.11,
                      FadeIn(self.put(str(x), 2.25, row_y, size=39, color=ACCENT)),
                      FadeIn(Dot(graph_point(x, y), radius=.09, color=ACCENT)))
            self.beat(.23 + index*.11,
                      FadeIn(self.put(str(y), 4.65, row_y, size=39, color=CURVE)))
        self.mark("candidate_values_ready")
        self.beat(.62)
        self.focus_end("candidate_values")
        self.beat(.72, FadeIn(self.put(r"\min f=0\quad(x=1)", 3.5, -1.55,
                                     size=34, color=CURVE, width=5.5)))
        self.focus_begin("closed_extremes")
        self.beat(.79, FadeIn(self.put(r"\max f=4\quad(x=3)", 3.5, -2.4,
                                     size=34, color=ACCENT, width=5.5)))
        self.mark("closed_extremes_ready")
        self.end_chapter()

    def conditions(self, cue):
        self.begin_chapter(cue)
        self.beat(.15, FadeIn(self.graph()),
                  FadeIn(self.label("连续", 2.1, 1.95, size=32, color=CURVE)),
                  FadeIn(self.label("有限闭区间", 4.65, 1.95, size=32, color=ACCENT, width=3.3)),
                  FadeIn(self.label("曲线不断开，两个端点也在其中", 3.5, .85, size=27, width=5.5)))
        self.mark("existence_conditions_ready")
        self.focus_begin("existence_conditions")
        self.beat(.31, FadeIn(self.label("保证最大值、最小值都能取到", 3.5, -.3, size=29, width=5.5)))
        self.beat(.49)
        self.focus_end("existence_conditions")
        self.beat(.53)
        self.focus_begin("existence_and_search")
        self.beat(.58, FadeIn(self.label("本例：比较端点与内部驻点的值", 3.5, -1.3, size=27, width=5.5)))
        self.beat(.72, FadeIn(self.label("若内部不可导，还需检查那些位置", 3.5, -2.2,
                                      size=25, color=MUTED, width=5.5)))
        self.mark("existence_and_search_ready")
        self.end_chapter()
