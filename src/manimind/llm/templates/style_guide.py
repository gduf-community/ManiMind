"""3B1B-inspired visual style guide for Manim code generation.

This module provides reusable style specifications extracted from professional
math education videos. Embed these prompts into LLM code generation to produce
visually consistent, high-quality animations.
"""

from ...render import DEFAULT_MANIM_BACKEND, ManimBackend

# ============================================================================
# Core Style Profile
# ============================================================================

STYLE_PROFILE = {
    "color_scheme": {
        "background": "BLACK",
        "primary_text": "WHITE",
        "accent_1": "BLUE",       # curves, main graphics
        "accent_2": "YELLOW",     # highlights, labels
        "accent_3": "GREEN",      # tangents, emphasis
        "warning": "RED",         # errors, important points
        "subtle": "GRAY",         # grid lines, axes
        "fill": "BLUE",           # area shading
        "fill_opacity": 0.3,
    },
    "layout": {
        "title_position": "TOP",
        "formula_position": "BOTTOM_LEFT",
        "graph_region": "CENTER",
        "annotation_position": "BOTTOM",
        "max_elements_per_frame": 3,
    },
    "typography": {
        "title_size": 42,
        "formula_size": 36,
        "annotation_size": 24,
        "axis_label_size": 28,
        "font": "SimHei",         # Chinese font
    },
    "animation": {
        "write_speed": 1.0,
        "wait_after_key_point": 2.0,
        "transition_duration": 1.5,
        "use_arrows": True,
        "use_highlights": True,
    }
}


# ============================================================================
# Prompt Template — inject into LLM code generation
# ============================================================================

STYLE_INJECTION_PROMPT = """
【视觉风格要求 — 参考 3Blue1Brown/漫士沉思录】

1. 配色：黑色背景，白色文字，蓝色曲线，黄色高亮关键点，绿色标注切线/重点
   实现: self.camera.background_color = BLACK
   Axes用GRAY，曲线用BLUE(stroke_width=4)，切点用YELLOW，切线用GREEN

2. 布局：标题放顶部(42号字体)，公式放左下角(36号)，图形占中央区域，注释放底部(24号)
   实现: title.to_edge(UP), formula.to_corner(DL), annotation.to_edge(DOWN)

3. 层次：每帧2-3个核心元素，不堆砌。重要结论用大字号+高亮色
   实现: 先展示标题和图形，再缓缓出现公式，最后出现注释

4. 引导视线：用箭头/虚线标注关键位置，用半透明填充强调区域
   实现: Arrow(起点, 终点, color=YELLOW), Rectangle(..., fill_color=BLUE, fill_opacity=0.3)

5. 动态演示：公式和图形通过逐笔绘制渐入，不是突然出现

6. 字体：中文用SimHei，数学公式用LaTeX对象，字号足够大
   实现: Text("标题", font="SimHei", color=WHITE).to_edge(UP)
"""


MANIMGL_API_PROMPT = """
【ManimGL API 硬约束】
- 首行使用 `from manimlib import *`，禁止导入 `manim`
- 数学公式使用 `Tex`，禁止使用不存在的 `MathTex`
- 绘制动画使用 `ShowCreation`，禁止使用不存在的 `Create`
- Axes 曲线使用 `axes.get_graph(...)`，不要使用 ManimCE 的 `axes.plot(...)`
- 可使用 ManimGL 的 `always_redraw`、updater、相机与 shader 能力增强连续运动
- 禁止在 `always_redraw` 中创建 Tex；动态数值使用 `DecimalNumber` 和 updater
"""


MANIMCE_API_PROMPT = """
【ManimCE API 硬约束】
- 首行使用 `from manim import *`
- 数学公式使用 `MathTex`
- 绘制动画使用 `Create`
- Axes 曲线使用 `axes.plot(...)`
"""


def get_style_prompt(
    backend: ManimBackend | str = DEFAULT_MANIM_BACKEND,
) -> str:
    """Return the full style injection prompt for LLM code generation."""
    selected_backend = ManimBackend(backend)
    api_prompt = (
        MANIMGL_API_PROMPT
        if selected_backend is ManimBackend.MANIM_GL
        else MANIMCE_API_PROMPT
    )
    return STYLE_INJECTION_PROMPT + api_prompt


def build_styled_prompt(
    base_prompt: str,
    backend: ManimBackend | str = DEFAULT_MANIM_BACKEND,
) -> str:
    """Wrap a base prompt with style guide requirements."""
    return base_prompt + "\n\n" + get_style_prompt(backend)


# ============================================================================
# Quality Review Checklist — for Kimi vision comparison
# ============================================================================

REVIEW_CHECKLIST = """
请按以下维度评分(1-10):

1. 配色方案: 是否使用黑色背景+白色文字+蓝色曲线+黄色高亮
2. 布局规律: 标题/公式/图形/注释是否各就其位
3. 信息密度: 每帧是否有2-3个关键元素
4. 视觉引导: 是否有箭头/虚线/高亮标注
5. 动画流畅度: 元素是否渐入而非突然出现
6. 字体排版: 中文是否清晰，公式是否使用LaTeX

总评: [分数]/60
需要改进的1-2点:
"""
