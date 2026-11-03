"""Chapter 04 intact-WAV retiming candidate, not an independent review.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4. Consumers: main renderer,
native tests and independent reviewers. Lifetime: one v003 execution;
source, timings, plan or geometry changes invalidate its derived evidence.
Original author: 01a199e9-73ab-7700-8a9f-cd7b5541b0ad.
"""

from derivative_ch04_chain import (
    DerivativeChainLesson, CUE_IDS, X_COLOR, U_COLOR, Y_COLOR,
    inner, composite, chain_ratios,
)
from manimlib import Arrow, FadeIn, FadeOut, Group, ValueTracker, linear
from derivative_chapter_shared import ACCENT


AUTHOR_AGENT = "01a19acd-e149-74d0-8a5d-975a3adf45f4"


class DerivativeChainLessonV003(DerivativeChainLesson):
    def construct(self):
        self.motion_samples = []
        if tuple(cue["id"] for cue in self.cues) != CUE_IDS:
            raise ValueError("Chapter 04 intact speech cue order changed")
        for cue in self.cues:
            self.begin_chapter(cue)
            getattr(self, cue["id"].replace("-", "_"))()
            self.end_chapter()

    def beat(self, fraction, *animations, **kwargs):
        key = f"{fraction:.2f}"
        # Every endpoint is explicit; missing keys must not revert to old ratios.
        end = self._cue["stage_times"][key]
        if animations:
            start = self._cue["animation_starts"].get(key, end - .4)
            absolute = self._cue["start"] + start
            if round(absolute * self.camera.fps) > round(self.get_time() * self.camera.fps):
                self.until(absolute)
        super().beat(fraction, *animations, **kwargs)

    def one_change(self):
        x, u, y = ValueTracker(1), ValueTracker(2), ValueTracker(8)
        trackers = (x, u, y)
        positions, colors = (-4.2, 0, 4.2), (X_COLOR, U_COLOR, Y_COLOR)
        numbers = [self.number(t.get_value(), size=34 if index == 2 else 40,
                               color=color, decimals=6 if index == 2 else 3).move_to([p, .55, 0])
                   for index, (t, p, color) in enumerate(zip(trackers, positions, colors))]
        group = Group(*(self.put(name, p, 1.5, color=color) for name, p, color in
                        zip(("x", "u=x^2+1", "y=u^3"), positions, colors)), *numbers,
                      Arrow([-3, .55, 0], [-1.2, .55, 0], buff=.1),
                      Arrow([1.2, .55, 0], [3, .55, 0], buff=.1))
        self.beat(.12, FadeIn(group))
        self.mark("change_base_ready")
        phase = {"name": "input"}
        driver = Group()

        def update(_):
            for number, tracker in zip(numbers, trackers):
                number.set_value(tracker.get_value())
            self.sample("chain_transfer", phase=phase["name"], x=float(x.get_value()),
                        u=float(u.get_value()), y=float(y.get_value()))

        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("input_change")
        self.beat(.28, x.animate.set_value(1.1), rate_func=linear)
        self.mark("input_change_complete")
        self.beat(.34, FadeIn(self.put(r"\Delta x=0.1", -4.2, -.45, size=32, color=X_COLOR)))
        self.beat(.37)
        self.focus_end("input_change")
        self.beat(.39)
        phase["name"] = "inner"
        self.focus_begin("inner_change")
        self.beat(.51, u.animate.set_value(inner(1.1)), rate_func=linear)
        self.mark("inner_change_complete")
        self.beat(.57, FadeIn(self.put(r"\Delta u=0.21", 0, -.45, size=32, color=U_COLOR)))
        self.beat(.60)
        self.focus_end("inner_change")
        self.beat(.63)
        phase["name"] = "outer"
        self.focus_begin("outer_change")
        self.beat(.74, y.animate.set_value(composite(1.1)), rate_func=linear)
        self.mark("outer_change_complete")
        self.beat(.77)
        self.focus_end("outer_change")
        driver.clear_updaters()
        self.beat(.80, FadeIn(self.put(r"\Delta y=2.793861", 4.2, -.45, size=30, color=Y_COLOR)))
        self.beat(.86, FadeIn(self.label("同一次输入改变，经过两级传到输出", 0, -1.6, size=32)))
        self.focus_begin("transfer_complete")
        self.mark("chain_transfer_ready")

    def ratios(self):
        identity = self.semantic(r"\frac{\Delta y}{\Delta x}=\frac{\Delta y}{\Delta u}\cdot\frac{\Delta u}{\Delta x}",
                                 {"outer": r"\frac{\Delta y}{\Delta u}",
                                  "inner": r"\frac{\Delta u}{\Delta x}"}, y=1.9,
                                 colors={"outer": Y_COLOR, "inner": U_COLOR})
        self.beat(.14, FadeIn(identity), FadeIn(self.put(r"x=1,\quad 0<|h|<1,\quad \Delta x=h", 0, 2.7, size=30)))
        self.mark("ratio_identity_ready")
        self.focus_begin("ratio_identity")
        self.beat(.30, FadeIn(self.put(r"\Delta u=(1+h)^2-1=h(2+h)\ne0", 0, .75, size=37, color=U_COLOR)))
        self.mark("ratio_nonzero_ready")
        self.focus_begin("nonzero_increment")
        labels = Group(self.label("输入增量 h", -4.8, -.15, size=24),
                       self.label("内层比值", -1.6, -.15, size=24, color=U_COLOR),
                       self.label("外层比值", 1.6, -.15, size=24, color=Y_COLOR),
                       self.label("总比值", 4.8, -.15, size=24))
        self.beat(.38, FadeIn(labels))
        self.focus_begin("ratio_limit")
        for index, h in enumerate((.1, .01, .001)):
            rates = chain_ratios(1, h)
            row = Group(*(self.number(v, size=29, decimals=5).move_to([p, -.75-index*.58, 0])
                          for p, v in zip((-4.8, -1.6, 1.6, 4.8),
                                          (h, rates["inner_ratio"], rates["outer_ratio"], rates["total_ratio"]))))
            self.beat(.48+index*.15, FadeIn(row))
            self.mark(f"ratio_row_{index+1}_ready")
            self.sample("ratio_row", h=h, **rates)
        self.beat(.90, FadeIn(self.put(r"2\times12=24", 0, -2.65, color=ACCENT)))
        self.mark("ratio_limit_ready")

    def practice(self):
        # Retain the original practice unmodified, then support its domain clause.
        super().practice()
        bottom = [obj for obj in self.mobjects if obj.get_center()[1] < -1]
        self.beat(.92, *(FadeOut(obj) for obj in bottom))
        root = self.put(r"\sqrt{2x+1}:\quad x\ge-\frac12;\quad y'=\frac1{\sqrt{2x+1}},\ x>-\frac12",
                        0, -1.45, size=29, width=11.8)
        self.beat(.94, FadeIn(root))
        self.mark("chain_root_domain_ready")
        self.focus_begin("chain_domain_examples")
        log = self.put(r"\ln(2x+1):\quad y'=\frac2{2x+1},\quad x>-\frac12",
                       0, -2.35, size=30, width=11.8)
        self.beat(.96, FadeIn(log))
        self.mark("chain_log_domain_ready")
