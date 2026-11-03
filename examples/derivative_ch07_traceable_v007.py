"""Delay endpoint classification until the moving stationary point has landed.

Two local display references are written during candidate setup, consumed at
the existing history-retirement beat, and cleared immediately. Source, clock
or layout changes invalidate native journals; this file has no review power.
"""
from derivative_ch07_traceable_v006 import DerivativeCh07TraceableV006
from manimlib import FadeIn


class DerivativeCh07TraceableV007(DerivativeCh07TraceableV006):
    def scaffold(self, formula, keys):
        result = super().scaffold(formula, keys)
        if self._cue["id"] == "candidates" and formula.get_tex() == r"0,\ 3":
            result.set_opacity(0)
            self._endpoint_scaffold = result
        return result

    def label(self, text, x=0, y=0, **kwargs):
        result = super().label(text, x, y, **kwargs)
        if self._cue["id"] == "candidates" and text == "端点":
            result.set_opacity(0)
            self._endpoint_label = result
        return result

    def beat(self, fraction, *animations, **kwargs):
        reveal = self._cue["id"] == "candidates" and fraction == .46
        if reveal:
            self._endpoint_scaffold.set_opacity(1)
            for key in self._endpoint_scaffold.semantic_ids:
                self._endpoint_scaffold.tag(key).set_opacity(0)
            animations = (*animations, FadeIn(self._endpoint_scaffold), FadeIn(self._endpoint_label.set_opacity(1)))
        super().beat(fraction, *animations, **kwargs)
        if reveal:
            self._endpoint_scaffold = self._endpoint_label = None
            self.sample("endpoint_classification_revealed", stationary_position_already_landed=True)
