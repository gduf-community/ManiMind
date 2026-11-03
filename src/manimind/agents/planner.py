"""Planner Agent — 方案规划、约束分析、分镜建议生成。"""

from __future__ import annotations

from typing import Any

from ..llm.templates.planner import (
    PLAN_OUTPUT_SCHEMA,
    SUMMARIZE_OUTPUT_SCHEMA,
    build_plan_user_message,
    build_summarize_user_message,
)
from ..models import ContextScope, PipelineStage
from .base import BaseAgent


class PlannerAgent(BaseAgent):
    """方案规划 Agent — 只读角色。

    负责两个阶段的工作:

    SUMMARIZE:
        - 分析研究总结、术语表、公式目录
        - 评估数学难度与受众匹配度
        - 估算时间、推荐媒介、标记风险点
        - 输出: constraint_analysis + feasibility_assessment → 短期上下文

    PLAN:
        - 基于约束分析和镜头定义生成分镜建议
        - 优化镜头顺序、详细规划每个镜头
        - 给出整体节奏建议
        - 输出: storyboard_suggestions → 短期上下文
    """

    role_id = "planner"

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def run(self, stage: PipelineStage, task_id: str, **kwargs: Any) -> dict[str, Any]:
        if stage == PipelineStage.SUMMARIZE:
            return self._run_summarize(task_id, **kwargs)
        if stage == PipelineStage.PLAN:
            return self._run_plan(task_id, **kwargs)
        return {
            "success": False,
            "task_id": task_id,
            "error": f"Planner does not support stage: {stage.value}",
        }

    # ------------------------------------------------------------------
    # SUMMARIZE — 约束分析
    # ------------------------------------------------------------------

    def _run_summarize(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        pid = self.plan.project_id

        # 从 kwargs 或 runtime 读取输入
        research_summary = kwargs.get("research_summary") or self._read_context(
            f"{pid}.research.summary"
        )
        glossary = kwargs.get("glossary") or self._read_context(f"{pid}.glossary")
        formula_catalog = kwargs.get("formula_catalog") or self._read_context(
            f"{pid}.formula.catalog"
        )
        style_guide = kwargs.get("style_guide") or self._read_context(f"{pid}.style.guide")

        user_message = build_summarize_user_message(
            research_summary=research_summary,
            glossary=glossary,
            formula_catalog=formula_catalog,
            style_guide=style_guide,
        )
        system_prompt = self._build_system_prompt_text(PipelineStage.SUMMARIZE)

        try:
            llm = self._require_llm()
            result = llm.chat_structured(
                system_prompt, user_message, SUMMARIZE_OUTPUT_SCHEMA
            )
        except RuntimeError:
            return {"success": False, "task_id": task_id, "error": "llm_unavailable"}

        # 校验输出
        validation_errors = _validate_summarize_output(result)
        if validation_errors:
            return {
                "success": False,
                "task_id": task_id,
                "error": "validation_failed",
                "validation_errors": validation_errors,
            }

        # 写入短期上下文（Planner 是 read_only，只能写短期）
        constraint_key = "planner.constraint.analysis"
        feasibility_key = "planner.feasibility.assessment"

        self._write_context(
            constraint_key, result["constraint_analysis"], ContextScope.SHORT_TERM
        )
        self._write_context(
            feasibility_key, result["feasibility_assessment"], ContextScope.SHORT_TERM
        )

        return {
            "success": True,
            "task_id": task_id,
            "outputs": [constraint_key, feasibility_key],
            "difficulty_level": result["constraint_analysis"]
            .get("audience_match", {})
            .get("difficulty_level", ""),
            "overall_score": result["feasibility_assessment"].get("overall_score", 0),
            "risk_count": len(result["constraint_analysis"].get("risk_points", [])),
        }

    # ------------------------------------------------------------------
    # PLAN — 分镜建议
    # ------------------------------------------------------------------

    def _run_plan(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        pid = self.plan.project_id

        # 从 kwargs 或 runtime 读取输入
        segments = [s.to_dict() for s in self.plan.segments]
        constraint_analysis = kwargs.get("constraint_analysis") or self._read_context(
            "planner.constraint.analysis"
        )
        research_summary = kwargs.get("research_summary") or self._read_context(
            f"{pid}.research.summary"
        )
        glossary = kwargs.get("glossary") or self._read_context(f"{pid}.glossary")
        formula_catalog = kwargs.get("formula_catalog") or self._read_context(
            f"{pid}.formula.catalog"
        )
        assets = kwargs.get("assets")

        user_message = build_plan_user_message(
            segments=segments,
            constraint_analysis=constraint_analysis,
            research_summary=research_summary,
            glossary=glossary,
            formula_catalog=formula_catalog,
            assets=assets,
        )
        system_prompt = self._build_system_prompt_text(PipelineStage.PLAN)

        try:
            llm = self._require_llm()
            result = llm.chat_structured(system_prompt, user_message, PLAN_OUTPUT_SCHEMA)
        except RuntimeError:
            return {"success": False, "task_id": task_id, "error": "llm_unavailable"}

        # 校验输出
        validation_errors = _validate_plan_output(result)
        if validation_errors:
            return {
                "success": False,
                "task_id": task_id,
                "error": "validation_failed",
                "validation_errors": validation_errors,
            }

        # 写入短期上下文
        key = "planner.storyboard.suggestions"
        self._write_context(key, result["storyboard_suggestions"], ContextScope.SHORT_TERM)

        return {
            "success": True,
            "task_id": task_id,
            "outputs": [key],
            "segments_planned": len(result["storyboard_suggestions"].get("segments", [])),
        }

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _build_system_prompt_text(self, stage: PipelineStage) -> str:
        parts = self.build_system_prompt(stage)
        return "\n".join(parts)


# ============================================================================
# 输出校验
# ============================================================================


def _validate_summarize_output(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    constraint = result.get("constraint_analysis")
    feasibility = result.get("feasibility_assessment")

    if not isinstance(constraint, dict):
        errors.append("constraint_analysis must be an object")
    else:
        audience_match = constraint.get("audience_match")
        if not isinstance(audience_match, dict):
            errors.append("constraint_analysis.audience_match must be an object")
        else:
            if audience_match.get("difficulty_level") not in [
                "beginner",
                "intermediate",
                "advanced",
            ]:
                errors.append(
                    "constraint_analysis.audience_match.difficulty_level must be "
                    "beginner/intermediate/advanced"
                )
            if not isinstance(audience_match.get("recommendations"), list):
                errors.append(
                    "constraint_analysis.audience_match.recommendations must be an array"
                )

        time_estimates = constraint.get("time_estimates")
        if not isinstance(time_estimates, list) or len(time_estimates) == 0:
            errors.append("constraint_analysis.time_estimates must be a non-empty array")

        modality_recs = constraint.get("modality_recommendations")
        if not isinstance(modality_recs, list) or len(modality_recs) == 0:
            errors.append(
                "constraint_analysis.modality_recommendations must be a non-empty array"
            )

        risk_points = constraint.get("risk_points")
        if not isinstance(risk_points, list):
            errors.append("constraint_analysis.risk_points must be an array")

    if not isinstance(feasibility, dict):
        errors.append("feasibility_assessment must be an object")
    else:
        score = feasibility.get("overall_score")
        if not isinstance(score, int) or score < 1 or score > 5:
            errors.append("feasibility_assessment.overall_score must be integer 1-5")
        if not isinstance(feasibility.get("success_factors"), list):
            errors.append("feasibility_assessment.success_factors must be an array")
        if not isinstance(feasibility.get("challenges"), list):
            errors.append("feasibility_assessment.challenges must be an array")

    return errors


def _validate_plan_output(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    storyboard = result.get("storyboard_suggestions")
    if not isinstance(storyboard, dict):
        errors.append("storyboard_suggestions must be an object")
        return errors

    segment_order = storyboard.get("segment_order")
    if not isinstance(segment_order, list) or len(segment_order) == 0:
        errors.append("storyboard_suggestions.segment_order must be a non-empty array")

    segments = storyboard.get("segments")
    if not isinstance(segments, list) or len(segments) == 0:
        errors.append("storyboard_suggestions.segments must be a non-empty array")
    else:
        for i, seg in enumerate(segments):
            if not isinstance(seg, dict):
                errors.append(f"storyboard_suggestions.segments[{i}] must be an object")
                continue

            if not seg.get("segment_id"):
                errors.append(f"storyboard_suggestions.segments[{i}] missing segment_id")

            if seg.get("modality") not in ["html", "manim", "hybrid", "svg"]:
                errors.append(
                    f"storyboard_suggestions.segments[{i}].modality must be "
                    "html/manim/hybrid/svg"
                )

            est_seconds = seg.get("estimated_seconds")
            if not isinstance(est_seconds, int) or est_seconds < 5:
                errors.append(
                    f"storyboard_suggestions.segments[{i}].estimated_seconds must be >= 5"
                )

    pacing = storyboard.get("pacing_advice")
    if not isinstance(pacing, dict):
        errors.append("storyboard_suggestions.pacing_advice must be an object")
    else:
        for field in ["opening", "middle", "closing"]:
            if not isinstance(pacing.get(field), str) or not pacing[field]:
                errors.append(f"storyboard_suggestions.pacing_advice.{field} must be a string")

    return errors
