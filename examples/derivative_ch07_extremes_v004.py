"""not_reviewed: explicit right-branch scope and whole-domain no-maximum proof.

All other v003 methods, mathematical states and the 322.2-second clock remain
inherited. New proof objects are cue-local; they expire at the next chapter.
Original speech/transport is unchanged. This is not independent review.
"""

from derivative_ch07_extremes_v003 import DerivativeCh07ExtremesV003
from manimlib import UpdateFromAlphaFunc
from derivative_ch07_extremes import (
    Dot, FadeIn, FadeOut, Group, ValueTracker, VGroup, linear, np,
    ACCENT, CURVE, graph_point, path, value, finite,
)


def right_comparator(x):
    x = finite(x)
    if not 1 < x < 3:
        raise ValueError("Right-branch comparison requires 1 < x < 3")
    return (x+3)/2


def open_higher_witness(x):
    x = finite(x)
    if not 0 < x < 3:
        raise ValueError("Whole-domain comparison requires 0 < x < 3")
    return 2 if x <= 1 else right_comparator(x)


class DerivativeCh07ExtremesV004(DerivativeCh07ExtremesV003):
    def open_interval(self, cue):
        self.begin_chapter(cue)
        graph = self.graph(closed=False)
        left = path([graph_point(t, value(t)) for t in np.linspace(0, 1, 61)])
        right = path([graph_point(t, value(t)) for t in np.linspace(1, 3, 121)])
        # Split the same 181-point curve at its existing vertex. Both endpoint
        # rings remain above the curves in the original graph's draw order.
        graph.submobjects[1] = VGroup(left, right)
        self.beat(.12, FadeIn(graph),
                  FadeIn(self.put(r"f(x)=(x-1)^2,\quad x\in(0,3)", 3.5, 2.15, size=32, width=5.7)),
                  FadeIn(self.label("空心端点：位置不属于区间", 3.5, 1.25, size=27, color=ACCENT, width=5.5)),
                  FadeIn(Dot(graph_point(1, 0), color=CURVE, radius=.085)),
                  FadeIn(self.put(r"\min f=0\quad(x=1)", 3.5, .3, size=35, color=CURVE, width=5.5)))
        self.mark("open_minimum_retained_ready")
        self.focus_begin("open_minimum_retained")
        self.beat(.35)
        self.focus_end("open_minimum_retained")

        scope = self.label("递增右支：1 < x < 3", -3, 2.60, size=29, color=ACCENT, width=5.8)
        chosen = self.put(r"y=(x+3)/2,\quad x<y<3", -3, -2.60, size=29, width=5.7)
        increase = self.put(r"f(y)-f(x)=(y-x)(x+y-2)>0", 3.5, -1.55, size=27, width=5.7)
        self.beat(.38, UpdateFromAlphaFunc(graph, lambda _, a: left.set_stroke(opacity=1-.68*a)),
                  FadeIn(scope), FadeIn(chosen), FadeIn(increase))
        self.mark("open_right_scope_ready")
        self.sample("open_comparison_scope", phase="right", domain=[1, 3], open_ends=True,
                    quantified_statement="For every 1<x<3 choose y=(x+3)/2; x<y<3 and f(y)>f(x)")

        x = ValueTracker(2.2)
        point = Dot(graph_point(2.2, value(2.2)), color=ACCENT, radius=.075)
        number = self.number(value(2.2), decimals=3, size=33, color=ACCENT).move_to([4.8, -.65, 0])
        self.beat(.40, FadeIn(point), FadeIn(self.put("f(x)=", 2.2, -.65, size=32)), FadeIn(number))
        driver = Group()

        def update(_):
            t = x.get_value()
            point.move_to(graph_point(t, value(t)))
            number.set_value(value(t))
            self.sample("open_approach", x=t, value=value(t), gap=4-value(t), endpoint_included=False)

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.mark("open_approach_start")
        self.focus_begin("open_approach")
        self.beat(.67, x.animate.set_value(2.99), rate_func=linear)
        self.focus_end("open_approach")
        driver.clear_updaters()

        self.beat(.70, FadeOut(scope), FadeOut(chosen), FadeOut(increase))
        self.beat(.74, UpdateFromAlphaFunc(graph, lambda _, a: left.set_stroke(opacity=.32+.68*a)),
                  FadeIn(self.label("全域比较：左段与右支", -3, 2.60, size=29, width=5.8)),
                  FadeIn(self.put(r"0<x\le1:\quad f(x)<1=f(2)", -3, -2.48, size=26, width=5.8)),
                  FadeIn(self.put(r"1<x<3:\quad x<y<3,\ f(x)<f(y)", -3, -2.88, size=24, width=5.8)),
                  FadeIn(Dot(graph_point(2, 1), color=ACCENT, radius=.075)),
                  FadeIn(self.put(r"0\le f(x)<4\quad(0<x<3)", 3.5, -1.23, size=28, width=5.7)),
                  FadeIn(self.put(r"x\to3^-:\ f(x)\to4", 3.5, -1.85, size=30, color=ACCENT, width=5.7)),
                  FadeIn(self.label("上确界为 4，无最大值；最小值仍为 0", 3.5, -2.45, size=25, width=5.8)))
        self.mark("open_global_coverage_ready")
        self.mark("unattained_supremum_ready")
        self.sample("open_comparison_scope", phase="whole", domain=[0, 3], open_ends=True,
                    quantified_statement="Every 0<x<=1 is beaten by y=2; every 1<x<3 is beaten by y=(x+3)/2",
                    supremum=4, minimum=0, maximum=None)
        self.focus_begin("unattained_supremum")
        self.end_chapter()
