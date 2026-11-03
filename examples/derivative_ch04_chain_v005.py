"""Keep v004 scope headings; reveal the settled output increment in time.

Writer: 019eaf8b-9151-75e2-9db4-5ff834335577. Consumers: renderer/reviewers.
Lifetime: this exact plan and scene; any source/time/media change invalidates
its evidence. All original tracker motion and full audio timings are retained.
"""

from derivative_ch04_chain_v004 import DerivativeChainLessonV004, SCOPE_HEADINGS
from derivative_ch04_chain import X_COLOR, U_COLOR, Y_COLOR, inner, composite
from manimlib import Arrow, FadeIn, Group, ValueTracker, linear


AUTHOR_AGENT = "019eaf8b-9151-75e2-9db4-5ff834335577"


class DerivativeChainLessonV005(DerivativeChainLessonV004):
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
        self.beat(.76, FadeIn(self.put(r"\Delta y=2.793861", 4.2, -.45, size=30, color=Y_COLOR)))
        self.beat(.77)
        self.focus_end("outer_change")
        driver.clear_updaters()
        self.beat(.80)
        self.beat(.86, FadeIn(self.label("同一次输入改变，经过两级传到输出", 0, -1.6, size=32)))
        self.focus_begin("transfer_complete")
        self.mark("chain_transfer_ready")
