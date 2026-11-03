"""Same v012 lesson geometry; correct the one-change-only diagnostic entry.

Writer: 01a19f6b-1725-7be3-a4d8-bf988a308b31. Probe/full use the exact
same inherited one_change method. Source/media changes invalidate evidence.
"""

from derivative_ch04_traceable_v012 import DerivativeChainTraceableV012


class DerivativeChainTraceableV013(DerivativeChainTraceableV012):
    """No mathematical or visual changes from the frozen v012 implementation."""


class DerivativeChainStateProbeV013(DerivativeChainTraceableV013):
    def construct(self):
        self.motion_samples = []
        for cue in self.cues:
            if cue["id"] != "one-change":
                raise ValueError("This diagnostic is only the actual one-change cue")
            self.begin_chapter(cue)
            self.one_change()
            self.end_chapter()
