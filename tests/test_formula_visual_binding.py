from manimind.review import assess_formula_visual_binding


def test_formula_visual_binding_blocks_bare_derivative_formula() -> None:
    finding = assess_formula_visual_binding(
        {
            "segment_id": "seg-1",
            "scene_code": (
                "from manim import *\n"
                "class Bare(Scene):\n"
                "    def construct(self):\n"
                "        eq = MathTex(r\"f'(x)=2x\")\n"
                "        self.play(Write(eq))\n"
                "        self.wait(1)\n"
            ),
        },
        [r"f'(x)=2x"],
    )

    assert finding.status == "block"
    assert any("visual companion" in issue for issue in finding.issues)


def test_formula_visual_binding_passes_derivative_with_graph_point_and_line() -> None:
    code = """
from manim import *
class Bound(Scene):
    def construct(self):
        axes = Axes()
        graph = axes.plot(lambda x: x**2)
        point = Dot(axes.c2p(2, 4), color=YELLOW)
        tangent = Line(axes.c2p(1, 2), axes.c2p(3, 6), color=GREEN)
        eq = MathTex(r"f'(2)=4")
        self.play(Create(axes), Create(graph))
        self.play(FadeIn(point), Create(tangent), Write(eq))
        self.wait(1)
"""

    finding = assess_formula_visual_binding(
        {"segment_id": "seg-1", "scene_code": code},
        [r"f'(2)=4"],
    )

    assert finding.status == "pass"
    assert "graph" in finding.visual_companions
    assert "point" in finding.visual_companions
