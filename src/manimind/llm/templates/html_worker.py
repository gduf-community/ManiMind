"""HTML Worker 的 prompt 模板 — DISPATCH 阶段生成 HTML 动画片段。"""

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
        "你是一个数学科普动画的 HTML Worker。请基于分镜表和讲解脚本，为每个 HTML/hybrid 镜头生成动画页面的 HTML 代码。",
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
        "1. 为每个 HTML/hybrid 镜头生成独立的 HTML 动画页面",
        "2. 使用仿 PPT 轮播风格，增大字体，利用加粗/颜色/背景强调关键内容",
        "3. 添加页面切换动画（元素依次缓入），class 名统一使用 `an` 或 `anim-item`",
        "4. 将 emoji 替换为 Font Awesome 或 Lucide 图标库",
        "5. 在 </body> 前插入动画重置 JS：cloneNode + replaceChild 确保每次切换动画重触发",
        "6. 配色使用 style_sheet 中指定的调色板",
        "7. 每个镜头的代码应包含完整的 HTML/CSS/JS，可直接在浏览器打开",
    ])
    return "\n".join(parts)


def build_html_segment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string"},
            "title": {"type": "string"},
            "html_code": {"type": "string"},
            "template_used": {"type": "string"},
            "animation_notes": {"type": "array", "items": {"type": "string"}},
            "estimated_render_time_seconds": {"type": "integer"},
        },
        "required": ["segment_id", "title", "html_code"],
        "additionalProperties": False,
    }


DISPATCH_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "html_segments": {
            "type": "array",
            "items": build_html_segment_schema(),
        },
        "summary": {"type": "string"},
    },
    "required": ["html_segments"],
    "additionalProperties": False,
}
