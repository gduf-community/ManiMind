"""SVG Worker 的 prompt 模板 — DISPATCH 阶段生成 SVG 动效片段。"""

from __future__ import annotations

import json
from typing import Any


def build_dispatch_user_message(
    segments: list[dict[str, Any]] | None = None,
    storyboard: dict[str, Any] | None = None,
    narration: dict[str, Any] | None = None,
    style_guide: dict[str, Any] | None = None,
) -> str:
    parts: list[str] = [
        "你是一个数学科普动画的 SVG Worker。请基于分镜表和讲解脚本，为需要 SVG 动效的镜头生成 SVG 动画代码。",
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

    if style_guide:
        parts.extend([
            "",
            "## 风格指南",
            json.dumps(default=str, obj=style_guide, ensure_ascii=False, indent=2),
        ])

    parts.extend([
        "",
        "## 任务",
        "1. 为每个需要 SVG 动效的镜头生成 SVG + CSS/JS 动画代码",
        "2. SVG 用于图标、流程图、连接线、标注等辅助视觉元素",
        "3. 使用 CSS keyframes 或 SMIL 动画实现动效（淡入、路径绘制、变形等）",
        "4. 配色使用 style_sheet 中指定的调色板",
        "5. 生成的 SVG 片段应支持嵌入到 HTML 页面中",
        "6. 每个镜头的代码应包含完整的 SVG 标记和动画定义",
    ])
    return "\n".join(parts)


def build_svg_segment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string"},
            "title": {"type": "string"},
            "svg_code": {"type": "string"},
            "animation_type": {"type": "string"},
            "icon_elements": {"type": "array", "items": {"type": "string"}},
            "estimated_render_time_seconds": {"type": "integer"},
        },
        "required": ["segment_id", "title", "svg_code"],
        "additionalProperties": False,
    }


DISPATCH_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "svg_segments": {
            "type": "array",
            "items": build_svg_segment_schema(),
        },
        "summary": {"type": "string"},
    },
    "required": ["svg_segments"],
    "additionalProperties": False,
}
