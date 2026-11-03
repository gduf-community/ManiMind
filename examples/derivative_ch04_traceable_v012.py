"""Separate base history, pending computations and ready values in one_change.

Writer: 01a19f6b-1725-7be3-a4d8-bf988a308b31. This cue owns the base
reference, stage roles, counters and updater; all expire at the next cue.
Changing source, role geometry or clocks invalidates its evidence. No approval.
"""

from derivative_ch04_traceable_v011 import DerivativeChainTraceableV011
from derivative_ch04_chain import X_COLOR, U_COLOR, Y_COLOR, inner, composite
from derivative_chapter_shared import MUTED
from manimlib import Arrow, FadeIn, Group, ValueTracker, linear


class DerivativeChainTraceableV012(DerivativeChainTraceableV011):
    def one_change(self):
        x, u, y = ValueTracker(1), ValueTracker(2), ValueTracker(8)
        trackers = (x, u, y)
        positions, colors = (-4.2, 0, 4.2), (X_COLOR, U_COLOR, Y_COLOR)
        numbers = [self.number(t.get_value(), size=34 if i == 2 else 40,
                   color=color, decimals=6 if i == 2 else 3).move_to([p,.55,0])
                   for i,(t,p,color) in enumerate(zip(trackers,positions,colors))]
        history = Group(self.label("基点对照",0,2.85,size=24,color=MUTED),
            *(self.put(tex,p,2.4,size=28,color=MUTED) for tex,p in
              zip((r"x_0=1",r"u_0=2",r"y_0=8"),positions)))
        badges = [self.label(text,p,1.08,size=24,color=color) for text,p,color in
                  zip(("输入变化","内层待计算","外层待计算"),positions,colors)]
        pending = [None,self.label("待新输入",0,.55,size=29,color=MUTED),
                   self.label("待中间量",4.2,.55,size=29,color=MUTED)]
        main = Group(*(self.put(name,p,1.7,color=color) for name,p,color in
                     zip(("x","u=x^2+1","y=u^3"),positions,colors)),
                     numbers[0],pending[1],pending[2],*badges,
                     Arrow([-3,.55,0],[-1.2,.55,0],buff=.1),
                     Arrow([1.2,.55,0],[3,.55,0],buff=.1))
        self.beat(.12,FadeIn(history),FadeIn(main))
        self.mark("change_base_ready")
        self.mark("change_history_roles_ready")
        roles = ["input_computing","pending","pending"]
        phase = {"name":"input"}
        driver = Group()

        def badge(index,text):
            replacement = self.label(text,positions[index],1.08,size=24,color=colors[index])
            self.remove(badges[index])
            main.remove(badges[index])
            badges[index] = replacement
            self.add(replacement)

        def begin_calculation(index,text):
            self.remove(pending[index])
            main.remove(pending[index])
            badge(index,text)
            numbers[index].set_opacity(.6)
            self.add(numbers[index])
            roles[index] = "computing"

        def ready(index,text):
            badge(index,text)
            numbers[index].set_opacity(1)
            roles[index] = "ready"

        def update(_):
            for number,tracker in zip(numbers,trackers):
                number.set_value(tracker.get_value())
            present = {id(m) for obj in self.mobjects for m in obj.get_family()}
            shown = [any(id(m) in present for m in number.family_members_with_points()) for number in numbers]
            self.sample("chain_transfer",phase=phase["name"],x=float(x.get_value()),
                        u=float(u.get_value()),y=float(y.get_value()))
            self.sample("transfer_display_roles",phase=phase["name"],roles=roles.copy(),
                        numeric_shown=shown,base=(1,2,8),
                        base_reference_present=any(obj is history for obj in self.mobjects))

        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("input_change")
        self.beat(.28,x.animate.set_value(1.1),rate_func=linear)
        ready(0,"新输入已就绪")
        self.mark("input_change_complete")
        self.beat(.34,FadeIn(self.put(r"\Delta x=0.1",-4.2,-.45,size=32,color=X_COLOR)))
        self.beat(.37)
        self.focus_end("input_change")
        self.beat(.39)
        phase["name"] = "inner"
        begin_calculation(1,"内层计算中")
        self.focus_begin("inner_change")
        self.beat(.51,u.animate.set_value(inner(1.1)),rate_func=linear)
        ready(1,"新中间量已就绪")
        self.mark("inner_change_complete")
        self.beat(.57,FadeIn(self.put(r"\Delta u=0.21",0,-.45,size=32,color=U_COLOR)))
        self.beat(.60)
        self.focus_end("inner_change")
        self.beat(.63)
        phase["name"] = "outer"
        begin_calculation(2,"外层计算中")
        self.focus_begin("outer_change")
        self.beat(.74,y.animate.set_value(composite(1.1)),rate_func=linear)
        ready(2,"新输出已就绪")
        self.mark("outer_change_complete")
        self.beat(.76,FadeIn(self.put(r"\Delta y=2.793861",4.2,-.45,size=30,color=Y_COLOR)))
        self.beat(.77)
        self.focus_end("outer_change")
        driver.clear_updaters()
        self.beat(.80)
        self.beat(.86,FadeIn(self.label("同一次输入改变，经过两级传到输出",0,-1.6,size=32)))
        self.focus_begin("transfer_complete")
        self.mark("chain_transfer_ready")


class DerivativeChainStateProbeV012(DerivativeChainTraceableV012):
    def construct(self):
        self.motion_samples = []
        for cue in self.cues:
            self.begin_chapter(cue)
            getattr(self,cue["id"])()
            self.end_chapter()
