from manimind.review import assess_manim_code_quality


def test_assess_manim_code_quality_blocks_bare_formula() -> None:
    finding = assess_manim_code_quality(
        {
            "segment_id": "seg-1",
            "scene_code": (
                "from manim import *\n"
                "class Bare(Scene):\n"
                "    def construct(self):\n"
                "        self.play(Write(MathTex(r'E=mc^2')))\n"
            ),
        },
        formula_required=True,
    )

    assert finding.status == "block"
    assert any("visual anchor" in issue for issue in finding.issues)
    assert any("reading pause" in issue for issue in finding.issues)


def test_assess_manim_code_quality_passes_staged_visual_scene() -> None:
    code = """
from manim import *

class Staged(Scene):
    def construct(self):
        self.camera.background_color = "#1C1C1C"
        axes = Axes(x_range=[0, 5], y_range=[0, 10], tips=False)
        graph = axes.plot(lambda x: x**2, color=BLUE)
        dot = Dot(axes.c2p(2, 4), color=YELLOW)
        tracker = ValueTracker(0)
        label = MathTex(r"f'(2)=4", color=GREEN).to_edge(DOWN)
        self.play(Create(axes), run_time=1.0)
        self.play(Create(graph), FadeIn(dot), run_time=2.0)
        self.play(tracker.animate.set_value(1), Write(label), run_time=2.0)
        self.wait(1)
"""

    finding = assess_manim_code_quality(
        {"segment_id": "seg-1", "scene_code": code},
        formula_required=True,
    )

    assert finding.status == "pass"
    assert finding.issues == []


def test_assess_manim_code_quality_accepts_native_manimgl_scene() -> None:
    code = """
from manimlib import *

class StagedGL(Scene):
    def construct(self):
        axes = Axes(x_range=(-3, 3, 1), y_range=(-1, 5, 1))
        graph = axes.get_graph(lambda x: x**2, color=BLUE)
        dot = Dot(axes.c2p(1, 1), color=YELLOW)
        tracker = ValueTracker(0)
        formula = Tex(r"f(x)=x^2", tex_to_color_map={r"x": GREEN})
        self.play(ShowCreation(axes), run_time=1)
        self.play(ShowCreation(graph), FadeIn(dot), run_time=2)
        self.play(tracker.animate.set_value(1), Write(formula), run_time=2)
        self.wait(1)
"""

    finding = assess_manim_code_quality(
        {"segment_id": "seg-gl", "scene_code": code},
        formula_required=True,
    )

    assert finding.status == "pass"
    assert finding.issues == []


def test_assess_manim_code_quality_blocks_tex_inside_always_redraw() -> None:
    code = """
from manimlib import *

class SlowFormula(Scene):
    def construct(self):
        axes = Axes()
        graph = axes.get_graph(lambda x: x, color=BLUE)
        tracker = ValueTracker(0)
        dot = Dot(color=YELLOW)
        value = always_redraw(lambda: Tex(fr"x={tracker.get_value():.2f}", color=GREEN))
        self.play(ShowCreation(axes), ShowCreation(graph))
        self.play(FadeIn(dot), Write(value))
        self.play(tracker.animate.set_value(1), run_time=2)
        self.wait(1)
"""

    finding = assess_manim_code_quality(
        {"segment_id": "seg-slow", "scene_code": code},
        formula_required=True,
    )

    assert finding.status == "block"
    assert any("per-frame LaTeX" in issue for issue in finding.issues)
