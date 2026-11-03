"""Explorer Agent 的 prompt 模板 — 四个阶段的用户消息与 JSON Schema。"""

from __future__ import annotations

import json
from typing import Any


# ============================================================================
# 用户消息构建函数
# ============================================================================


def build_prestart_user_message(env_report: dict[str, Any] | None = None) -> str:
    """构建 PRESTART 阶段的用户消息 — 环境就绪检查。

    Args:
        env_report: 环境检测报告（来自 ingest 层 EnvReport）
    """
    parts: list[str] = [
        "你是一个数学科普项目的资料探索 Agent。请基于环境检测报告，判断开发环境是否就绪。",
        "",
        "## 环境检测报告",
    ]

    if env_report:
        parts.append(json.dumps(default=str, obj=env_report, ensure_ascii=False, indent=2))
    else:
        parts.append("（未提供环境检测报告）")

    parts.extend([
        "",
        "## 任务",
        "1. 检查关键工具（python, node, manim, ffmpeg）是否可用",
        "2. 标记任何缺少或版本不兼容的工具",
        "3. 给出环境就绪状态：ok / warning / error",
        "4. 对每个 warning/error 给出修复建议",
    ])
    return "\n".join(parts)


def build_ingest_user_message(
    paper_text: str | None = None,
    notes: list[dict[str, Any]] | None = None,
    assets: dict[str, Any] | None = None,
) -> str:
    """构建 INGEST 阶段的用户消息 — 材料初步分析。

    Args:
        paper_text: 论文全文文本（来自 PDF 解析）
        notes: 笔记列表（来自 Markdown 读取）
        assets: 资产清单（来自 asset_scanner）
    """
    parts: list[str] = [
        "你是一个数学科普项目的资料探索 Agent。请对输入材料进行初步分析，提取关键信息。",
    ]

    if paper_text:
        parts.extend([
            "",
            "## 论文内容",
            paper_text[:8000],  # 限制长度，避免超 token
        ])
    else:
        parts.extend([
            "",
            "## 论文内容",
            "（论文文件未找到，请基于笔记分析）",
        ])

    if notes:
        parts.extend([
            "",
            "## 笔记",
            json.dumps(default=str, obj=notes, ensure_ascii=False, indent=2),
        ])
    else:
        parts.extend([
            "",
            "## 笔记",
            "（未提供笔记）",
        ])

    if assets:
        parts.extend([
            "",
            "## 可用资产",
            json.dumps(default=str, obj=assets, ensure_ascii=False, indent=2),
        ])
    else:
        parts.extend([
            "",
            "## 可用资产",
            "（未提供资产清单）",
        ])

    parts.extend([
        "",
        "## 任务",
        "1. 识别论文的核心主题和学科领域",
        "2. 列出论文中的关键数学概念（5-10 个），每个附一句话解释",
        "3. 判断论文难度级别（beginner / intermediate / advanced）",
        "4. 评估该主题适合的动画表现方式",
        "5. 标记论文中需要简化或特别处理的部分",
        "6. 如果论文不可用，基于笔记给出尽可能多的分析",
    ])
    return "\n".join(parts)


def build_summarize_user_message(
    paper_text: str | None = None,
    notes: list[dict[str, Any]] | None = None,
    ingest_findings: dict[str, Any] | None = None,
) -> str:
    """构建 SUMMARIZE 阶段的用户消息 — 生成研究总结、术语表、公式目录。

    Args:
        paper_text: 论文全文
        notes: 笔记列表
        ingest_findings: INGEST 阶段的初步发现
    """
    parts: list[str] = [
        "你是一个数学科普项目的资料探索 Agent。请基于以下材料生成结构化的研究总结、术语表和公式目录。",
    ]

    if paper_text:
        parts.extend([
            "",
            "## 论文内容",
            paper_text[:10000],
        ])

    if notes:
        parts.extend([
            "",
            "## 笔记",
            json.dumps(default=str, obj=notes, ensure_ascii=False, indent=2),
        ])

    if ingest_findings:
        parts.extend([
            "",
            "## INGEST 阶段初步发现",
            json.dumps(default=str, obj=ingest_findings, ensure_ascii=False, indent=2),
        ])

    parts.extend([
        "",
        "## 任务",
        "### 研究总结（research_summary）",
        "1. 概括论文核心主题（2-3 句话）",
        "2. 列出 5-10 个核心概念，每个附难度（beginner/intermediate/advanced）和是否适合可视化",
        "3. 列出 3-5 个关键发现",
        "4. 评估受众适配度：目标受众水平、需要的前置知识、需要简化的内容",
        "5. 为每个核心概念给出视觉化建议（graph/transform/comparison/3d）",
        "",
        "### 术语表（glossary）",
        "1. 为每个重要术语给出清晰定义",
        "2. 如有 LaTeX 表达式请附上",
        "3. 标注术语分类（数学/物理/计算机/其他）",
        "4. 列出相关术语的关联关系",
        "",
        "### 公式目录（formula_catalog）",
        "1. 逐个列出关键公式的完整 LaTeX 表达式",
        "2. 解释每个公式的含义",
        "3. 列出公式中每个变量的含义",
        "4. 标注公式重要性（core/supporting/optional）",
        "5. 为每个公式建议可视化方法",
    ])
    return "\n".join(parts)


