"""Small native ManimGL scene used to verify the rendering backend."""

from manimlib import *


class ManimGLBackendSmoke(Scene):
    def construct(self):
        title = Text("Derivative as local slope", font_size=42, color=WHITE)
        title.to_edge(UP)
        subtitle = Text("One point moves; the tangent responds", font_size=24, color=GREY_B)
        subtitle.next_to(title, DOWN, buff=0.2)

        axes = Axes(
            x_range=(-4, 4, 1),
            y_range=(-2, 4, 1),
            width=10,
            height=5,
            axis_config={"stroke_color": GREY_B, "stroke_width": 2},
        ).shift(DOWN * 0.5)
        graph = axes.get_graph(
            lambda x: 0.35 * x * x - 1,
            x_range=(-3.4, 3.4),
            color=BLUE,
            stroke_width=5,
        )
        formula = Tex(
            r"f(x)=0.35x^2-1",
            tex_to_color_map={r"f(x)": BLUE, r"x": YELLOW},
        ).scale(0.7)
        formula.to_corner(DL).shift(UP * 0.35)

        tracker = ValueTracker(-2.4)

        def graph_point():
            x = tracker.get_value()
            return axes.c2p(x, 0.35 * x * x - 1)

        def tangent_line():
            x = tracker.get_value()
            y = 0.35 * x * x - 1
            slope = 0.7 * x
            dx = 1.15
            return Line(
                axes.c2p(x - dx, y - slope * dx),
                axes.c2p(x + dx, y + slope * dx),
                color=GREEN,
                stroke_width=5,
            )

        def focus_band():
            band = Rectangle(
                width=1.15,
                height=4.8,
                stroke_width=0,
                fill_color=BLUE_D,
                fill_opacity=0.16,
            )
            band.move_to(axes.get_center())
            band.set_x(graph_point()[0])
            return band

        focus = always_redraw(focus_band)
        projection = always_redraw(
            lambda: DashedLine(
                axes.c2p(tracker.get_value(), 0),
                graph_point(),
                color=YELLOW,
                stroke_width=2,
            )
        )
        dot = always_redraw(lambda: Dot(graph_point(), color=YELLOW, radius=0.09))
        tangent = always_redraw(tangent_line)
        label = Text("local slope", font_size=25, color=GREEN)
        label.to_corner(DR).shift(UP * 0.45)
        swatch = Line(LEFT * 0.35, RIGHT * 0.35, color=GREEN, stroke_width=5)
        swatch.next_to(label, LEFT, buff=0.18)

        self.play(Write(title), FadeIn(subtitle), run_time=1.2)
        self.play(ShowCreation(axes), ShowCreation(graph), Write(formula), run_time=2.2)
        self.play(
            FadeIn(focus),
            ShowCreation(projection),
            FadeIn(dot),
            ShowCreation(tangent),
            FadeIn(label),
            FadeIn(swatch),
            run_time=1.2,
        )
        self.play(tracker.animate.set_value(2.4), run_time=4.0, rate_func=smooth)
        self.wait(1)
