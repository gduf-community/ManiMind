"""08 closing-condition/object repair; all other v003 methods are inherited.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main/native tests/
independent reviewers. Lifecycle: one v004 construct. Source, clock, wording,
model or input changes invalidate evidence. No production/review authority.
Original lesson author: 01a199e9-7432-7052-96f7-6bd6eb2e63bb.
"""

import math

from derivative_ch08_optimization_v003 import DerivativeCh08OptimizationV003
from derivative_ch08_optimization import dimensions, feasible, volume
from derivative_chapter_shared import ACCENT, CURVE, RATE
from manimlib import FadeIn, FadeOut, Group, ValueTracker, linear


AUTHOR_AGENT = "01a19acd-e149-74d0-8a5d-975a3adf45f4"


class DerivativeCh08OptimizationV004(DerivativeCh08OptimizationV003):
    def closing(self, cue):
        self.begin_chapter(cue)
        faces = self.panels(2, math.pi/2)
        original_condition = self.label("原条件：无额外高度下限", 3.5, 2.65, size=26, width=5.7)
        original_result = self.put(r"x=2\ \mathrm{cm},\quad V=128\ \mathrm{cm}^3", 3.5, 2, size=34, color=CURVE, width=5.7)
        original_dimensions = self.put(r"8\times8\times2\ \mathrm{cm}", 3.5, 1.1, size=35, width=5.7)
        self.beat(.13, FadeIn(faces), FadeIn(original_condition), FadeIn(original_result), FadeIn(original_dimensions),
                  FadeIn(self.label("尺寸 → 同一变量 → 目标与可行域", 3.5, -.1, size=27, width=5.7)),
                  FadeIn(self.label("变化率 → 单调性 → 全范围比较", 3.5, -1, size=27, width=5.7)))
        self.sample("closing_binding", x_cm=2, min_height_cm=0, dimensions_cm=dimensions(2), volume_cm3=volume(2), feasible=True)
        self.mark("chapter_chain_ready")
        self.focus_begin("chapter_chain")
        self.beat(.70)
        self.focus_end("chapter_chain")
        self.beat(.78, FadeIn(self.label("约束改变，沿同一模型重新判断", 3.5, -2.25, size=28, color=ACCENT, width=5.7)))
        self.mark("feasibility_transfer_ready")
        self.focus_begin("feasibility_transfer")

        rejected = self.label("旧解 x = 2：高度不足，排除", 3.5, 1.1, size=27, color=RATE, width=5.7)
        self.beat(.80, FadeOut(original_condition), FadeOut(original_result), FadeOut(original_dimensions),
                  FadeIn(self.label("当前条件：盒高至少 3 cm", 3.5, 2.65, size=26, width=5.7)),
                  FadeIn(self.put(r"3\leq x<6\quad(\mathrm{cm})", 3.5, 2, size=34, color=ACCENT, width=5.7)),
                  FadeIn(rejected))
        self.mark("closing_old_solution_excluded")
        x = ValueTracker(2)
        driver = Group()

        def update(_):
            size = x.get_value()
            faces.become(self.panels(size, math.pi/2))
            self.sample("closing_binding", x_cm=size, min_height_cm=3, dimensions_cm=dimensions(size),
                        volume_cm3=volume(size), feasible=feasible(size, 3))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        # The old candidate has been rejected before the box changes identity.
        self.beat(.84, x.animate.set_value(3), rate_func=linear)
        self.mark("closing_current_box_ready")
        self.beat(.86, FadeOut(rejected),
                  FadeIn(self.label("旧解 x = 2：高度不足，排除", -3.3, -2.3, size=26, color=RATE, width=5.5)),
                  FadeIn(self.put(r"x=3\ \mathrm{cm},\quad V=108\ \mathrm{cm}^3", 3.5, 1.15, size=32, color=CURVE, width=5.7)),
                  FadeIn(self.put(r"6\times6\times3\ \mathrm{cm}", 3.5, .4, size=31, width=5.7)))
        self.mark("closing_current_optimum_ready")
        self.end_chapter()
        driver.clear_updaters()
