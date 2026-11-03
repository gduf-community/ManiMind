"""CH06-B1 proof-only revision over the immutable v003 presentation.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main/native tests/
independent reviewers. Lifecycle: one v004 construct; bound proof, source,
clock or inputs invalidate evidence. Original author:
01a199e9-7432-7052-96f7-6bd6eb2e63bb. No media or review authority.
"""

from derivative_ch06_extrema_v003 import DerivativeCh06ExtremaV003
from derivative_ch06_extrema import path
from derivative_chapter_shared import ACCENT, CURVE, MUTED, RATE
from manimind.components.formula_motion import SemanticFormula, matching_transform
from manimlib import Dot, FadeIn, FadeOut, Group, Line, ShowCreation, ValueTracker, linear


AUTHOR_AGENT = "01a19acd-e149-74d0-8a5d-975a3adf45f4"
VALUES = {"near": "f(a+h)", "center": "f(a)"}


class DerivativeCh06ExtremaV004(DerivativeCh06ExtremaV003):
    def semantic(self, latex, tokens, x, y, size=32, width=5.8):
        colors = {key: color for key, color in (("near", CURVE), ("center", ACCENT), ("bound", RATE)) if key in tokens}
        result = SemanticFormula(latex, tokens=tokens, colors=colors, font_size=size)
        if result.get_width() > width:
            result.set_width(width)
        return result.move_to([x, y, 0])

    def reason_transfer(self, source, target, end, *, stage, pairs, copy=False):
        moving = source.copy() if copy else source
        driver = Group()

        def sample(_):
            self.sample("proof_transfer", stage=stage, source=source.get_tex(), target=target.get_tex(),
                copy_preserves_source=copy, pairs=list(pairs),
                moving_centers={key: moving.tag(key).get_center().tolist() for key, _ in pairs},
                target_centers={key: target.tag(key).get_center().tolist() for _, key in pairs})

        sample(driver)
        driver.add_updater(sample)
        self.add(driver)
        self.beat(end, matching_transform(moving, target, pairs=pairs, unmatched_in_place=True, path_arc=0))
        driver.clear_updaters()
        self.sample("proof_transfer_complete", stage=stage, source=source.get_tex(), target=target.get_tex(), pairs=list(pairs))

    def necessary(self, cue):
        self.begin_chapter(cue)
        condition = self.label("可导的内点 a", 0, 2.55, size=31, color=ACCENT)
        implication = Group(self.label("a 是局部极值点", -2.7, 1.85, size=29, width=5),
                            self.put(r"\Longrightarrow\quad f'(a)=0", 2.65, 1.85, size=37, width=5))
        self.beat(.13, FadeIn(condition), FadeIn(implication))
        self.mark("conditional_necessity_ready")
        self.focus_begin("conditional_necessity")

        axis = Line([-3, .65, 0], [3, .65, 0], color=MUTED, stroke_width=2)
        ticks = Group(*(Line([x, .52, 0], [x, .78, 0], color=ACCENT) for x in (-3, 0, 3)))
        labels = Group(self.put(r"a-\delta", -3, .12, size=29), self.put("a", 0, .12, size=29),
                       self.put(r"a+\delta", 3, .12, size=29),
                       self.put(r"(a-\delta,a+\delta)\subset\mathrm{Dom}(f)", 0, -.65, size=31, width=11.8),
                       self.put(r"0<|h|<\delta", 0, -1.35, size=31, color=ACCENT))
        approach = ValueTracker(.75)
        probes = Group(Dot([-2.25, .65, 0], color=CURVE, radius=.065),
                       Dot([2.25, .65, 0], color=CURVE, radius=.065))
        self.beat(.18, ShowCreation(axis), FadeIn(ticks), FadeIn(labels), FadeIn(probes))
        self.mark("interior_neighborhood_ready")
        driver = Group()

        def update(_):
            ratio = approach.get_value()
            probes[0].move_to([-3*ratio, .65, 0])
            probes[1].move_to([3*ratio, .65, 0])
            self.sample("proof_neighborhood", abs_h_over_delta=ratio,
                        left=probes[0].get_center().tolist(), right=probes[1].get_center().tolist())

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.beat(.22, approach.animate.set_value(.16), rate_func=linear)
        driver.clear_updaters()
        finite_derivative = self.label("可导：左右得到同一个有限导数", 0, -2.15, size=28)
        self.beat(.26, FadeIn(finite_derivative))
        self.beat(.29)
        self.focus_end("conditional_necessity")

        maximum = self.label("局部极大：取足够小的邻域", -2.7, 1.08, size=26, width=6)
        bound = self.put(r"0<|h|<\delta", 3.5, 1.08, size=29, color=ACCENT, width=4.5)
        comparison = self.semantic(r"f(a+h)\leq f(a)", VALUES, 0, .35, size=34, width=11.8)
        self.beat(.32, FadeOut(axis), FadeOut(ticks), FadeOut(labels), FadeOut(probes), FadeOut(finite_derivative),
                  FadeIn(maximum), FadeIn(bound), FadeIn(comparison))
        self.focus_begin("one_sided_quotients")
        self.mark("local_comparison_ready")
        numerator = self.semantic(r"f(a+h)-f(a)\leq0", {**VALUES, "bound": r"\leq0"}, 0, -.45, size=34, width=11.8)
        self.reason_transfer(comparison, numerator, .38, stage="comparison_to_numerator",
                             pairs=[("near", "near"), ("center", "center")], copy=True)
        self.mark("common_numerator_ready")

        left_sign = self.put("h<0", -3, -.95, size=30, color=ACCENT)
        right_sign = self.put("h>0", 3, -.95, size=30, color=ACCENT)
        left = self.semantic(r"\frac{f(a+h)-f(a)}h\geq0", {**VALUES, "bound": r"\geq0"}, -3, -1.75)
        right = self.semantic(r"\frac{f(a+h)-f(a)}h\leq0", {**VALUES, "bound": r"\leq0"}, 3, -1.75)
        self.beat(.40, FadeIn(left_sign))
        self.reason_transfer(numerator, left, .44, stage="negative_h_quotient",
                             pairs=[("near", "near"), ("center", "center")], copy=True)
        self.mark("left_quotient_ready")
        self.beat(.46, FadeIn(right_sign))
        self.reason_transfer(numerator, right, .50, stage="positive_h_quotient",
                             pairs=[("near", "near"), ("center", "center")], copy=True)
        self.mark("one_sided_quotients_ready")
        self.beat(.55)
        self.focus_end("one_sided_quotients")
        self.beat(.56, FadeOut(comparison), FadeOut(numerator), FadeOut(left_sign), FadeOut(right_sign))
        self.focus_begin("common_zero_necessity")

        left_limit = self.semantic(r"L=\lim_{h\to0^-}\frac{f(a+h)-f(a)}h\geq0",
            {**VALUES, "bound": r"\geq0"}, -3.1, -.25, size=30, width=5.9)
        right_limit = self.semantic(r"R=\lim_{h\to0^+}\frac{f(a+h)-f(a)}h\leq0",
            {**VALUES, "bound": r"\leq0"}, 3.1, -.25, size=30, width=5.9)
        pairs = [(key, key) for key in ("near", "center", "bound")]
        limit_driver = Group()

        def sample_limits(_):
            self.sample("proof_limit_transfer",
                left={key: left.tag(key).get_center().tolist() for key, _ in pairs},
                right={key: right.tag(key).get_center().tolist() for key, _ in pairs},
                target_left={key: left_limit.tag(key).get_center().tolist() for key, _ in pairs},
                target_right={key: right_limit.tag(key).get_center().tolist() for key, _ in pairs})

        sample_limits(limit_driver)
        limit_driver.add_updater(sample_limits)
        self.add(limit_driver)
        # Columns stay separate: same values/inequality rise into each limit.
        self.beat(.58, matching_transform(left, left_limit, pairs=pairs, unmatched_in_place=True),
                  matching_transform(right, right_limit, pairs=pairs, unmatched_in_place=True))
        limit_driver.clear_updaters()
        self.sample("proof_limits_complete", left=left_limit.get_tex(), right=right_limit.get_tex(), pairs=pairs)
        self.mark("one_sided_limits_ready")
        equality = self.put(r"L=f'(a)=R", .5, -1.12, size=37)
        equal_reason = self.label("可导", -2.6, -1.12, size=28, color=ACCENT, width=1.7)
        self.beat(.61, FadeIn(equality), FadeIn(equal_reason))
        self.mark("equal_derivative_ready")
        common_tokens = {"derivative": "f'(a)", "zero": "0"}
        lower = self.semantic(r"f'(a)\geq0", common_tokens, -3, -2.0, size=35)
        upper = self.semantic(r"f'(a)\leq0", common_tokens, 3, -2.0, size=35)
        self.beat(.64, FadeIn(lower))
        self.beat(.67, FadeIn(upper))
        zero = self.put(r"\Longrightarrow\quad f'(a)=0", 0, -2.75, size=35, color=RATE, width=11.8)
        self.beat(.70, FadeIn(zero))
        self.mark("common_zero_proved")

        minimum = self.label("局部极小：不等号反向", -2.7, 1.08, size=26, width=6)
        minimum_bound = self.put(r"0<|h|<\delta:\ f(a+h)-f(a)\geq0", 0, .65, size=28, width=11.8)
        left_min = self.semantic(r"L=\lim_{h\to0^-}\frac{f(a+h)-f(a)}h\leq0",
            {**VALUES, "bound": r"\leq0"}, -3.1, -.25, size=30, width=5.9)
        right_min = self.semantic(r"R=\lim_{h\to0^+}\frac{f(a+h)-f(a)}h\geq0",
            {**VALUES, "bound": r"\geq0"}, 3.1, -.25, size=30, width=5.9)
        lower_min = self.semantic(r"f'(a)\leq0", common_tokens, -3, -2.0, size=35)
        upper_min = self.semantic(r"f'(a)\geq0", common_tokens, 3, -2.0, size=35)
        self.beat(.71, FadeOut(maximum), FadeOut(bound), FadeIn(minimum))
        self.beat(.73, FadeIn(minimum_bound),
                  matching_transform(left_limit, left_min, pairs=[("near", "near"), ("center", "center")], unmatched_in_place=True),
                  matching_transform(right_limit, right_min, pairs=[("near", "near"), ("center", "center")], unmatched_in_place=True),
                  matching_transform(lower, lower_min, pairs=[("derivative", "derivative"), ("zero", "zero")], unmatched_in_place=True),
                  matching_transform(upper, upper_min, pairs=[("derivative", "derivative"), ("zero", "zero")], unmatched_in_place=True))
        self.mark("minimum_same_zero_ready")
        self.beat(.74)
        self.focus_end("common_zero_necessity")
        self.beat(.77, *(FadeOut(obj) for obj in (minimum, minimum_bound, left_min, right_min, equality, equal_reason, lower_min, upper_min, zero)))
        cusp = path([[-2.4, -1.3, 0], [-1.2, -2.5, 0], [0, -1.3, 0]], ACCENT)
        self.beat(.79, ShowCreation(cusp), FadeIn(self.put(r"y=|x|", -4, -1.9, size=35, width=2.3)),
                  FadeIn(self.label("0 是尖点极小，导数不存在", 3.1, -1.8, size=28, width=5.7)),
                  FadeIn(self.label("这说明为什么要保留“可导内点”", 3.1, -2.5, size=26, color=MUTED, width=5.7)))
        self.mark("cusp_condition_ready")
        self.focus_begin("cusp_condition")
        self.end_chapter()
