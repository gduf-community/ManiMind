"""自动修复 LLM 生成的 Manim 代码中常见 API 兼容错误。"""

import re


from ..render import DEFAULT_MANIM_BACKEND, ManimBackend


COMMON_FIXES = (
    (r"\(\s*,", "("),
    (r",\s*,\s*", ", "),
    (r",\s*\)", ")"),
)

BACKEND_FIXES = {
    ManimBackend.MANIM_GL: (
        (r"\bMathTex\b", "Tex"),
        (r"\bCreate\b", "ShowCreation"),
        (r"\.plot\(", ".get_graph("),
        (r"\bx_length\s*=", "width="),
        (r"\by_length\s*=", "height="),
        (r"\btips\s*=\s*False\s*,?", ""),
        (r"\.get_horizontal_line\(", ".get_h_line("),
        (r"\.get_vertical_line\(", ".get_v_line("),
    ),
    ManimBackend.MANIM_CE: (
        (r"\bShowCreation\b", "Create"),
        (r"\.get_graph\(", ".plot("),
    ),
}


def auto_fix(
    code: str,
    *,
    backend: ManimBackend | str = DEFAULT_MANIM_BACKEND,
) -> str:
    """对 LLM 生成的 Manim 代码应用最小、可追溯的后端修复。"""
    selected_backend = ManimBackend(backend)
    fixed = code

    if selected_backend is ManimBackend.MANIM_GL:
        fixed = re.sub(r"from\s+manim\s+import", "from manimlib import", fixed)
        expected_import = "from manimlib import"
        import_line = "from manimlib import *\n"
    else:
        fixed = re.sub(r"from\s+manimlib\s+import", "from manim import", fixed)
        expected_import = "from manim import"
        import_line = "from manim import *\n"

    if expected_import not in fixed:
        fixed = import_line + fixed

    for pattern, replacement in BACKEND_FIXES[selected_backend] + COMMON_FIXES:
        fixed = re.sub(pattern, replacement, fixed)

    # 清理多余逗号管道
    fixed = fixed.replace('(,', '(')
    fixed = fixed.replace(', ,', ',')
    fixed = fixed.replace(', )', ')')

    # 检查语法
    try:
        compile(fixed, '<fix>', 'exec')
    except SyntaxError:
        pass  # 非语法错误，留给 Manim 运行时处理

    return fixed


def fix_and_save(
    input_path: str,
    output_path: str | None = None,
    *,
    backend: ManimBackend | str = DEFAULT_MANIM_BACKEND,
) -> str:
    """读取、修复并保存代码。"""
    if output_path is None:
        output_path = input_path

    with open(input_path, 'r', encoding='utf-8') as f:
        code = f.read()

    fixed = auto_fix(code, backend=backend)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(fixed)

    return fixed
