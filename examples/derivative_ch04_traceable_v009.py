"""Keep the surviving affine increment at the same native glyph-group depth.

Writer: 01a19f6b-1725-7be3-a4d8-bf988a308b31. One construct only; changes to
source, grouping, time or pixels invalidate observations. Not review authority.
"""

from derivative_ch04_traceable_v008 import (
    DerivativeChainTraceableV008, DerivativeChainLinearProbeV008, AUTHOR_AGENT,
)
from manimlib import Transform, VGroup


class DerivativeChainTraceableV009(DerivativeChainTraceableV008):
    def at(self, offset, *animations):
        if self._cue["id"] == "linear-inner" and offset == 14 and len(animations) == 2:
            survivor = animations[1]
            # Both sides are now flat native glyph lists. Nesting a and Delta x
            # as two groups makes native alignment shrink/duplicate glyphs.
            target = VGroup(*(glyph for part in survivor.target_mobject.submobjects
                              for glyph in part.submobjects))
            animations = (animations[0], Transform(survivor.mobject, target))
            self.sample("affine_survivor_flat", glyphs=len(target))
        return super().at(offset, *animations)


class DerivativeChainLinearProbeV009(DerivativeChainTraceableV009):
    construct = DerivativeChainLinearProbeV008.construct
