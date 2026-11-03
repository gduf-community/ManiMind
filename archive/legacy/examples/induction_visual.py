"""Motional induction: one physical model, three representations.

The scene owns transient geometry/model samples. The existing visual runtime
writes actual events and focus windows; none of these annotations approve it.
"""

import json
import math
import sys

_argv = sys.argv
try:
    sys.argv = sys.argv[:1]
    import numpy as np
    from manimlib import *
    from manimind.components.formula_motion import SemanticFormula, matching_transform
    from manimind.experiments.understanding_support import UnderstandingScene
finally:
    sys.argv = _argv
del _argv


INK = "#EEF3F2"
MUTED = "#99ABA9"
BLUE = "#70BAED"
CORAL = "#F29180"
MINT = "#94D8B2"
GOLD = "#E8CC78"
GRID = "#314447"


def conductor_state(x, velocity, magnetic_field=.5, length=2., resistance=5.):
    """B into page; outward normal/CCW positive; stationary rails and load."""
    values = (x, velocity, magnetic_field, length, resistance)
    if not all(math.isfinite(v) for v in values) or x < 0 or min(magnetic_field, length, resistance) <= 0:
        raise ValueError("Finite state, nonnegative loop width and positive B/length/R required")
    emf = magnetic_field * length * velocity
    current = emf / resistance
    drag = -magnetic_field * length * current
    return {"x": x, "velocity": velocity, "area": length * x,
            "flux": -magnetic_field * length * x, "emf": emf, "current": current,
            "magnetic_force_x": drag, "external_force_x": -drag,
            "mechanical_power": -drag * velocity, "heat_power": current * current * resistance}


def sweep_state(time, start_x=2.5, velocity=3.):
    if not math.isfinite(time) or time < 0:
        raise ValueError("Finite nonnegative physical time required")
    return conductor_state(start_x + velocity * time, velocity)


