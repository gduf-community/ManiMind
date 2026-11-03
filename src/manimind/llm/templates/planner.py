"""Planner Agent 的 prompt 模板 — SUMMARIZE 和 PLAN 两个阶段的用户消息与 JSON Schema。"""

from __future__ import annotations

import json
from typing import Any


# ============================================================================
# 用户消息构建函数
# ============================================================================


def build_summarize_user_message(
    research_summary: dict[str, Any] | None = None,
    glossary: dict[str, Any] | None = None,
    formula_catalog: dict[str, Any] | None = None,
    style_guide: dict[str, Any] | None = None,
) -> str:
    """构建 SUMMARIZE 阶段的用户消息 — 约束分析。

    Args:
        research_summary: Explorer 生成的研究总结
        glossary: 术语表
        formula_catalog: 公式目录
        style_guide: 风格指南（受众画像、视觉规范）
    """
    parts: list[str] = [
        "你是一个数学科普项目的方案规划 Agent。请基于已有的研究总结，分析约束并提出建议。",
    ]

    if research_summary:
        parts.extend([
            "",
            "## 研究总结",
            json.dumps(default=str, obj=research_summary, ensure_ascii=False, indent=2),
        ])
    else:
        parts.extend([
            "",
            "## 研究总结",
            "（未提供研究总结）",
        ])

    if glossary:
        parts.extend([
            "",
            "## 术语表",
            json.dumps(default=str, obj=glossary, ensure_ascii=False, indent=2),
        ])
    else:
        parts.extend([
            "",
            "## 术语表",
            "（未提供术语表）",
        ])

    if formula_catalog:
        parts.extend([
            "",
            "## 公式目录",
            json.dumps(default=str, obj=formula_catalog, ensure_ascii=False, indent=2),
        ])
    else:
        parts.extend([
            "",
            "## 公式目录",
            "（未提供公式目录）",
        ])

    if style_guide:
        parts.extend([
            "",
            "## 风格指南",
            json.dumps(default=str, obj=style_guide, ensure_ascii=False, indent=2),
        ])
    else:
        parts.extend([
            "",
            "## 风格指南",
            "（未提供风格指南）",
        ])

    parts.extend([
        "",
        "## 任务",
        "1. **数学难度与受众匹配度分析**：",
        "   - 评估当前内容对目标受众的难度级别",
        "   - 指出哪些概念需要简化或额外解释",
        "   - 给出适配建议",
        "",
        "2. **时间估算**：",
        "   - 为每个核心概念估算讲解所需的最短时长（秒）",
        "   - 考虑动画表现所需的额外时间",
        "",
        "3. **媒介选择建议**：",
        "   - 标注哪些概念适合 HTML 动画（交互、转场）",
        "   - 标注哪些需要 Manim 数学动画（公式推导、几何变换）",
        "   - 标注哪些适合 SVG 动效（图标、流程图）",
        "   - 说明选择理由",
        "",
        "4. **风险点标记**：",
        "   - 列出潜在的难点或容易出错的地方",
        "   - 给出替代方案或缓解策略",
        "",
        "5. **整体可行性评估**：",
        "   - 给出总体可行性评分（1-5）",
        "   - 列出关键成功因素",
        "   - 列出主要挑战",
    ])
    return "\n".join(parts)


def build_plan_user_message(
    segments: list[dict[str, Any]] | None = None,
    constraint_analysis: dict[str, Any] | None = None,
    research_summary: dict[str, Any] | None = None,
    glossary: dict[str, Any] | None = None,
    formula_catalog: dict[str, Any] | None = None,
    assets: dict[str, Any] | None = None,
) -> str:
    """构建 PLAN 阶段的用户消息 — 分镜建议。

    Args:
        segments: 镜头定义列表
        constraint_analysis: SUMMARIZE 阶段的约束分析结果
        research_summary: 研究总结
        glossary: 术语表
        formula_catalog: 公式目录
        assets: 可用资产清单
    """
    parts: list[str] = [
        "你是一个数学科普项目的方案规划 Agent。请基于约束分析和镜头定义，生成分镜建议。",
    ]

    if segments:
        parts.extend([
            "",
            "## 镜头清单",
            json.dumps(default=str, obj=segments, ensure_ascii=False, indent=2),
        ])
    else:
        parts.extend([
            "",
            "## 镜头清单",
            "（未提供镜头定义）",
        ])

    if constraint_analysis:
        parts.extend([
            "",
            "## 约束分析结果",
            json.dumps(default=str, obj=constraint_analysis, ensure_ascii=False, indent=2),
        ])
    else:
        parts.extend([
            "",
            "## 约束分析结果",
            "（未提供约束分析）",
        ])

    if research_summary:
        parts.extend([
            "",
            "## 研究总结",
            json.dumps(default=str, obj=research_summary, ensure_ascii=False, indent=2),
        ])

    if glossary:
        parts.extend([
            "",
            "## 术语表",
            json.dumps(default=str, obj=glossary, ensure_ascii=False, indent=2),
        ])

    if formula_catalog:
        parts.extend([
            "",
            "## 公式目录",
            json.dumps(default=str, obj=formula_catalog, ensure_ascii=False, indent=2),
        ])

    if assets:
        parts.extend([
            "",
            "## 可用资产",
            json.dumps(default=str, obj=assets, ensure_ascii=False, indent=2),
        ])

    parts.extend([
        "",
        "## 任务",
        "为每个镜头生成分镜建议，包括：",
        "",
        "1. **镜头顺序优化**：",
        "   - 建议的逻辑顺序（如有调整需说明理由）",
        "   - 镜头间的过渡方式",
        "",
        "2. **每个镜头的详细规划**：",
        "   - 重点强调的核心概念",
        "   - 建议的 modality（html/manim/hybrid/svg）及理由",
        "   - 预计时长（秒）",
        "   - 需要展示的公式（LaTeX）",
        "   - 动画备注（如何可视化这个概念）",
        "   - 叙事要点（如何讲解）",
        "",
        "3. **资源匹配**：",
        "   - 为每个镜头推荐可用的参考资产",
        "   - 说明如何使用这些资产",
        "",
        "4. **整体节奏建议**：",
        "   - 开头如何吸引注意力",
        "   - 中间如何保持观众兴趣",
        "   - 结尾如何总结和强化记忆",
    ])
    return "\n".join(parts)


