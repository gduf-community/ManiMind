"""Reviewer Agent — 审核下游 Worker 产物，硬关卡。"""

from __future__ import annotations

from typing import Any

from ..llm.templates.reviewer import REVIEW_OUTPUT_SCHEMA, build_review_user_message
from ..models import ContextScope, PipelineStage
from ..review import (
    FormulaVisualBindingFinding,
    ManimCodeQualityFinding,
    RenderEvidenceFinding,
    SemanticColorFinding,
    assess_formula_visual_binding,
    assess_manim_code_quality,
    assess_render_evidence,
    assess_semantic_color_consistency,
)
from .base import BaseAgent


class ReviewerAgent(BaseAgent):
    """审核 Agent — VERIFY_ONLY 模式，只读不写。

    REVIEW 阶段:
        - 读取 storyboard + narration + research + formula + worker outputs
        - 逐镜头审核数学正确性、叙事一致性、渲染可执行性
        - 输出: review.report → 长期上下文
    """

    role_id = "reviewer"

    def run(self, stage: PipelineStage, task_id: str, **kwargs: Any) -> dict[str, Any]:
        if stage != PipelineStage.REVIEW:
            return {
                "success": False,
                "task_id": task_id,
                "error": f"Reviewer only supports REVIEW stage, got {stage.value}",
            }
        return self._run_review(task_id, **kwargs)

    def _run_review(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        pid = self.plan.project_id
        storyboard = kwargs.get("storyboard") or self._read_context(f"{pid}.storyboard.master")
        narration = kwargs.get("narration") or self._read_context(f"{pid}.narration.script")
        research = kwargs.get("research_summary") or self._read_context(f"{pid}.research.summary")
        formula = kwargs.get("formula_catalog") or self._read_context(f"{pid}.formula.catalog")
        worker_outputs = kwargs.get("worker_outputs") or self._collect_worker_outputs(pid)
        evidence_findings = _assess_worker_render_evidence(worker_outputs)
        code_findings = _assess_worker_manim_code(
            worker_outputs,
            _formula_segment_ids(self.plan),
        )
        binding_findings = _assess_formula_visual_bindings(
            worker_outputs,
            _segment_formula_map(self.plan),
        )
        color_finding = assess_semantic_color_consistency(
            worker_outputs.get("manim", [])
        )
        if evidence_findings:
            worker_outputs["render_evidence_findings"] = [
                finding.to_dict() for finding in evidence_findings
            ]
        if code_findings:
            worker_outputs["manim_code_quality_findings"] = [
                finding.to_dict() for finding in code_findings
            ]
        if binding_findings:
            worker_outputs["formula_visual_binding_findings"] = [
                finding.to_dict() for finding in binding_findings
            ]
        if color_finding.symbol_colors:
            worker_outputs["semantic_color_consistency"] = color_finding.to_dict()

        user_message = build_review_user_message(
            storyboard=storyboard,
            narration=narration,
            research_summary=research,
            formula_catalog=formula,
            worker_outputs=worker_outputs,
        )
        system_prompt = self._build_system_prompt_text(PipelineStage.REVIEW)

        try:
            llm = self._require_llm()
            result = llm.chat_structured(system_prompt, user_message, REVIEW_OUTPUT_SCHEMA)
        except RuntimeError:
            return {"success": False, "task_id": task_id, "error": "llm_unavailable"}

        validation_errors = _validate_output(result)
        if validation_errors:
            return {
                "success": False,
                "task_id": task_id,
                "error": "validation_failed",
                "validation_errors": validation_errors,
            }

        _apply_render_evidence_gate(result, evidence_findings)
        _apply_manim_code_quality_gate(result, code_findings)
        _apply_formula_visual_binding_gate(result, binding_findings)
        _apply_semantic_color_gate(result, color_finding)

        key = f"{pid}.review.report"
        self._write_context(key, result, ContextScope.LONG_TERM)

        return {
            "success": True,
            "task_id": task_id,
            "outputs": [key],
            "verdict": result["overall_verdict"],
            "pass_count": sum(1 for s in result["segment_reviews"] if s["verdict"] == "pass"),
            "block_count": sum(1 for s in result["segment_reviews"] if s["verdict"] == "block"),
        }

    def _collect_worker_outputs(self, pid: str) -> dict[str, Any]:
        outputs: dict[str, list] = {"html": [], "manim": [], "svg": [], "render_evidence": []}
        for segment in self.plan.segments:
            sid = segment.id
            html_key = f"{pid}.html.{sid}.approved"
            manim_key = f"{pid}.manim.{sid}.approved"
            render_key = f"{pid}.manim.{sid}.render_evidence"
            svg_key = f"{pid}.svg.{sid}.approved"
            for key in (html_key, manim_key, render_key, svg_key):
                content = self._read_context(key)
                if content:
                    if "html" in key:
                        outputs["html"].append({"segment_id": sid, "content": content})
                    elif "render_evidence" in key:
                        outputs["render_evidence"].append({"segment_id": sid, "content": content})
                    elif "manim" in key:
                        outputs["manim"].append({"segment_id": sid, "content": content})
                    elif "svg" in key:
                        outputs["svg"].append({"segment_id": sid, "content": content})
        return outputs

    def _build_system_prompt_text(self, stage: PipelineStage) -> str:
        return "\n".join(self.build_system_prompt(stage))


def _validate_output(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    verdict = result.get("overall_verdict")
    if verdict not in ("pass", "block"):
        errors.append("overall_verdict must be pass or block")
    reviews = result.get("segment_reviews")
    if not isinstance(reviews, list) or len(reviews) == 0:
        errors.append("segment_reviews must be a non-empty array")
    return errors


def _assess_worker_render_evidence(
    worker_outputs: dict[str, Any],
) -> list[RenderEvidenceFinding]:
    findings: list[RenderEvidenceFinding] = []
    approved_by_segment = _manim_outputs_by_segment(worker_outputs)
    for item in worker_outputs.get("render_evidence", []):
        content = item.get("content") if isinstance(item, dict) else None
        segment_id = item.get("segment_id") if isinstance(item, dict) else None
        if isinstance(content, dict):
            approved_manim = approved_by_segment.get(str(segment_id))
            findings.append(
                assess_render_evidence(
                    content,
                    approved_manim=approved_manim,
                )
            )
    return findings


def _manim_outputs_by_segment(worker_outputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    outputs: dict[str, dict[str, Any]] = {}
    for item in worker_outputs.get("manim", []):
        if not isinstance(item, dict):
            continue
        segment_id = item.get("segment_id")
        content = item.get("content")
        if segment_id is not None and isinstance(content, dict):
            outputs[str(segment_id)] = content
    return outputs


def _assess_worker_manim_code(
    worker_outputs: dict[str, Any],
    formula_segment_ids: set[str],
) -> list[ManimCodeQualityFinding]:
    findings: list[ManimCodeQualityFinding] = []
    for item in worker_outputs.get("manim", []):
        content = item.get("content") if isinstance(item, dict) else None
        segment_id = item.get("segment_id") if isinstance(item, dict) else None
        if isinstance(content, dict):
            findings.append(
                assess_manim_code_quality(
                    content,
                    formula_required=str(segment_id) in formula_segment_ids,
                )
            )
    return findings


def _formula_segment_ids(plan) -> set[str]:
    return {
        segment.id
        for segment in plan.segments
        if segment.formulas
    }


def _segment_formula_map(plan) -> dict[str, list[str]]:
    return {
        segment.id: list(segment.formulas)
        for segment in plan.segments
    }


def _assess_formula_visual_bindings(
    worker_outputs: dict[str, Any],
    formulas_by_segment: dict[str, list[str]],
) -> list[FormulaVisualBindingFinding]:
    findings: list[FormulaVisualBindingFinding] = []
    for item in worker_outputs.get("manim", []):
        content = item.get("content") if isinstance(item, dict) else None
        segment_id = str(item.get("segment_id") if isinstance(item, dict) else "")
        formulas = formulas_by_segment.get(segment_id, [])
        if isinstance(content, dict) and formulas:
            findings.append(assess_formula_visual_binding(content, formulas))
    return findings


def _apply_render_evidence_gate(
    result: dict[str, Any],
    findings: list[RenderEvidenceFinding],
) -> None:
    blocking_findings = [finding for finding in findings if finding.status == "block"]
    if not blocking_findings:
        return

    for finding in blocking_findings:
        _append_gate_block(
            result,
            finding.segment_id,
            target_section="render_feasibility",
            issue_prefix="render evidence failed",
            issues=finding.issues,
            default_sections={
                "math_correctness": {"status": "pass", "issues": []},
                "narrative_consistency": {"status": "pass", "issues": []},
                "render_feasibility": {"status": "block", "issues": []},
            },
        )

    _append_summary_suffix(
        result,
        "Render evidence gate forced block because rendered video or frames failed deterministic checks.",
    )


def _apply_manim_code_quality_gate(
    result: dict[str, Any],
    findings: list[ManimCodeQualityFinding],
) -> None:
    blocking_findings = [finding for finding in findings if finding.status == "block"]
    if not blocking_findings:
        return

    for finding in blocking_findings:
        _append_gate_block(
            result,
            finding.segment_id,
            target_section="render_feasibility",
            issue_prefix="manim code quality failed",
            issues=finding.issues,
            default_sections={
                "math_correctness": {"status": "pass", "issues": []},
                "narrative_consistency": {"status": "pass", "issues": []},
                "render_feasibility": {"status": "block", "issues": []},
            },
        )

    _append_summary_suffix(
        result,
        "Manim code quality gate forced block because generated scene code lacks required explanatory animation signals.",
    )


def _apply_formula_visual_binding_gate(
    result: dict[str, Any],
    findings: list[FormulaVisualBindingFinding],
) -> None:
    blocking_findings = [finding for finding in findings if finding.status == "block"]
    if not blocking_findings:
        return

    for finding in blocking_findings:
        _append_gate_block(
            result,
            finding.segment_id,
            target_section="narrative_consistency",
            issue_prefix="formula visual binding failed",
            issues=finding.issues,
            default_sections={
                "math_correctness": {"status": "pass", "issues": []},
                "narrative_consistency": {"status": "block", "issues": []},
                "render_feasibility": {"status": "pass", "issues": []},
            },
        )

    _append_summary_suffix(
        result,
        "Formula visual binding gate forced block because formulas lack matching visual companions.",
    )


def _apply_semantic_color_gate(
    result: dict[str, Any],
    finding: SemanticColorFinding,
) -> None:
    if finding.status != "block":
        return

    affected_segments = _segments_from_color_finding(finding)

    for segment_id in sorted(affected_segments):
        _append_gate_block(
            result,
            segment_id,
            target_section="narrative_consistency",
            issue_prefix="semantic color consistency failed",
            issues=finding.issues,
            default_sections={
                "math_correctness": {"status": "pass", "issues": []},
                "narrative_consistency": {"status": "block", "issues": []},
                "render_feasibility": {"status": "pass", "issues": []},
            },
        )

    _append_summary_suffix(
        result,
        "Semantic color gate forced block because repeated symbols use conflicting colors across segments.",
    )


def _append_gate_block(
    result: dict[str, Any],
    segment_id: str,
    *,
    target_section: str,
    issue_prefix: str,
    issues: list[str],
    default_sections: dict[str, dict[str, Any]],
) -> None:
    result["overall_verdict"] = "block"
    review = _get_or_create_segment_review(result, segment_id, default_sections)
    review["verdict"] = "block"

    section = review.setdefault(
        target_section,
        {"status": "block", "issues": []},
    )
    section["status"] = "block"
    section_issues = section.setdefault("issues", [])
    blocking_issues = review.setdefault("blocking_issues", [])
    for issue in issues:
        message = f"{issue_prefix}: {issue}"
        _append_unique(section_issues, message)
        _append_unique(blocking_issues, message)


def _get_or_create_segment_review(
    result: dict[str, Any],
    segment_id: str,
    default_sections: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reviews = result.setdefault("segment_reviews", [])
    for review in reviews:
        if isinstance(review, dict) and review.get("segment_id") == segment_id:
            return review

    review = {
        "segment_id": segment_id,
        "verdict": "block",
        **default_sections,
        "blocking_issues": [],
        "fix_suggestions": [],
    }
    reviews.append(review)
    return review


def _append_summary_suffix(result: dict[str, Any], suffix: str) -> None:
    summary = result.get("summary", "")
    if suffix not in summary:
        result["summary"] = (summary + " " + suffix).strip()


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _segments_from_color_finding(finding: SemanticColorFinding) -> set[str]:
    segments: set[str] = set()
    for colors in finding.symbol_colors.values():
        if len(colors) <= 1:
            continue
        for segment_list in colors.values():
            segments.update(segment_list)
    return segments
