"""Chapter 08 intact-WAV native presentation revision, not review authority.

Writer: 01a19acd-e149-74d0-8a5d-975a3adf45f4; consumers: main, native tests,
independent reviewers. Lifecycle: one v003 construct. Bound source, plan,
geometry or timing changes invalidate evidence. Original lesson author:
01a199e9-7432-7052-96f7-6bd6eb2e63bb. Model helpers remain inherited unchanged.
"""

import math

from derivative_ch08_optimization import (
    DerivativeCh08Optimization, FACE_ORDER, net_point, panel_vertices,
)
from derivative_chapter_shared import ACCENT, CURVE, RATE
from manimlib import FadeIn, FadeOut, Group, Polygon, Transform, ValueTracker, VGroup, linear


AUTHOR_AGENT = "01a19acd-e149-74d0-8a5d-975a3adf45f4"


class DerivativeCh08OptimizationV003(DerivativeCh08Optimization):
    def beat(self, fraction, *animations, **kwargs):
        key = f"{fraction:.2f}"
        end = self._cue["stage_times"][key]
        if animations:
            start = self._cue["animation_starts"].get(key, end-.4)
            absolute = self._cue["start"]+start
            if round(absolute*self.camera.fps) > round(self.get_time()*self.camera.fps):
                self.until(absolute)
        super().beat(fraction, *animations, **kwargs)
        hold = self._cue.get("post_holds", {}).get(key)
        if hold is not None:
            self.until(self._cue["start"]+hold)

    def planar_panels(self):
        # Same centimeter vertices and face identities as the oblique model.
        # This new screen-projection morph is not a physical camera rotation.
        faces = panel_vertices(2, 0)
        return VGroup(*(Polygon(*(net_point(a+2, b+2) for a, b, _ in faces[name]),
            fill_color=CURVE if name == "base" else ACCENT,
            fill_opacity=.22 if name == "base" else .12,
            stroke_color=CURVE if name == "base" else ACCENT, stroke_width=2)
            for name in FACE_ORDER))

    def fold(self, cue):
        self.begin_chapter(cue)
        angle = ValueTracker(0)
        faces = self.planar_panels()
        self.beat(.10, FadeIn(faces),
                  FadeIn(self.label("保留同一张裁好的纸板", 3.5, 1.95, size=29, width=5.5)),
                  FadeIn(self.put(r"x=2\ \mathrm{cm}", 3.5, .95, size=39, color=ACCENT, width=5.5)),
                  FadeIn(self.put(r"12-2x=8\ \mathrm{cm}", 3.5, -.05, size=37, color=CURVE, width=5.5)))
        self.mark("planar_panels_ready")
        self.focus_begin("flat_panels")
        view_driver = Group()

        def view_sample(_):
            self.sample("net_view", x_cm=2, face_order=list(FACE_ORDER),
                        screen_vertices=[face.get_vertices().tolist() for face in faces])

        view_sample(view_driver)
        view_driver.add_updater(view_sample)
        self.add(view_driver)
        target = self.panels(2, 0)
        self.beat(.12, *(Transform(face, other) for face, other in zip(faces, target, strict=True)), rate_func=linear)
        self.mark("flat_panels_ready")
        self.beat(.26)
        view_driver.clear_updaters()
        self.focus_end("flat_panels")
        driver = Group()

        def update(_):
            theta = angle.get_value()
            faces.become(self.panels(2, theta))
            self.sample("fold", x_cm=2, angle=theta, panel_vertices_cm=panel_vertices(2, theta))

        update(driver)
        driver.add_updater(update)
        self.add(driver)
        self.focus_begin("hinge_motion")
        self.beat(.62, angle.animate.set_value(math.pi/2), rate_func=linear)
        self.focus_end("hinge_motion")
        driver.clear_updaters()
        self.beat(.69, FadeIn(self.label("裁去的边长 x，折起后成为盒高", 3.5, -1.15, size=28, width=5.6)),
                  FadeIn(self.put(r"8\times8\times2\ \mathrm{cm}", 3.5, -2.15, size=37, width=5.5)))
        self.mark("fold_dimensions_ready")
        self.focus_begin("fold_dimensions")
        self.end_chapter()

    def optimize(self, cue):
        self.begin_chapter(cue)
        self.beat(.10, FadeIn(self.put(r"V=x(12-2x)^2,\quad0<x<6", 0, 2.35, size=40)))
        row1 = self.put(r"V'=(12-2x)^2-4x(12-2x)", 0, 1.35, size=40)
        row2 = self.put(r"=(12-2x)(12-6x)", 0, .35, size=40)
        row3 = self.put(r"=12(x-2)(x-6)", 0, -.65, size=42, color=RATE)
        self.beat(.22, FadeIn(row1))
        self.mark("product_derivative_ready")
        self.focus_begin("product_derivative")
        self.beat(.34)
        self.focus_end("product_derivative")
        self.beat(.43, FadeIn(row2))
        self.focus_begin("factor_derivative")
        self.beat(.55, FadeIn(row3))
        self.mark("factor_derivative_ready")
        roots = self.put(r"V'=0:\ x=2,6;\quad6\notin(0,6)", 0, -1.65, size=34, color=ACCENT)
        choice = self.label("只保留内部候选 x = 2", 0, -2.4, size=29)
        self.beat(.57, FadeIn(roots), FadeIn(choice))
        self.mark("root_candidates_ready")
        self.beat(.62)
        self.focus_end("factor_derivative")
        self.beat(.68, FadeOut(row1), FadeOut(row2), FadeOut(roots), FadeOut(choice))
        self.beat(.75, FadeIn(self.put(r"0<x<2:\ V'>0\qquad2<x<6:\ V'<0", 0, 1.2, size=37)),
                  FadeIn(self.label("体积先增后减，x = 2 在可行域内", 0, .25, size=31)),
                  FadeIn(self.put(r"V(2)=2\times8^2=128\ \mathrm{cm}^3", 0, -1.8, size=42, color=CURVE)))
        self.mark("volume_peak_ready")
        self.focus_begin("volume_peak")
        self.end_chapter()