# ============================================================================
# JSON Schema 定义
# ============================================================================


SUMMARIZE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["constraint_analysis", "feasibility_assessment"],
    "properties": {
        "constraint_analysis": {
            "type": "object",
            "required": [
                "audience_match",
                "time_estimates",
                "modality_recommendations",
                "risk_points",
            ],
            "properties": {
                "audience_match": {
                    "type": "object",
                    "required": ["difficulty_level", "simplification_needed", "recommendations"],
                    "properties": {
                        "difficulty_level": {
                            "type": "string",
                            "enum": ["beginner", "intermediate", "advanced"],
                            "description": "内容对目标受众的整体难度级别",
                        },
                        "simplification_needed": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["concept", "reason", "suggestion"],
                                "properties": {
                                    "concept": {"type": "string"},
                                    "reason": {"type": "string"},
                                    "suggestion": {"type": "string"},
                                },
                            },
                            "description": "需要简化的概念列表",
                        },
                        "recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "受众适配建议",
                        },
                    },
                },
                "time_estimates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["concept", "min_seconds", "recommended_seconds"],
                        "properties": {
                            "concept": {"type": "string"},
                            "min_seconds": {"type": "integer", "minimum": 5},
                            "recommended_seconds": {"type": "integer", "minimum": 10},
                        },
                    },
                    "description": "每个核心概念的时间估算",
                },
                "modality_recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["concept", "recommended_modality", "reason"],
                        "properties": {
                            "concept": {"type": "string"},
                            "recommended_modality": {
                                "type": "string",
                                "enum": ["html", "manim", "hybrid", "svg"],
                            },
                            "reason": {"type": "string"},
                        },
                    },
                    "description": "媒介选择建议",
                },
                "risk_points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["risk", "severity", "mitigation"],
                        "properties": {
                            "risk": {"type": "string"},
                            "severity": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "mitigation": {"type": "string"},
                        },
                    },
                    "description": "潜在风险点",
                },
            },
        },
        "feasibility_assessment": {
            "type": "object",
            "required": ["overall_score", "success_factors", "challenges"],
            "properties": {
                "overall_score": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "总体可行性评分（1-5）",
                },
                "success_factors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关键成功因素",
                },
                "challenges": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "主要挑战",
                },
            },
        },
    },
}


PLAN_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["storyboard_suggestions"],
    "properties": {
        "storyboard_suggestions": {
            "type": "object",
            "required": ["segment_order", "segments", "pacing_advice"],
            "properties": {
                "segment_order": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "建议的镜头顺序（segment_id 列表）",
                },
                "segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "segment_id",
                            "key_concepts",
                            "modality",
                            "estimated_seconds",
                            "formulas",
                            "animation_notes",
                            "narration_points",
                            "asset_references",
                        ],
                        "properties": {
                            "segment_id": {
                                "type": "string",
                                "description": "镜头 ID",
                            },
                            "key_concepts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "该镜头的重点概念",
                            },
                            "modality": {
                                "type": "string",
                                "enum": ["html", "manim", "hybrid", "svg"],
                                "description": "建议的媒介类型",
                            },
                            "estimated_seconds": {
                                "type": "integer",
                                "minimum": 5,
                                "description": "预计时长（秒）",
                            },
                            "formulas": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "需要展示的 LaTeX 公式",
                            },
                            "animation_notes": {
                                "type": "string",
                                "description": "动画表现建议",
                            },
                            "narration_points": {
                                "type": "string",
                                "description": "叙事要点",
                            },
                            "asset_references": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["asset_path", "usage_description"],
                                    "properties": {
                                        "asset_path": {"type": "string"},
                                        "usage_description": {"type": "string"},
                                    },
                                },
                                "description": "推荐的参考资产",
                            },
                        },
                    },
                    "description": "每个镜头的详细规划",
                },
                "pacing_advice": {
                    "type": "object",
                    "required": ["opening", "middle", "closing"],
                    "properties": {
                        "opening": {
                            "type": "string",
                            "description": "开头如何吸引注意力",
                        },
                        "middle": {
                            "type": "string",
                            "description": "中间如何保持观众兴趣",
                        },
                        "closing": {
                            "type": "string",
                            "description": "结尾如何总结和强化记忆",
                        },
                    },
                    "description": "整体节奏建议",
                },
            },
        },
    },
}