def build_plan_user_message(
    segments: list[dict[str, Any]] | None = None,
    research_summary: dict[str, Any] | None = None,
    glossary: dict[str, Any] | None = None,
    formula_catalog: dict[str, Any] | None = None,
    assets: dict[str, Any] | None = None,
) -> str:
    """构建 PLAN 阶段的用户消息 — 为每个镜头检索参考资源。

    Args:
        segments: 镜头定义列表
        research_summary: 研究总结
        glossary: 术语表
        formula_catalog: 公式目录
        assets: 可用资产清单
    """
    parts: list[str] = [
        "你是一个数学科普项目的资料探索 Agent。请基于研究成果，为每个镜头匹配可用的参考资源。",
    ]

    if segments:
        parts.extend([
            "",
            "## 镜头清单",
            json.dumps(default=str, obj=segments, ensure_ascii=False, indent=2),
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
        "1. 为每个镜头匹配相关的参考资源（模板、动画模式、SVG 动效）",
        "2. 为每个镜头推荐合适的视觉风格",
        "3. 标注哪些公式适合在该镜头中展示",
        "4. 列出该镜头可能需要的额外参考（如特殊动画技术）",
        "5. 标记任何资源缺口（当前 assets 中缺少但可能需要的）",
    ])
    return "\n".join(parts)


# ============================================================================
# JSON Schema — 用于 chat_structured 约束输出格式
# ============================================================================


RESEARCH_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "paper_available": {"type": "boolean"},
        "paper_title": {"type": "string"},
        "core_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "difficulty": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "advanced"],
                    },
                    "visualizable": {"type": "boolean"},
                },
                "required": ["name", "description", "difficulty", "visualizable"],
                "additionalProperties": False,
            },
        },
        "key_findings": {
            "type": "array",
            "items": {"type": "string"},
        },
        "audience_assessment": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "advanced"],
                },
                "prerequisites": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "simplification_needed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["level", "prerequisites", "simplification_needed"],
            "additionalProperties": False,
        },
        "visual_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "visual_type": {
                        "type": "string",
                        "enum": ["graph", "transform", "comparison", "3d"],
                    },
                    "notes": {"type": "string"},
                },
                "required": ["concept", "visual_type", "notes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["paper_available", "core_concepts", "key_findings", "audience_assessment"],
    "additionalProperties": False,
}


GLOSSARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "definition": {"type": "string"},
                    "latex": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["数学", "物理", "计算机", "其他"],
                    },
                    "related_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["term", "definition", "category"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["terms"],
    "additionalProperties": False,
}


FORMULA_CATALOG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "formulas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "latex": {"type": "string"},
                    "description": {"type": "string"},
                    "variables": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["core", "supporting", "optional"],
                    },
                    "visual_approach": {"type": "string"},
                },
                "required": ["id", "latex", "description", "importance"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["formulas"],
    "additionalProperties": False,
}


# SUMMARIZE 阶段的聚合输出
SUMMARIZE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "research_summary": RESEARCH_SUMMARY_SCHEMA,
        "glossary": GLOSSARY_SCHEMA,
        "formula_catalog": FORMULA_CATALOG_SCHEMA,
    },
    "required": ["research_summary", "glossary", "formula_catalog"],
    "additionalProperties": False,
}


# PLAN 阶段的参考匹配输出
PLAN_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "segment_references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string"},
                    "matched_assets": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "recommended_style": {"type": "string"},
                    "formulas_to_show": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "pattern_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "resource_gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["segment_id", "matched_assets", "recommended_style"],
                "additionalProperties": False,
            },
        },
        "overall_recommendations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["segment_references"],
    "additionalProperties": False,
}


# INGEST 阶段的初步分析输出
INGEST_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "subject_area": {"type": "string"},
        "identified_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name", "description"],
                "additionalProperties": False,
            },
        },
        "difficulty_level": {
            "type": "string",
            "enum": ["beginner", "intermediate", "advanced"],
        },
        "animation_suitability": {"type": "string"},
        "sections_needing_simplification": {
            "type": "array",
            "items": {"type": "string"},
        },
        "paper_unavailable": {"type": "boolean"},
    },
    "required": ["domain", "identified_concepts", "difficulty_level"],
    "additionalProperties": False,
}


# PRESTART 阶段的环境就绪输出
PRESTART_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "overall_status": {
            "type": "string",
            "enum": ["ok", "warning", "error"],
        },
        "tool_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "available": {"type": "boolean"},
                    "version": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["ok", "warning", "error"],
                    },
                    "fix_suggestion": {"type": "string"},
                },
                "required": ["tool", "available", "status"],
                "additionalProperties": False,
            },
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["overall_status", "tool_checks", "warnings"],
    "additionalProperties": False,
}
