from manimind.agents.code_fixer import auto_fix
from manimind.render import ManimBackend


def test_auto_fix_targets_manimgl_by_default() -> None:
    code = """from manim import *
class Demo(Scene):
    def construct(self):
        axes = Axes(x_length=8, y_length=4, tips=False)
        graph = axes.plot(lambda x: x)
        guide = axes.get_horizontal_line(axes.c2p(1, 1))
        formula = MathTex(r"f(x)=x")
        self.play(Create(graph), Write(formula))
"""

    fixed = auto_fix(code)

    assert "from manimlib import *" in fixed
    assert "axes.get_graph" in fixed
    assert "Axes(width=8, height=4)" in fixed
    assert "tips=" not in fixed
    assert "axes.get_h_line" in fixed
    assert "Tex(" in fixed
    assert "ShowCreation(" in fixed
    assert "MathTex(" not in fixed


def test_auto_fix_can_target_manimce() -> None:
    code = """from manimlib import *
class Demo(Scene):
    def construct(self):
        axes = Axes()
        graph = axes.get_graph(lambda x: x)
        self.play(ShowCreation(graph))
"""

    fixed = auto_fix(code, backend=ManimBackend.MANIM_CE)

    assert "from manim import *" in fixed
    assert "axes.plot" in fixed
    assert "Create(graph)" in fixed
