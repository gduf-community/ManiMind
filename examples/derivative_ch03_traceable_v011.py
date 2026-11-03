"""Local equality-stage correction; all rendered parents remain immutable."""

from manimlib import FadeIn
from derivative_ch03_traceable_v010 import DerivativeCh03TraceableV010


class DerivativeCh03TraceableV011(DerivativeCh03TraceableV010):
    def product_example(self):
        first = self.tf(r"f(x)=x^2\sin x\qquad(x\in\mathbb R,\ \mathrm{rad})",
                        {"u": "x^2", "v": r"\sin x"}, 2.0)
        info = self.tf(r"u=x^2,\quad u'=2x;\qquad v=\sin x,\quad v'=\cos x",
                       {"u": "x^2", "up": "2x", "v": r"\sin x", "vp": r"\cos x"}, .6, size=35)
        self.beat(.15, FadeIn(first))
        self.ready("product_example_factors")
        self.beat(.38, FadeIn(info))
        self.ready("product_example_derivatives")
        self.at(18.1)
        self.ready("product_example_result")
        first_term = self.tf(r"2x\sin x", {"up": "2x", "v": r"\sin x",},
                             -.85, x=-2.5, size=39, width=6)
        self.gather("product_example_first", first_term,
                    [(info, "up", "up"), (info, "v", "v")], 18.5, 21.4)
        second_term = self.tf(r"x^2\cos x", {"u": "x^2", "vp": r"\cos x"},
                              -.85, x=3.0, size=39, width=5)
        self.gather("product_example_second", second_term,
                    [(info, "u", "u"), (info, "vp", "vp")], 22.0, 25.0)
        left = self.tf(first_term.get_tex(), {"term": r"2x\sin x"}, -.85, x=-2.5, size=39, width=6)
        right = self.tf(second_term.get_tex(), {"term": r"x^2\cos x"}, -.85, x=3.0, size=39, width=5)
        self.remove(first_term, second_term)
        self.add(left, right)
        result = self.tf(r"f'(x)=2x\sin x+x^2\cos x",
                         {"left": r"2x\sin x", "right": r"x^2\cos x"}, -.85, size=39)
        self.gather("product_example_join_sum", result,
                    [(left, "term", "left"), (right, "term", "right")], 25.1, 27.8, retire=(left, right))
        self.beat(.84, FadeIn(self.label("每一项：一个因子的变化率 × 另一个因子的当前值", 0, -2.25, size=28)))
