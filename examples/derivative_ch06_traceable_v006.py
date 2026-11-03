"""CH06 v006: one anchored derivative and fresh inequality glyphs.

Writer: 01a19f6b-174f-7431-a0fd-2adf59301a9e. Consumers: renderer,
native tests and independent reviewers. Glyph roles and retired relations live
for one construct; changed sources or timing invalidate evidence. v005 frozen.
"""
from derivative_ch06_traceable import DerivativeCh06Traceable
from derivative_ch06_extrema_v004 import VALUES
from derivative_ch06_extrema import path
from derivative_chapter_shared import ACCENT, CURVE, MUTED, RATE
from manimind.components.formula_motion import SemanticFormula, matching_transform
from manimlib import Dot, FadeIn, FadeOut, Group, Line, ShowCreation, Transform, ValueTracker, VGroup, linear

AUTHOR_AGENT = "01a19f6b-174f-7431-a0fd-2adf59301a9e"


class DerivativeCh06TraceableV006(DerivativeCh06Traceable):
    def signed(self, latex, x, y, *, side=None, limit=False):
        relation=r"\geq" if r"\geq" in latex else r"\leq"
        tokens={**VALUES,"bound":relation,"zero":("0",1) if limit else "0"}
        if side:
            tokens["side"]=side
        value=self.semantic(latex,tokens,x,y,size=30 if limit else 32,width=5.9 if limit else 5.8)
        value.tag("zero").set_color(RATE)
        return value

    def copy_parts(self, origins, targets, end, stage, *syntax):
        self.until(self._cue["start"]+self._cue["animation_starts"][f"{end:.2f}"])
        if any(float(g.get_opacity())<.95 for part in origins for g in part.family_members_with_points()):
            raise ValueError("Copy only currently visible proof roles")
        moving=[part.copy() for part in origins]
        destinations=[part.copy() for part in targets]
        driver=Group()

        def sample(_):
            self.sample("v006_role_copy",stage=stage,moving=[m.get_center().tolist() for m in moving],
                targets=[m.get_center().tolist() for m in destinations])

        sample(driver)
        driver.add_updater(sample)
        self.add(driver,*moving)
        self.beat(end,*(Transform(m,t,path_arc=0) for m,t in zip(moving,destinations)),*syntax)
        driver.clear_updaters()
        self.remove(driver,*moving)
        self.add(*targets)
        self.mark(stage+"_ready")

    def reverse_relations(self, old, replacements, end, premise):
        fresh=[]
        for source,latex in zip(old,replacements):
            target=self.put(latex,size=30,color=RATE)
            target.set_height(source.get_height()).move_to(source.get_center())
            fresh.append(target)
        driver=Group()

        def sample(_):
            self.sample("v006_relation_reversal",old=[float(m.get_opacity()) for m in old],
                new=[float(m.get_opacity()) for m in fresh],
                old_present=[any(m is obj for obj in self.mobjects) for m in old],
                new_present=[any(m is obj for obj in self.mobjects) for m in fresh])

        driver.add_updater(sample)
        self.add(driver)
        self.beat(.72,*(FadeOut(m) for m in old))
        self.remove(*old)
        # Native FadeOut cleanup restores its source style after removal.
        # Retired relations must also stay invisible in any retained parent.
        for relation in old:
            relation.set_opacity(0)
        self.mark("minimum_old_relations_removed")
        self.beat(.75,FadeIn(premise))
        self.mark("minimum_blank_relations_readable")
        # Never pass a retired parent formula to a transform: it can re-add
        # hidden relation glyphs while installing otherwise unmatched syntax.
        self.beat(end,*(ShowCreation(m) for m in fresh))
        self.mark("minimum_fresh_relations_ready")
        driver.clear_updaters()
        self.remove(driver)
        return fresh

    def necessary(self,cue):
        self.begin_chapter(cue)
        condition=self.label("可导的内点 a",0,2.55,size=31,color=ACCENT)
        implication=Group(self.label("a 是局部极值点",-2.7,1.85,size=29,width=5),
                          self.put(r"\Longrightarrow\quad f'(a)=0",2.65,1.85,size=37,width=5))
        self.beat(.13,FadeIn(condition),FadeIn(implication))
        self.mark("conditional_necessity_ready")
        persistent=tuple(self.mobjects)
        self.focus_begin("conditional_necessity")
        axis=Line([-3,.65,0],[3,.65,0],color=MUTED,stroke_width=2)
        ticks=Group(*(Line([x,.52,0],[x,.78,0],color=ACCENT) for x in (-3,0,3)))
        labels=Group(self.put(r"a-\delta",-3,.12,size=29),self.put("a",0,.12,size=29),self.put(r"a+\delta",3,.12,size=29),
            self.put(r"(a-\delta,a+\delta)\subset\mathrm{Dom}(f)",0,-.65,size=31,width=11.8),
            self.put(r"0<|h|<\delta",0,-1.35,size=31,color=ACCENT))
        approach=ValueTracker(.75)
        probes=Group(Dot([-2.25,.65,0],color=CURVE,radius=.065),Dot([2.25,.65,0],color=CURVE,radius=.065))
        self.beat(.18,ShowCreation(axis),FadeIn(ticks),FadeIn(labels),FadeIn(probes))
        self.mark("interior_neighborhood_ready")
        driver=Group()

        def update(_):
            ratio=approach.get_value()
            probes[0].move_to([-3*ratio,.65,0])
            probes[1].move_to([3*ratio,.65,0])
            self.sample("proof_neighborhood",abs_h_over_delta=ratio,left=probes[0].get_center().tolist(),right=probes[1].get_center().tolist())

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.beat(.22,approach.animate.set_value(.16),rate_func=linear)
        driver.clear_updaters()
        finite=self.label("可导：左右得到同一个有限导数",0,-2.15,size=28)
        self.beat(.26,FadeIn(finite))
        self.beat(.29)
        self.focus_end("conditional_necessity")
        maximum=self.label("局部极大：取足够小的邻域",-2.7,1.08,size=26,width=6)
        bound=self.put(r"0<|h|<\delta",3.5,1.08,size=29,color=ACCENT,width=4.5)
        comparison=self.semantic(r"f(a+h)\leq f(a)",VALUES,0,.35,size=34,width=11.8)
        self.beat(.32,*(FadeOut(m) for m in (axis,ticks,labels,probes,finite)),FadeIn(maximum),FadeIn(bound),FadeIn(comparison))
        self.focus_begin("one_sided_quotients")
        self.mark("local_comparison_ready")
        numerator=self.semantic(r"f(a+h)-f(a)\leq0",{**VALUES,"bound":r"\leq0"},0,-.45,size=34,width=11.8)
        self.reason_transfer(comparison,numerator,.38,stage="comparison_to_numerator",pairs=[("near","near"),("center","center")],copy=True)
        self.mark("common_numerator_ready")
        left_sign=self.put("h<0",-3,-2.55,size=30,color=ACCENT)
        right_sign=self.put("h>0",3,-2.55,size=30,color=ACCENT)
        left=self.signed(r"\frac{f(a+h)-f(a)}h\geq0",-3,-1.75)
        right=self.signed(r"\frac{f(a+h)-f(a)}h\leq0",3,-1.75)
        self.beat(.40,FadeIn(left_sign))
        self.reason_transfer(numerator,left,.44,stage="negative_h_quotient",pairs=[("near","near"),("center","center")],copy=True)
        self.mark("left_quotient_ready")
        self.beat(.46,FadeIn(right_sign))
        self.reason_transfer(numerator,right,.50,stage="positive_h_quotient",pairs=[("near","near"),("center","center")],copy=True)
        self.mark("one_sided_quotients_ready")
        self.beat(.55)
        self.focus_end("one_sided_quotients")
        self.beat(.56,*(FadeOut(m) for m in (comparison,numerator,left_sign,right_sign)))
        self.focus_begin("common_zero_necessity")

        left_limit=self.signed(r"L=\lim_{h\to0^-}\frac{f(a+h)-f(a)}h\geq0",-3.1,-.25,side="L",limit=True)
        right_limit=self.signed(r"R=\lim_{h\to0^+}\frac{f(a+h)-f(a)}h\leq0",3.1,-.25,side="R",limit=True)
        pairs=[(key,key) for key in ("near","center","bound","zero")]
        self.beat(.58,matching_transform(left,left_limit,pairs=pairs,unmatched_in_place=True),
            matching_transform(right,right_limit,pairs=pairs,unmatched_in_place=True))
        self.mark("one_sided_limits_ready")
        equality=self.semantic(r"L=f'(a)=R",{"left":"L","derivative":"f'(a)","right":"R"},0,-1.25,size=37)
        equal_reason=self.label("可导：L、R 对应同一个导数",0,-2.95,size=27,color=ACCENT,width=10)
        self.add(equal_reason)
        self.assemble(equality,[(left_limit,"side","left"),(right_limit,"side","right")],.60,"equal_derivative")
        self.beat(.59)
        common=equality.tag("derivative")
        used={id(g) for g in common.family_members_with_points()}
        aliases=VGroup(*(g for g in equality.family_members_with_points() if id(g) not in used))
        self.beat(.61,FadeOut(aliases))
        self.remove(equality,aliases)
        aliases.set_opacity(0)
        self.add(common)
        anchor=Group()

        def common_sample(_):
            self.sample("v006_common_anchor",center=common.get_center().tolist(),
                glyph_ids=[id(g) for g in common.family_members_with_points()],
                opacity=[float(g.get_opacity()) for g in common.family_members_with_points()])

        common_sample(anchor)
        anchor.add_updater(common_sample)
        self.add(anchor)
        left_rel=self.put(r"\leq",size=37,color=RATE).move_to([common.get_left()[0]-.3,-1.25,0])
        right_rel=self.put(r"\leq",size=37,color=RATE).move_to([common.get_right()[0]+.3,-1.25,0])
        left_zero=self.put("0",size=37,color=RATE).move_to([left_rel.get_center()[0]-.45,-1.25,0])
        right_zero=self.put("0",size=37,color=RATE).move_to([right_rel.get_center()[0]+.45,-1.25,0])
        self.copy_parts([left_limit.tag("zero")],[left_zero],.64,"derivative_lower",ShowCreation(left_rel))
        self.beat(.65)
        self.copy_parts([right_limit.tag("zero")],[right_zero],.67,"bounds_join",ShowCreation(right_rel))
        self.mark("derivative_upper_ready")
        self.beat(.68)
        self.mark("complete_clamp_readable")
        result=self.semantic(r"\Longrightarrow\quad f'(a)=0",{"derivative":"f'(a)","zero":"0"},0,-2.2,size=35)
        occupied={id(g) for key in ("derivative","zero") for g in result.tag(key).family_members_with_points()}
        syntax=VGroup(*(g for g in result.family_members_with_points() if id(g) not in occupied))
        result_parts=[result.tag("derivative"),result.tag("zero")]
        self.copy_parts([common,right_zero],result_parts,.70,"bounds_to_zero",FadeIn(syntax))
        self.remove(syntax,*result_parts)
        self.add(result)
        self.mark("common_zero_proved")

        minimum=self.label("局部极小：不等号反向",-2.7,1.08,size=26,width=6)
        minimum_bound=self.put(r"0<|h|<\delta:\ f(a+h)-f(a)\geq0",0,.65,size=28,width=11.8)
        self.beat(.71,FadeOut(maximum),FadeOut(bound),FadeIn(minimum))
        retired=[left_limit.tag("bound"),right_limit.tag("bound"),left_rel,right_rel]
        fresh=self.reverse_relations(retired,[r"\leq",r"\geq",r"\geq",r"\geq"],.73,minimum_bound)
        self.mark("minimum_same_zero_ready")
        self.beat(.74)
        self.focus_end("common_zero_necessity")
        anchor.clear_updaters()
        self.remove(anchor)
        visible_proof=[m for m in self.mobjects if all(m is not old for old in persistent)]
        self.beat(.77,*(FadeOut(m) for m in visible_proof))
        cusp=path([[-2.4,-1.3,0],[-1.2,-2.5,0],[0,-1.3,0]],ACCENT)
        self.beat(.79,ShowCreation(cusp),FadeIn(self.put(r"y=|x|",-4,-1.9,size=35,width=2.3)),
            FadeIn(self.label("0 是尖点极小，导数不存在",3.1,-1.8,size=28,width=5.7)),
            FadeIn(self.label("这说明为什么要保留“可导内点”",3.1,-2.5,size=26,color=MUTED,width=5.7)))
        self.mark("cusp_condition_ready")
        self.focus_begin("cusp_condition")
        self.end_chapter()
