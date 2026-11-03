"""not_reviewed: chapter-03 presentation timing, inherited math/geometry unchanged.

Cue-local starts and movement finishes expire when the cue ends. The inherited
scene owns trackers, formulas, geometry and focus lifetimes; this wrapper only
waits, runs the original native animations and holds their completed states.
Any source/timing change invalidates the journal. No review authority is supplied.
"""

from derivative_ch03_rules import DerivativeRulesLesson


class DerivativeRulesLessonV004(DerivativeRulesLesson):
    def beat(self, fraction, *animations, **kwargs):
        key = f"{fraction:.2f}"
        target = self.stage_time(fraction)
        if animations:
            offset = self._cue.get("animation_starts", {}).get(key)
            if offset is None:
                offset = self._cue["stage_times"][key] - .4
            start = self._cue["start"] + offset
            if round(start*self.camera.fps) > round(self.get_time()*self.camera.fps):
                self.until(start)
            finish = self._cue["start"] + self._cue.get("animation_ends", {}).get(
                key, self._cue["stage_times"][key])
            if finish > target + 1e-8:
                raise ValueError("Motion finish must precede its cue-local hold boundary")
            self.until(finish, *animations, **kwargs)
            self.until(target)
        else:
            self.until(target)

    def safe_formula(self, source, target, end, **kwargs):
        self.until(self._cue["start"] + self._cue["animation_starts"][f"{end:.2f}"])
        return super().safe_formula(source, target, end, **kwargs)
