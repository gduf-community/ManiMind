"""Coordinator Agent 的 prompt 模板 — PLAN 和 DISPATCH 阶段。"""

from __future__ import annotations

import json
from typing import Any


def build_plan_user_message(
    segments: list[dict[str, Any]],
    research_summary: dict[str, Any] | None = None,
    planner_suggestions: dict[str, Any] | None = None,
) -> str:
    """构建 PLAN 阶段的用户消息。

    Args:
        segments: 镜头定义列表（来自 manifest）
        research_summary: Explorer 产出的研究总结建议稿
        planner_suggestions: Planner 产出的约束分析 + 分镜建议
    """
    parts: list[str] = [
        "你是一个数学科普项目的协调 Agent。请基于研究总结和规划建议，生成讲解脚本和分镜表。",
        "",
        "## 镜头清单",
        json.dumps(default=str, obj=segments, ensure_ascii=False, indent=2),
    ]

    if research_summary:
        parts.extend([
            "",
            "## 研究总结",
            json.dumps(default=str, obj=research_summary, ensure_ascii=False, indent=2),
        ])

    if planner_suggestions:
        parts.extend([
            "",
            "## 规划建议",
            json.dumps(default=str, obj=planner_suggestions, ensure_ascii=False, indent=2),
        ])

    parts.extend([
        "",
        "## 任务",
        "1. 为每个镜头写讲解词（口语化，适合配音，每个镜头 2-5 句）",
        "2. 确定每个镜头的 modality（html/manim/hybrid/svg）",
        "3. 列出每个镜头的公式、动画备注、预计时长",
        "4. 生成完整分镜表（含镜头顺序、转场建议、叙事节奏）",
        "5. 评估总体时长是否合理",
    ])
    return "\n".join(parts)


def build_dispatch_user_message(
    storyboard: dict[str, Any] | None = None,
    segments: list[dict[str, Any]] | None = None,
) -> str:
    """构建 DISPATCH 阶段的用户消息。

    Args:
        storyboard: Coordinator PLAN 阶段产出的分镜主表
        segments: 原始镜头定义
    """
    parts: list[str] = [
        "你是一个数学科普项目的协调 Agent。请基于已批准的分镜表，分发任务给下游 Worker 并生成会话交接。",
    ]

    if storyboard:
        parts.extend([
            "",
            "## 分镜主表",
            json.dumps(default=str, obj=storyboard, ensure_ascii=False, indent=2),
        ])

    if segments:
        parts.extend([
            "",
            "## 原始镜头定义",
            json.dumps(default=str, obj=segments, ensure_ascii=False, indent=2),
        ])

    parts.extend([
        "",
        "## 任务",
        "1. 为每个镜头分配 Worker（html/manim/svg），生成具体任务描述",
        "2. 确定任务间的依赖关系",
        "3. 生成本次会话交接记录（session.handoff）",
        "4. 列出下游 Worker 需要的所有上下文信息",
        "5. 标记任何需要特别关注的风险点",
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# JSON Schema — 用于 chat_structured 约束输出格式
# ---------------------------------------------------------------------------

NARRATION_SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string"},
                    "title": {"type": "string"},
                    "narration_text": {"type": "string"},
                    "timing_hints": {
                        "type": "object",
                        "properties": {
                            "estimated_seconds": {"type": "integer"},
                            "pause_after": {"type": "integer"},
                        },
                        "required": ["estimated_seconds"],
                        "additionalProperties": False,
                    },
                    "emphasis": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "formulas_in_context": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "latex": {"type": "string"},
                                "spoken_form": {"type": "string"},
                                "display_timing": {
                                    "type": "string",
                                    "enum": ["before_narration", "during_narration", "after_narration"],
                                },
                            },
                            "required": ["latex", "spoken_form", "display_timing"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["segment_id", "title", "narration_text", "timing_hints"],
                "additionalProperties": False,
            },
        },
        "voiceover_notes": {
            "type": "object",
            "properties": {
                "style": {"type": "string"},
                "tone": {"type": "string"},
                "total_estimated_duration_seconds": {"type": "integer"},
            },
            "required": ["style", "tone", "total_estimated_duration_seconds"],
            "additionalProperties": False,
        },
    },
    "required": ["segments", "voiceover_notes"],
    "additionalProperties": False,
}

STORYBOARD_MASTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string"},
                    "title": {"type": "string"},
                    "order": {"type": "integer"},
                    "modality": {
                        "type": "string",
                        "enum": ["html", "manim", "hybrid", "svg"],
                    },
                    "estimated_seconds": {"type": "integer"},
                    "goal": {"type": "string"},
                    "formulas": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "animation_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "visual_references": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "html_motion_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "requires_svg_motion": {"type": "boolean"},
                    "worker_tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "worker": {
                                    "type": "string",
                                    "enum": ["html", "manim", "svg"],
                                },
                                "task_id": {"type": "string"},
                                "objective": {"type": "string"},
                            },
                            "required": ["worker", "task_id", "objective"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "segment_id", "title", "order", "modality",
                    "estimated_seconds", "goal", "worker_tasks",
                ],
                "additionalProperties": False,
            },
        },
        "style_sheet": {
            "type": "object",
            "properties": {
                "color_palette": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "font_scale": {"type": "string"},
                "animation_pacing": {"type": "string"},
            },
            "required": ["color_palette", "font_scale", "animation_pacing"],
            "additionalProperties": False,
        },
    },
    "required": ["segments", "style_sheet"],
    "additionalProperties": False,
}

SESSION_HANDOFF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "session_summary": {"type": "string"},
        "completed_tasks": {
            "type": "array",
            "items": {"type": "string"},
        },
        "pending_tasks": {
            "type": "array",
            "items": {"type": "string"},
        },
        "blockers": {
            "type": "array",
            "items": {"type": "string"},
        },
        "notes_for_workers": {
            "type": "object",
            "properties": {
                "html_worker": {"type": "string"},
                "manim_worker": {"type": "string"},
                "svg_worker": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "review_checkpoints": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["session_summary", "completed_tasks", "pending_tasks", "notes_for_workers"],
    "additionalProperties": False,
}

PLAN_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "narration_script": NARRATION_SCRIPT_SCHEMA["type"] == "object" and NARRATION_SCRIPT_SCHEMA or {},
        "storyboard_master": STORYBOARD_MASTER_SCHEMA["type"] == "object" and STORYBOARD_MASTER_SCHEMA or {},
    },
    "required": ["narration_script", "storyboard_master"],
    "additionalProperties": False,
}
# Fix: build the aggregate schemas properly
PLAN_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "narration_script": NARRATION_SCRIPT_SCHEMA,
        "storyboard_master": STORYBOARD_MASTER_SCHEMA,
    },
    "required": ["narration_script", "storyboard_master"],
    "additionalProperties": False,
}

DISPATCH_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task_assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "worker": {"type": "string"},
                    "segment_id": {"type": "string"},
                    "objective": {"type": "string"},
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["task_id", "worker", "segment_id", "objective"],
                "additionalProperties": False,
            },
        },
        "session_handoff": SESSION_HANDOFF_SCHEMA,
    },
    "required": ["task_assignments", "session_handoff"],
    "additionalProperties": False,
}
