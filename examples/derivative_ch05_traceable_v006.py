"""CH05 two-caption route repair; frozen v005 reasoning and motion reused.

The positive-factor caption is owned by the interval cue, consumed by native
animation/review, and retired with that cue's geometric witness. Its reference
expires immediately after retirement; any layout/source change invalidates QA.
"""
from derivative_ch05_traceable import DerivativeCh05Traceable
from manimlib import FadeOut


class DerivativeCh05TraceableV006(DerivativeCh05Traceable):
    def label(self, text, x=0, y=0, **kwargs):
        if self._cue and self._cue["id"] == "interval" and text == "中值定理：连线斜率 = 某处切线斜率":
            x, y = -3.55, 2.65
        return super().label(text, x, y, **kwargs)

    def put(self, latex, x=0, y=0, **kwargs):
        is_reminder = self._cue and self._cue["id"] == "interval" and latex == r"f'(c)>0,\quad b-a>0"
        if is_reminder:
            x, y = -3.55, -2.35
        result = super().put(latex, x, y, **kwargs)
        if is_reminder:
            self._path_positive_reminder = result
        return result

    def beat(self, fraction, *animations, **kwargs):
        retire = self._cue and self._cue["id"] == "interval" and fraction == .88
        if retire:
            animations = (*animations, FadeOut(self._path_positive_reminder))
        super().beat(fraction, *animations, **kwargs)
        if retire:
            self._path_positive_reminder.set_opacity(0)
            self._path_positive_reminder = None
            self.sample("path_caption_retired", reason="Positive proof complete before the separate decreasing case")
