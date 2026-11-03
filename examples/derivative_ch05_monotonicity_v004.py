"""not_reviewed: timing-only wrapper over the complete chapter-05 v002 scene.

All mathematical methods, values, geometry, semantic objects and focus lifecycle
are inherited. This construct removes only the old visual-duration equality
guard. Cue-local animation starts/finishes and holds expire at cue exit; source
or timing changes invalidate the emitted journal, never authorize publication.
"""

from derivative_ch05_monotonicity_v002 import DerivativeMonotonicityLessonV002, CUE_IDS


class DerivativeMonotonicityLessonV004(DerivativeMonotonicityLessonV002):
    def construct(self):
        self.motion_samples = []
        if tuple(cue["id"] for cue in self.cues) != CUE_IDS:
            raise ValueError("Chapter 05 v004 requires the complete v002 cue order")
        for cue in self.cues:
            self.until(cue["start"])
            self.begin_chapter(cue)
            getattr(self, cue["id"].replace("-", "_"))()
            self.end_chapter()

    def beat(self, fraction, *animations, **kwargs):
        key = f"{fraction:.2f}"
        if key not in self._cue.get("stage_times", {}):
            raise ValueError("Chapter 05 v004 requires an explicit authored stage time: " + key)
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
