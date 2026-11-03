"""Chapter 02: replace only the final exponential comparison footnote.

The scene writes this cue-local formula; exp_compare and later reviewers consume
it. It expires at cue exit. Source, timing or typography changes invalidate all
derived evidence. Inherited v004 timing and v002 mathematics remain unchanged.
Native construction is not pixel approval or listening review.
"""

from derivative_ch02_basics_v004 import DerivativeBasicsLessonV004


EXP_COMPARE_TEX = (
    r"(e^x)'=e^x;\quad 0<a<1:\ (a^x)'<0;\quad "
    r"a=1\ \Rightarrow\ 1^x=1,\ (1^x)'=0"
)
INHERITED_EXP_NOTE = "e为底：函数值与斜率数值相同；0<a<1 时斜率为负"


class DerivativeBasicsLessonV005(DerivativeBasicsLessonV004):
    def label(self, text, x=0, y=0, size=30, **kwargs):
        if self._cue and self._cue["id"] == "exponential" and text == INHERITED_EXP_NOTE:
            return self.sf(EXP_COMPARE_TEX, y, x=x, size=28, width=kwargs.get("width", 12.2))
        return super().label(text, x=x, y=y, size=size, **kwargs)
