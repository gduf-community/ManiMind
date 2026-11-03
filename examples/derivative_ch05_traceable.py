"""CH05 narrow bridges over v004. No review or release authority.

Writer: 01a19f6b-174f-7431-a0fd-2adf59301a9e. Consumers: renderer, native
tests and independent reviewers. Local glyph roles live for one construct;
source, timing or geometry changes invalidate the motion journal.
"""
import numpy as np
from derivative_ch05_monotonicity_v004 import DerivativeMonotonicityLessonV004
from derivative_ch05_monotonicity import function, plot_point, secant_witness
from derivative_chapter_shared import ACCENT, CURVE, INK, MUTED, RATE
from manimind.components.formula_motion import SemanticFormula
from manimlib import Dot, FadeIn, FadeOut, Group, Line, Transform, ValueTracker, VGroup, linear

AUTHOR_AGENT = "01a19f6b-174f-7431-a0fd-2adf59301a9e"


class DerivativeCh05Traceable(DerivativeMonotonicityLessonV004):
    def scaffold(self, formula, keys):
        for key in keys:
            formula.tag(key).set_opacity(0)
        self.add(formula)
        return formula

    def transfer_roles(self, origins, target, end, stage):
        self.until(self._cue["start"]+self._cue["animation_starts"][f"{end:.2f}"])
        if any(float(g.get_opacity()) < .95 for part,_ in origins for g in part.family_members_with_points()):
            raise ValueError("A role transfer must start from a currently visible source")
        moving = [part.copy() for part, _ in origins]
        destinations = [target.tag(key).copy().set_opacity(1) for _, key in origins]
        driver = Group()

        def sample(_):
            self.sample("traceable_roles", stage=stage, moving=[m.get_center().tolist() for m in moving],
                        targets=[m.get_center().tolist() for m in destinations])

        sample(driver)
        driver.add_updater(sample)
        self.add(driver, *moving)
        self.beat(end, *(Transform(m, t, path_arc=0) for m,t in zip(moving,destinations)))
        driver.clear_updaters()
        self.remove(driver, *moving)
        for _, key in origins:
            target.tag(key).set_opacity(1)
        self.mark(stage+"_ready")

    def signs(self):
        self.beat(.12)
        factor = self.semantic(r"f'(x)=3(x-1)(x+1)", {"positive": "x-1", "negative": "x+1"}, y=2.2,
            colors={"positive":ACCENT,"negative":ACCENT})
        self.beat(.15, FadeIn(factor))
        self.focus_begin("sign_boundaries")
        negative = SemanticFormula("x+1=0",tokens={"factor":"x+1","zero":"0"},isolate=["x"],font_size=32).move_to([-3,1.4,0])
        positive = SemanticFormula("x-1=0",tokens={"factor":"x-1","zero":"0"},isolate=["x"],font_size=32).move_to([3,1.4,0])
        self.scaffold(negative,["factor"])
        self.transfer_roles([(factor.tag("negative"),"factor")],negative,.20,"negative_factor_to_zero")
        self.scaffold(positive,["factor"])
        self.transfer_roles([(factor.tag("positive"),"factor")],positive,.22,"positive_factor_to_zero")
        neg_root = self.semantic("x=-1",{"x":"x","position":"-1"},x=-3,y=.72,size=32)
        pos_root = self.semantic("x=1",{"x":"x","position":"1"},x=3,y=.72,size=32)
        self.scaffold(neg_root,["x","position"])
        self.scaffold(pos_root,["x","position"])
        self.transfer_roles([(negative.get_parts_by_tex("x")[0],"x")],neg_root,.24,"solve_negative_root")
        self.transfer_roles([(positive.get_parts_by_tex("x")[0],"x")],pos_root,.26,"solve_positive_root")
        self.until(self._cue["start"]+self._cue["animation_starts"]["0.27"])
        self.beat(.27, FadeIn(neg_root.tag("position").set_opacity(1)),FadeIn(pos_root.tag("position").set_opacity(1)))
        self.mark("derivative_roots_ready")
        axis = Line([-5.9,0,0],[5.9,0,0],color=MUTED)
        ticks = Group(Line([-2,-.12,0],[-2,.12,0],color=ACCENT),Line([2,-.12,0],[2,.12,0],color=ACCENT))
        tick_neg = self.semantic("-1",{"position":"-1"},x=-2,y=-.35,size=29)
        tick_pos = self.semantic("1",{"position":"1"},x=2,y=-.35,size=29)
        self.scaffold(tick_neg,["position"])
        self.scaffold(tick_pos,["position"])
        self.beat(.30, FadeIn(axis),FadeIn(ticks))
        self.transfer_roles([(neg_root.tag("position"),"position")],tick_neg,.34,"negative_root_to_boundary")
        self.transfer_roles([(pos_root.tag("position"),"position")],tick_pos,.38,"positive_root_to_boundary")
        for p,latex,keys,focus,finish,trend_end,trend,region in (
            (-4,r"3\cdot(-)\cdot(-)>0",{"first":("-",0),"second":("-",1)},"left_sign",.51,.55,"增","x<-1"),
            (0,r"3\cdot(-)\cdot(+)<0",{"first":"-","second":"+"},"middle_sign",.65,.69,"减","-1<x<1"),
            (4,r"3\cdot(+)\cdot(+)>0",{"first":("+",0),"second":("+",1)},"right_sign",.79,.83,"增","x>1")):
            self.focus_begin(focus)
            self.add(self.put(region,p,-.82,size=27,width=3.5))
            product = self.semantic(latex,keys,x=p,y=-1.35,size=29,width=3.6)
            self.scaffold(product,keys)
            self.transfer_roles([(factor.tag("positive"),"first"),(factor.tag("negative"),"second")],
                product,finish,focus+"_factors")
            self.beat(trend_end,FadeIn(self.label(trend,p,-2.0,size=33,color=CURVE)))
            self.mark(focus+"_ready")
        self.focus_begin("whole_sign_chart")
        self.beat(.90, FadeIn(self.put(r"(-\infty,-1):+\qquad(-1,1):-\qquad(1,+\infty):+",0,-2.75,size=30)))
        self.mark("sign_chart_complete")

    def interval(self):
        heading_objects=tuple(self.mobjects)
        x=ValueTracker(-1.85)
        driver=self.plots(x,.10,.17)
        a=-2.
        fixed=Dot(plot_point(a,function(a)),radius=.09,fill_color=INK)
        secant=Line(plot_point(a,function(a)),plot_point(x.get_value(),function(x.get_value())),color=INK,stroke_width=2)
        secant.add_updater(lambda line:line.put_start_and_end_on(np.array(plot_point(a,function(a))),np.array(plot_point(x.get_value(),function(x.get_value())))))
        self.beat(.24,FadeIn(fixed),FadeIn(secant),FadeIn(self.label("取区间内任意 a < b",0,-2.75,size=29)))
        self.mark("interval_pair_ready")
        self.focus_begin("interval_pair_motion")
        self.beat(.43,x.animate.set_value(-1.15),rate_func=linear)
        self.focus_end("interval_pair_motion")
        secant.clear_updaters()
        self.mark("interval_pair_complete")
        self.focus_begin("interval_pair_result")
        self.beat(.46)
        self.focus_end("interval_pair_result")
        b=x.get_value()
        self.add(Dot(plot_point(b,function(b)),radius=.09,fill_color=INK))
        self.focus_begin("secant_witness_motion")
        self.beat(.54,x.animate.set_value(secant_witness(a,b)),rate_func=linear)
        self.focus_end("secant_witness_motion")
        driver.clear_updaters()
        self.mark("secant_witness_ready")
        self.focus_begin("secant_witness_result")
        c=x.get_value()
        fa=self.semantic("f(a)",{"value":"f(a)"},x=plot_point(a,function(a))[0]-.25,y=plot_point(a,function(a))[1]-.3,size=25)
        fb=self.semantic("f(b)",{"value":"f(b)"},x=plot_point(b,function(b))[0]+.4,y=plot_point(b,function(b))[1]+.3,size=25)
        dc=self.semantic("f'(c)",{"slope":"f'(c)"},x=plot_point(c,function(c))[0],y=2.6,size=25,colors={"slope":RATE})
        apos=self.semantic("a",{"position":"a"},x=plot_point(a,0)[0],y=.72,size=24)
        bpos=self.semantic("b",{"position":"b"},x=plot_point(b,0)[0],y=.98,size=24)
        cpos=self.semantic("c",{"position":"c"},x=plot_point(c,0)[0],y=1.2,size=24)
        self.add(fa,fb,dc,apos,bpos,cpos)
        self.beat(.58)
        self.focus_end("secant_witness_result")
        self.focus_begin("interval_theorem")
        world=Group(*(obj for obj in self.mobjects if all(obj is not old for old in heading_objects)))
        theorem=self.label("整个开区间 I 内可导，且处处 f'(x)>0",3.35,2.55,size=25,width=6.0)
        between=self.put(r"a,b\in I,\quad a<c<b",3.35,1.95,size=29,width=5.8)
        self.beat(.62,world.animate.scale(.54).move_to([-3.55,.25,0]),FadeIn(theorem),FadeIn(between))
        self.mark("interval_condition_ready")
        quotient=self.semantic(r"\frac{f(b)-f(a)}{b-a}=f'(c)",
            {"fb":"f(b)","fa":"f(a)","b":("b",1),"a":("a",1),"dc":"f'(c)"},x=3.35,y=.95,size=33,width=5.8)
        self.scaffold(quotient,quotient.semantic_ids)
        for source,key,end in ((fb.tag("value"),"fb",.64),(fa.tag("value"),"fa",.65),
                               (bpos.tag("position"),"b",.66),(apos.tag("position"),"a",.67),(dc.tag("slope"),"dc",.68)):
            self.transfer_roles([(source,key)],quotient,end,"witness_to_"+key)
        explanation=self.label("中值定理：连线斜率 = 某处切线斜率",3.35,.1,size=23,width=5.9)
        self.add(explanation)
        product=self.semantic(r"f(b)-f(a)=f'(c)(b-a)",
            {"fb":"f(b)","fa":"f(a)","dc":"f'(c)","b":("b",1),"a":("a",1)},x=3.35,y=-.7,size=31,width=5.8)
        self.scaffold(product,product.semantic_ids)
        self.transfer_roles([(quotient.tag("fb"),"fb"),(quotient.tag("fa"),"fa")],product,.70,"difference_to_product")
        self.transfer_roles([(quotient.tag("dc"),"dc")],product,.71,"slope_to_product")
        self.transfer_roles([(quotient.tag("b"),"b"),(quotient.tag("a"),"a")],product,.72,"positive_delta_to_product")
        self.beat(.73,FadeIn(self.put(r"f'(c)>0,\quad b-a>0",3.35,-1.35,size=28,color=RATE,width=5.8)))
        positive=self.semantic(r"f(b)-f(a)>0",{"fb":"f(b)","fa":"f(a)"},x=3.35,y=-2.0,size=31,width=5.8)
        self.scaffold(positive,["fb","fa"])
        self.transfer_roles([(product.tag("fb"),"fb"),(product.tag("fa"),"fa")],positive,.74,"positive_product_to_difference")
        order=self.semantic(r"a<b\ \Longrightarrow\ f(a)<f(b)",{"fa":"f(a)","fb":"f(b)"},x=3.35,y=-2.7,size=31,width=6)
        self.scaffold(order,["fa","fb"])
        self.transfer_roles([(positive.tag("fa"),"fa")],order,.75,"difference_to_left_value")
        self.transfer_roles([(positive.tag("fb"),"fb")],order,.76,"difference_to_right_value")
        self.mark("interval_increasing_ready")
        self.beat(.88,FadeOut(world),FadeOut(explanation))
        self.beat(.90,FadeIn(self.put(r"f'<0\ \text{on}\ I\quad\Longrightarrow\quad f(a)>f(b)\ (a<b)",-3.55,-.8,size=28,width=6.0)))
        self.mark("interval_decreasing_ready")
        self.focus_begin("interval_decreasing")
