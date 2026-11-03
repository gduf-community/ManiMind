"""Chapter 02 timing-only wrapper; inherited mathematics and geometry are frozen.

Cue-local presentation starts are authored from verified original-WAV estimates.
This class owns no mathematical state: it delays native fades/transfers/motions
while the inherited scene owns all objects, trackers, values and focus lifetimes.
Timing/source changes invalidate derived evidence. This is not a review.
"""

from derivative_ch02_basics_v002 import DerivativeBasicsLessonV002


class DerivativeBasicsLessonV004(DerivativeBasicsLessonV002):
    def beat(self, fraction, *animations, **kwargs):
        key = f"{fraction:.2f}"
        if animations:
            start = self._cue.get("animation_starts", {}).get(key)
            if start is None:
                start = self._cue["stage_times"][key] - .4
            absolute = self._cue["start"] + start
            if round(absolute * self.camera.fps) > round(self.get_time() * self.camera.fps):
                self.until(absolute)
        super().beat(fraction, *animations, **kwargs)

    def safe_formula(self, source, target, end, **kwargs):
        start = self._cue["start"] + self._cue["animation_starts"][f"{end:.2f}"]
        self.until(start)
        return super().safe_formula(source, target, end, **kwargs)