class InductionLesson(UnderstandingScene):
    def cn_at(self, text, x, y, size=30, color=INK, width=None):
        obj = self.cn(text, size=size, color=color)
        if width is not None and obj.get_width() > width:
            obj.set_width(width)
        return obj.move_to([x, y, 0])

    def eq(self, latex, x, y, size=38, color=INK):
        return self.formula(latex, size=size, color=color).move_to([x, y, 0])

    def semantic(self, latex, tokens, x=3.9, y=.2, size=40):
        obj = SemanticFormula(latex, tokens=tokens, font_size=size)
        obj.set_color(INK)
        for key in obj.semantic_ids:
            if key in ("field", "emf", "flux"):
                obj.tag(key).set_color(MINT)
            elif key in ("speed", "force"):
                obj.tag(key).set_color(CORAL)
            elif key in ("length", "width"):
                obj.tag(key).set_color(BLUE)
        if obj.get_width() > 5.2:
            obj.set_width(5.2)
        return obj.move_to([x, y, 0])

    def enter(self, cue_id):
        self._live=None
        cue = next(c for c in self.cues if c["id"] == cue_id)
        self.until(cue["start"])
        old = [o for o in self.mobjects if o is not self._subtitle_driver]
        if old:
            self.play(*(FadeOut(o) for o in old), run_time=.4)
            self.remove(*old)
        root = Group(self.cn_at(cue["heading"], 0, 3.18, 42),
                     Line([-6.6, 2.75, 0], [6.6, 2.75, 0], stroke_color=GRID, stroke_width=1))
        self.add(root)
        return cue["start"], root

    def reveal(self, root, *objects, duration=.7):
        self.play(*(FadeIn(o) for o in objects), run_time=duration)
        root.add(*objects)
        self.remove(*objects)
        self.add(root)

    def morph(self, root, old, new, duration=1.8):
        root.remove(old)
        self.add(old)
        self.play(matching_transform(old, new, unmatched_in_place=True), run_time=duration)
        self.remove(new)
        root.add(new)
        self.add(root)
        return new

    def focus(self, identity, end):
        self.focus_begin(identity)
        self.until(end)
        self.focus_end(identity)

    def field(self, left=-5.7, right=1.8, bottom=-1.55, top=1.55):
        result = Group()
        for x in np.arange(left + .25, right, .65):
            for y in np.arange(bottom + .2, top, .6):
                result.add(Line([x-.055, y-.055, 0], [x+.055, y+.055, 0], stroke_color=BLUE, stroke_width=1.6),
                           Line([x-.055, y+.055, 0], [x+.055, y-.055, 0], stroke_color=BLUE, stroke_width=1.6))
        return result.set_opacity(.48)

    def arrow(self, a, b, color=MINT):
        return Arrow(a, b, buff=0, thickness=2.5, fill_color=color, stroke_color=color)

    def cross_symbol(self, x, y, color=BLUE):
        return Group(Circle(radius=.17, stroke_color=color, stroke_width=2).move_to([x,y,0]),
            Line([x-.08,y-.08,0],[x+.08,y+.08,0],stroke_color=color,stroke_width=2),
            Line([x-.08,y+.08,0],[x+.08,y-.08,0],stroke_color=color,stroke_width=2))

    def out_symbol(self, x, y, color=MINT):
        return Group(Circle(radius=.17, stroke_color=color, stroke_width=2).move_to([x,y,0]),
                     Dot([x,y,0],radius=.045,fill_color=color))

    def circuit(self, x=2.5, velocity=3., numeric=True):
        left, low, high, scale = -5.25, -1.1, 1.1, 1.1
        rod_x = left + scale * x
        area = Polygon([left,low,0],[rod_x,low,0],[rod_x,high,0],[left,high,0],
                       stroke_width=0, fill_color=BLUE, fill_opacity=.12)
        rails = Group(Line([left,high,0],[1.6,high,0],stroke_color=INK,stroke_width=3),
                      Line([left,low,0],[1.6,low,0],stroke_color=INK,stroke_width=3),
                      Line([left,low,0],[left,-.5,0],stroke_color=INK,stroke_width=3),
                      Line([left,.5,0],[left,high,0],stroke_color=INK,stroke_width=3))
        zigzag = VMobject(stroke_color=GOLD,stroke_width=3)
        zigzag.set_points_as_corners([[left,-.5,0]] +
            [[left + (.14 if i%2 else -.14), -.5+i/8, 0] for i in range(1,8)] + [[left,.5,0]])
        rod = Line([rod_x,low,0],[rod_x,high,0],stroke_color=CORAL,stroke_width=7)
        arrows = Group(self.arrow([-3.3,high,0],[-4.1,high,0]),
                       self.arrow([-4.1,low,0],[-3.3,low,0]),
                       self.arrow([rod_x,-.45,0],[rod_x,.45,0]))
        speed = self.arrow([rod_x+.18,1.65,0],[rod_x+1.18,1.65,0],CORAL)
        speed_label = self.eq("v",rod_x+.65,1.35,25,CORAL)
        number = self.number(conductor_state(x,velocity)["current"],size=40,decimals=2,color=MINT).move_to([4.4,1.15,0])
        root = Group(self.field(), area, rails, zigzag, rod, arrows, speed, speed_label,
            self.eq(r"B=0.5\,\mathrm{T}", -4.3, 2.05, 28, BLUE),
            self.cn_at("磁场向纸内", -2.5, 2.05, 24, BLUE),
            self.eq(r"\ell=2\,\mathrm{m}", -.25,-1.7,30,BLUE),
            self.eq(r"R=5\,\Omega", -4.55,0,27,GOLD),
            self.cn_at("电阻只计R，自感忽略",-3.1,-2.8,22,MUTED,width=6.4))
        if numeric:
            root.add(self.cn_at("逆时针为正",4.05,2.05,26,MUTED),
                     self.eq("I=",3.45,1.15,38,MINT),number,self.eq(r"\mathrm A",5.4,1.15,32,MINT))
        return {"root":root,"left":left,"low":low,"high":high,"scale":scale,
                "rod":rod,"resistor":zigzag,"area":area,"arrows":arrows,"speed":speed,"speed_label":speed_label,"number":number}

    def draw_circuit(self, diagram, state):
        x = diagram["left"] + diagram["scale"] * state["x"]
        lo,hi,left = diagram["low"],diagram["high"],diagram["left"]
        diagram["rod"].put_start_and_end_on(np.array([x,lo,0]),np.array([x,hi,0]))
        diagram["area"].set_points_as_corners([[left,lo,0],[x,lo,0],[x,hi,0],[left,hi,0],[left,lo,0]])
        sign = 1 if state["current"] >= 0 else -1
        for arrow,a,b in ((diagram["arrows"][0],[-3.3,hi,0],[-4.1,hi,0]),
                          (diagram["arrows"][1],[-4.1,lo,0],[-3.3,lo,0]),
                          (diagram["arrows"][2],[x,-.45,0],[x,.45,0])):
            arrow.put_start_and_end_on(np.array(a if sign>0 else b),np.array(b if sign>0 else a))
        diagram["arrows"].set_opacity(1 if abs(state["current"])>.00001 else 0)
        diagram["speed"].put_start_and_end_on(np.array([x+.15,1.65,0]),np.array([x+.15+sign*.9,1.65,0]))
        diagram["speed"].set_opacity(1 if abs(state["velocity"])>.00001 else 0)
        diagram["speed_label"].move_to([x+.15+sign*.45,1.35,0])
        diagram["speed_label"].set_opacity(1 if abs(state["velocity"])>.00001 else 0)
        diagram["number"].set_value(state["current"])
        self._live = {**state,"rod_scene_x":float(diagram["rod"].get_x())}

    def update_mobjects(self, dt):
        super().update_mobjects(dt)
        if getattr(self,"_live",None) is not None and self.get_time()>getattr(self,"_last_sample",-1)+.00001:
            self.model_samples.append({"time":float(self.get_time()),**self._live})
            self._last_sample=float(self.get_time())

    def construct(self):
        self.camera.background_rgba=color_to_rgba("#101416")
        self.model_samples=[]
        self._live=None
        self.opening()
        self.separation()
        self.open_voltage()
        self.flux()
        self.direction()
        self.energy()
        self.prediction()
        self._live=None

    def opening(self):
        s,root=self.enter("opening")
        d=self.circuit(velocity=0)
        self.draw_circuit(d,conductor_state(2.5,0))
        label=self.cn_at("导体棒停在磁场里",3.9,-.2,31,width=4.3)
        self.reveal(root,d["root"],label)
        self.mark("stationary_loop_visible")
        self.focus("stationary_question",s+6)
        root.remove(label)
        self.remove(label)
        label=self.cn_at("推杆时，回路出现电流",3.9,-.2,31,width=4.3)
        self.reveal(root,label,duration=.6)
        self.focus_begin("moving_loop")
        self.play(UpdateFromAlphaFunc(d["rod"],lambda _,a:self.draw_circuit(d,sweep_state(.8*a))),run_time=7,rate_func=linear)
        self.mark("moving_current_visible")
        self.until(s+16)
        self.focus_end("moving_loop")
        self.draw_circuit(d,conductor_state(4.9,0))
        root.remove(label)
        self.remove(label)
        label=self.cn_at("停下，电流回到零",3.9,-.2,31,width=4.3)
        self.reveal(root,label,duration=.6)
        self.reveal(root,self.eq(r"v=0\quad\Rightarrow\quad I=0",3.9,-1.25,34))
        self.mark("stopped_current_zero")
        self.focus("stopped_result",s+19.8)
        self.until(s+20)

    def separation(self):
        s,root=self.enter("separation")
        rod=Line([-1.5,-1.3,0],[-1.5,1.3,0],stroke_color=CORAL,stroke_width=8)
        electron=Group(Circle(radius=.15,stroke_color=CORAL,fill_color="#101416",fill_opacity=1),
                       Line([-.08,0,0],[.08,0,0],stroke_color=CORAL,stroke_width=3)).move_to([-1.5,.1,0])
        force=self.arrow([-1.05,.05,0],[-1.05,-.85,0],CORAL)
        self.reveal(root,self.field(-4.6,1.2,-1.6,1.6),rod,electron,
            self.arrow([-1.1,1.85,0],[.1,1.85,0],CORAL),self.eq("v",.3,1.85,32,CORAL),
            self.cn_at("开路导体棒",-3.25,2.15,30),
            self.cn_at("电子",1.4,.15,28,CORAL),self.cn_at("磁场向纸内",-3.5,-2.1,27,BLUE))
        self.mark("open_rod_visible")
        self.focus("open_rod_and_electron",s+7)
        self.reveal(root,force,self.cn_at("磁场力",.2,-.6,28,CORAL))
        self.focus_begin("electron_deflection")
        self.play(electron.animate.move_to([-1.5,-.85,0]),run_time=2.5)
        top=self.eq("+",-1.5,1.55,42,CORAL)
        bottom=self.eq("-",-1.5,-1.55,42,BLUE)
        self.reveal(root,top,bottom,self.cn_at("上端缺电子，下端多电子",3.1,1.6,28,width=5.3))
        self.mark("charge_separation_visible")
        self.until(s+17)
        self.focus_end("electron_deflection")
        electric=self.arrow([-2.3,.7,0],[-2.3,-.7,0],GOLD)
        electric_force=self.arrow([-1.95,-.8,0],[-1.95,.1,0],MINT)
        self.reveal(root,electric,electric_force,self.eq("E_s",-2.75,.15,32,GOLD),
            self.cn_at("电场力",-.2,.6,28,MINT),self.cn_at("电荷分离建立电场",3.0,.55,30,width=5.1))
        self.mark("electric_restoring_force_visible")
        self.focus("electric_balance",s+28)
        self.reveal(root,self.eq(r"|q|E_s=|q|vB",3,-.7,42),
                    self.cn_at("稳态：两种力大小相等",3,-1.7,29,width=5.2))
        self.mark("open_force_balance_visible")
        self.focus("open_force_balance",s+37.8)
        self.until(s+38)

    def open_voltage(self):
        s,root=self.enter("voltage")
        self.reveal(root,Line([-3.7,-1.2,0],[-3.7,1.2,0],stroke_color=CORAL,stroke_width=8),
            self.eq("+",-3.7,1.5,40,CORAL),self.eq("-",-3.7,-1.5,40,BLUE),
            self.arrow([-2.8,.65,0],[-2.8,-.65,0],GOLD),self.eq("E_s",-2.1,.1,32,GOLD),
            self.eq(r"\ell",-4.35,0,40,BLUE),self.cn_at("开路两端电压 U",-3.4,-2.25,31))
        f=self.semantic(r"{|q|}{E_s}={|q|}{v}{B}",
            {"field":"{E_s}","speed":"{v}","magnetic":"{B}"},3.4,1.15)
        self.reveal(root,f)
        self.mark("force_balance_algebra")
        self.focus("force_balance_before_cancel",s+7)
        f=self.morph(root,f,self.semantic(r"{E_s}={v}{B}",
            {"field":"{E_s}","speed":"{v}","magnetic":"{B}"},3.4,1.15))
        self.mark("electric_field_relation_visible")
        self.focus("field_relation",s+13)
        voltage=self.semantic(r"{U}={E_s}{\ell}",{"voltage":"{U}","field":"{E_s}","length":r"{\ell}"},3.4,-.05)
        self.reveal(root,voltage)
        self.mark("voltage_length_relation")
        self.focus("voltage_from_field",s+19)
        voltage=self.morph(root,voltage,self.semantic(r"{U}={B}{\ell}{v}",
            {"voltage":"{U}","magnetic":"{B}","length":r"{\ell}","speed":"{v}"},3.4,-.05))
        self.reveal(root,self.eq(r"0.5\,\mathrm T\times2\,\mathrm m\times3\,\mathrm{m/s}=3\,\mathrm V",2.35,-1.7,29))
        self.mark("open_voltage_result")
        self.focus("open_voltage_result_hold",s+29.8)
        self.until(s+30)

    def flux(self):
        s,root=self.enter("flux")
        d=self.circuit()
        self.draw_circuit(d,conductor_state(2.5,3))
        self.reveal(root,d["root"],self.cn_at("闭合回路",-3.2,-2.1,30),
            self.cn_at("纸外为磁通正向",4,2.55,25,MUTED))
        self.mark("closed_loop_visible")
        self.focus("closed_current",s+7)
        oldx=d["rod"].get_x()
        swept=Polygon([oldx,-1.1,0],[oldx+.001,-1.1,0],[oldx+.001,1.1,0],[oldx,1.1,0],
                      fill_color=GOLD,fill_opacity=.35,stroke_width=0)
        root.add(swept)
        def sweep(_,a):
            state=sweep_state(.8*a)
            self.draw_circuit(d,state)
            x=d["rod"].get_x()
            swept.set_points_as_corners([[oldx,-1.1,0],[x,-1.1,0],[x,1.1,0],[oldx,1.1,0],[oldx,-1.1,0]])
        self.focus_begin("swept_area_motion")
        self.play(UpdateFromAlphaFunc(d["rod"],sweep),run_time=6,rate_func=linear)
        self.mark("swept_area_visible")
        self.until(s+18)
        self.focus_end("swept_area_motion")
        f=self.semantic(r"\Delta A={\ell}{\Delta x}",{"length":r"{\ell}","width":r"{\Delta x}"},4,.05,36)
        self.reveal(root,f)
        self.mark("swept_area_equation")
        self.focus("swept_area_relation",s+24)
        f=self.morph(root,f,self.semantic(r"\Delta\Phi_B=-{B}{\ell}{\Delta x}",
            {"magnetic":"{B}","length":r"{\ell}","width":r"{\Delta x}"},4,.05,35))
        self.mark("signed_flux_change")
        self.focus("signed_flux_relation",s+31)
        f=self.morph(root,f,self.semantic(r"{\mathcal E}={B}{\ell}\frac{\Delta x}{\Delta t}",
            {"emf":r"{\mathcal E}","magnetic":"{B}","length":r"{\ell}","speed":r"\frac{\Delta x}{\Delta t}"},4,.05,35))
        self.reveal(root,self.eq(r"\mathcal E=-\frac{\Delta\Phi_B}{\Delta t}",4,-1.1,32))
        self.mark("faraday_substitution_visible")
        self.focus("faraday_substitution",s+39)
        f=self.morph(root,f,self.semantic(r"{\mathcal E}={B}{\ell}{v}",
            {"emf":r"{\mathcal E}","magnetic":"{B}","length":r"{\ell}","speed":"{v}"},4,.05,40))
        self.reveal(root,self.eq(r"\frac{\Delta x}{\Delta t}=v",4,-2,32,CORAL))
        self.mark("motional_emf_visible")
        self.focus("motional_emf_relation",s+49.8)
        self.until(s+50)

    def direction(self):
        s,root=self.enter("direction")
        d=self.circuit(x=2.5)
        self.draw_circuit(d,conductor_state(2.5,3))
        outward=Group(self.out_symbol(-3.5,.1),self.cn_at("感应磁场向纸外",-3.3,-2,29,MINT))
        self.reveal(root,d["root"],outward,
            self.eq(r"I=\frac{B\ell v}{R}",4,-.1,38))
        self.mark("lenz_outward_visible")
        self.focus_begin("lenz_increasing")
        self.play(UpdateFromAlphaFunc(d["rod"],lambda _,a:self.draw_circuit(d,sweep_state(.8*a))),run_time=5,rate_func=linear)
        self.until(s+12)
        self.focus_end("lenz_increasing")
        self.draw_circuit(d,conductor_state(4.9,0))
        outward.set_opacity(0)
        stopped=self.cn_at("停下：磁通不再变化",3.9,-1.9,27,width=5.1)
        self.reveal(root,stopped)
        self.mark("stationary_flux_visible")
        self.focus("stationary_flux",s+18)
        self.play(FadeOut(outward),FadeOut(stopped),run_time=.4)
        root.remove(outward,stopped)
        self.draw_circuit(d,conductor_state(4.9,-3))
        self.reveal(root,self.cross_symbol(-2,.1,MINT),self.cn_at("感应磁场向纸内",-3.3,-2,29,MINT),
            self.cn_at("反向运动",4,-1.3,31,CORAL))
        self.focus_begin("lenz_decreasing")
        self.play(UpdateFromAlphaFunc(d["rod"],lambda _,a:self.draw_circuit(d,sweep_state(.8*a,start_x=4.9,velocity=-3))),run_time=5,rate_func=linear)
        self.mark("reverse_current_visible")
        self.until(s+29.8)
        self.focus_end("lenz_decreasing")
        self.until(s+30)

    def energy(self):
        s,root=self.enter("energy")
        d=self.circuit(x=3.2)
        self.draw_circuit(d,conductor_state(3.2,3))
        self.reveal(root,d["root"],self.arrow([-1.2,.35,0],[-.25,.35,0],CORAL),
            self.arrow([-1.65,-.35,0],[-2.6,-.35,0],GOLD),
            self.cn_at("外力",.35,.35,27,CORAL),self.cn_at("安培力",-3,-.35,27,GOLD))
        self.mark("opposing_mechanical_forces")
        self.focus("mechanical_energy_source",s+9)
        force=self.semantic(r"{F}= {B}{I}{\ell}",{"force":"{F}","magnetic":"{B}","current":"{I}","length":r"{\ell}"},4,.1)
        self.reveal(root,force,self.eq(r"F_{\rm ext}=F",4,-.8,32))
        self.mark("drag_force_relation")
        self.focus("force_relation",s+17)
        p=self.semantic(r"{P}={F}{v}",{"power":"{P}","force":"{F}","speed":"{v}"},1.7,-2.15,38)
        self.reveal(root,p)
        self.mark("mechanical_power_visible")
        self.focus("power_from_work",s+23)
        p=self.morph(root,p,self.semantic(r"{P}={B}{I}{\ell}{v}",
            {"power":"{P}","magnetic":"{B}","current":"{I}","length":r"{\ell}","speed":"{v}"},1.7,-2.15,38))
        self.mark("magnetic_force_power_substitution")
        self.focus("power_product",s+29)
        p=self.morph(root,p,self.semantic(r"{P}={\mathcal E}{I}={I}^2{R}",
            {"power":"{P}","emf":r"{\mathcal E}","current":("{I}",0),"resistance":"{R}"},1.7,-2.15,38))
        self.reveal(root,self.cn_at("电阻发热",-4.6,-1.7,26,GOLD),
            self.cn_at("机械输入 → 电阻热功率",2.6,-2.8,24,GOLD,width=6))
        self.play(d["resistor"].animate.set_stroke(CORAL,width=5),run_time=.6)
        self.mark("energy_conservation_visible")
        self.focus("mechanical_to_heat",s+39.8)
        self.until(s+40)

    def prediction(self):
        s,root=self.enter("prediction")
        current_law=self.eq(r"I=\frac{B\ell v}{R}",0,-1.45,36,MINT)
        self.reveal(root,self.eq(r"B=0.5\,\mathrm T\qquad\ell=2\,\mathrm m\qquad R=5\,\Omega",0,2.05,31),
            self.eq(r"v:\ 3\longrightarrow6\,\mathrm{m/s}",0,1.1,40,CORAL),current_law)
        p=self.semantic(r"{P}={I}^2{R}",{"power":"{P}","current":"{I}","resistance":"{R}"},0,-.4,43)
        self.reveal(root,p)
        self.mark("power_substitution_ready")
        self.focus("power_current_relation",s+7)
        p=self.morph(root,p,self.semantic(r"{P}=\left(\frac{{B}{\ell}{v}}{{R}}\right)^2{R}",
            {"power":"{P}","current":r"\frac{{B}{\ell}{v}}{{R}}","resistance":("{R}",1)},0,-.4,40))
        self.mark("squared_current_substitution")
        self.focus("squared_current_substitution",s+12.5)
        p=self.morph(root,p,self.semantic(r"{P}=\frac{{B}^2{\ell}^2{v}^2}{{R}}",
            {"power":"{P}","magnetic":"{B}","length":r"{\ell}","speed":"{v}","resistance":"{R}"},0,-.4,43))
        self.mark("quadratic_power_law_visible")
        self.focus("quadratic_power_law",s+19)
        question=self.cn_at("推得快一倍，外力功率会怎样？",0,.45,32)
        self.reveal(root,question)
        self.mark("power_prediction_visible")
        self.focus("power_prediction",s+22.5)
        self.play(FadeOut(question),FadeOut(current_law),run_time=.4)
        root.remove(question,current_law)
        self.reveal(root,self.eq(r"I:\ 0.6\longrightarrow1.2\,\mathrm A",0,-1.45,36,MINT))
        self.mark("doubled_current_visible")
        self.focus("current_doubles",s+27)
        self.reveal(root,self.eq(r"P:\ 1.8\longrightarrow7.2\,\mathrm W",0,-2.45,38,GOLD))
        self.mark("quadrupled_power_visible")
        self.focus("power_scaling_result",s+31.8)
        self.until(s+32)

    def tear_down(self):
        self._live=None
        with (self.out/"induction-motion.json").open("x",encoding="utf-8") as stream:
            json.dump({"duration":float(self.get_time()),"samples":self.model_samples,
                "writer":"InductionLesson live geometry/model sampler","consumers":["independent reviewer","test"],
                "lifecycle":"This exact render attempt","invalidation":"Source, plan, model or media change"},stream)
        super().tear_down()
