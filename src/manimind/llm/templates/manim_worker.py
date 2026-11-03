"""Manim Worker 的 prompt 模板 — DISPATCH 阶段生成 Manim 数学动画代码。"""

from __future__ import annotations

import json
from typing import Any

from ...render import DEFAULT_MANIM_BACKEND, ManimBackend


def build_dispatch_user_message(
    segments: list[dict[str, Any]] | None = None,
    storyboard: dict[str, Any] | None = None,
    narration: dict[str, Any] | None = None,
    formula_catalog: dict[str, Any] | None = None,
    render_backend: ManimBackend | str = DEFAULT_MANIM_BACKEND,
) -> str:
    selected_backend = ManimBackend(render_backend)
    parts: list[str] = [
        "你是一个数学科普动画的 Manim Worker。请基于分镜表、讲解脚本和公式目录，为每个 Manim/hybrid 镜头生成 Manim 动画 Python 代码。",
    ]

    if storyboard:
        parts.extend([
            "",
            "## 分镜主表",
            json.dumps(default=str, obj=storyboard, ensure_ascii=False, indent=2),
        ])

    if narration:
        parts.extend([
            "",
            "## 讲解脚本",
            json.dumps(default=str, obj=narration, ensure_ascii=False, indent=2),
        ])

    if formula_catalog:
        parts.extend([
            "",
            "## 公式目录",
            json.dumps(default=str, obj=formula_catalog, ensure_ascii=False, indent=2),
        ])

    if selected_backend is ManimBackend.MANIM_GL:
        api_requirements = [
            "2. 使用 ManimGL：`from manimlib import *`，公式用 Tex，禁止 MathTex",
            "3. 绘制使用 ShowCreation，Axes 曲线使用 axes.get_graph(...)，禁止 Create/axes.plot",
            "6. 代码应可直接运行：`manimgl scene.py SceneName -w --hd`",
        ]
    else:
        api_requirements = [
            "2. 使用 ManimCE：`from manim import *`，公式用 MathTex",
            "3. 绘制使用 Create，Axes 曲线使用 axes.plot(...) ",
            "6. 代码应可直接运行：`manim render -qh scene.py SceneName`",
        ]

    parts.extend([
        "",
        "## 任务",
        "1. 为每个 Manim/hybrid 镜头生成独立的 Manim Scene Python 代码",
        api_requirements[0],
        api_requirements[1],
        "4. 每个公式步骤之间使用 self.wait() 留出阅读时间",
        "5. 若有多个镜头，每个镜头生成独立的 Scene 类",
        api_requirements[2],
        "7. 注意颜色搭配，公式关键部分用醒目颜色高亮",
        "8. 动态数字使用 DecimalNumber/updater，禁止在 always_redraw 中创建 Tex",
    ])
    return "\n".join(parts)


def build_manim_segment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string"},
            "title": {"type": "string"},
            "scene_code": {"type": "string"},
            "scene_class_name": {"type": "string"},
            "formulas_displayed": {"type": "array", "items": {"type": "string"}},
            "animation_sequence": {"type": "array", "items": {"type": "string"}},
            "estimated_render_time_seconds": {"type": "integer"},
        },
        "required": ["segment_id", "title", "scene_code", "scene_class_name"],
        "additionalProperties": False,
    }


DISPATCH_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "manim_segments": {
            "type": "array",
            "items": build_manim_segment_schema(),
        },
        "summary": {"type": "string"},
    },
    "required": ["manim_segments"],
    "additionalProperties": False,
}
