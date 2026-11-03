"""Project-level deterministic quality audit for generated animation assets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..models import ContextScope, ProjectPlan, SegmentModality
from .formula_visual_binding import assess_formula_visual_binding
from .manim_code_quality import assess_manim_code_quality
from .render_evidence import assess_render_evidence, evidence_code_is_stale
from .semantic_colors import assess_semantic_color_consistency


@dataclass(slots=True)
class QualityAuditReport:
    project_id: str
    status: str
    segment_count: int
    checked_segments: list[str] = field(default_factory=list)
    missing_manim_segments: list[str] = field(default_factory=list)
    missing_evidence_segments: list[str] = field(default_factory=list)
    stale_evidence_segments: list[str] = field(default_factory=list)
    render_evidence_findings: list[dict[str, object]] = field(default_factory=list)
    manim_code_quality_findings: list[dict[str, object]] = field(default_factory=list)
    formula_visual_binding_findings: list[dict[str, object]] = field(default_factory=list)
    semantic_color_consistency: dict[str, object] | None = None
    output_path: str | None = None
    summary_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_quality_audit(
    plan: ProjectPlan,
    *,
    write_report: bool = True,
) -> QualityAuditReport:
    """Audit project runtime outputs without invoking an LLM."""
    manim_outputs: list[dict[str, object]] = []
    render_findings: list[dict[str, object]] = []
    code_findings: list[dict[str, object]] = []
    binding_findings: list[dict[str, object]] = []
    missing_manim: list[str] = []
    missing_evidence: list[str] = []
    stale_evidence: list[str] = []

    formula_segment_ids = {segment.id for segment in plan.segments if segment.formulas}
    formulas_by_segment = {
        segment.id: list(segment.formulas)
        for segment in plan.segments
    }

    for segment in plan.segments:
        requires_manim = (
            segment.modality in {SegmentModality.MANIM, SegmentModality.HYBRID}
            or bool(segment.formulas)
        )
        approved = _read_context_content(
            plan,
            f"{plan.project_id}.manim.{segment.id}.approved",
        )
        if isinstance(approved, dict):
            manim_outputs.append({"segment_id": segment.id, "content": approved})
            code_findings.append(
                assess_manim_code_quality(
                    approved,
                    formula_required=segment.id in formula_segment_ids,
                ).to_dict()
            )
            if formulas_by_segment.get(segment.id):
                binding_findings.append(
                    assess_formula_visual_binding(
                        approved,
                        formulas_by_segment[segment.id],
                    ).to_dict()
                )
        elif requires_manim:
            missing_manim.append(segment.id)

        evidence = _read_context_content(
            plan,
            f"{plan.project_id}.manim.{segment.id}.render_evidence",
        )
        if isinstance(evidence, dict):
            if isinstance(approved, dict) and evidence_code_is_stale(approved, evidence):
                stale_evidence.append(segment.id)
            render_findings.append(
                assess_render_evidence(
                    evidence,
                    approved_manim=approved if isinstance(approved, dict) else None,
                ).to_dict()
            )
        elif requires_manim or approved is not None:
            missing_evidence.append(segment.id)

    color_finding = assess_semantic_color_consistency(manim_outputs)
    checked_segments = sorted({
        str(item["segment_id"])
        for item in manim_outputs
        if "segment_id" in item
    } | {
        str(item.get("segment_id"))
        for item in render_findings
        if item.get("segment_id")
    })

    blocked = (
        bool(missing_manim)
        or bool(missing_evidence)
        or bool(stale_evidence)
        or _has_block(render_findings)
        or _has_block(code_findings)
        or _has_block(binding_findings)
        or color_finding.status == "block"
    )
    report = QualityAuditReport(
        project_id=plan.project_id,
        status="block" if blocked else "pass",
        segment_count=len(plan.segments),
        checked_segments=checked_segments,
        missing_manim_segments=missing_manim,
        missing_evidence_segments=missing_evidence,
        stale_evidence_segments=stale_evidence,
        render_evidence_findings=render_findings,
        manim_code_quality_findings=code_findings,
        formula_visual_binding_findings=binding_findings,
        semantic_color_consistency=(
            color_finding.to_dict() if color_finding.symbol_colors else None
        ),
    )
    if write_report:
        report.output_path = str(_write_quality_audit_report(plan, report.to_dict()))
        report.summary_path = str(_write_quality_audit_summary(plan, report.to_dict()))
    return report


def _read_context_content(plan: ProjectPlan, key: str) -> Any | None:
    path = _context_file_path(plan, key, ContextScope.LONG_TERM)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("content") if isinstance(payload, dict) else payload


def _context_file_path(plan: ProjectPlan, key: str, scope: ContextScope) -> Path:
    if scope == ContextScope.LONG_TERM:
        base = Path(plan.runtime_layout.project_context_dir)
    else:
        base = Path(plan.runtime_layout.session_context_root)
    return base / f"{key.replace('.', '-')}.json"


def _write_quality_audit_report(
    plan: ProjectPlan,
    payload: dict[str, object],
) -> Path:
    output_dir = Path(plan.runtime_layout.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "quality-audit.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_quality_audit_summary(
    plan: ProjectPlan,
    payload: dict[str, object],
) -> Path:
    output_dir = Path(plan.runtime_layout.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "quality-summary.md"
    path.write_text(_render_quality_summary_markdown(plan, payload), encoding="utf-8")
    return path


def _render_quality_summary_markdown(
    plan: ProjectPlan,
    payload: dict[str, object],
) -> str:
    render_by_segment = _findings_by_segment(payload.get("render_evidence_findings"))
    code_by_segment = _findings_by_segment(payload.get("manim_code_quality_findings"))
    binding_by_segment = _findings_by_segment(payload.get("formula_visual_binding_findings"))
    missing_manim = set(_string_list(payload.get("missing_manim_segments")))
    missing_evidence = set(_string_list(payload.get("missing_evidence_segments")))
    stale_evidence = set(_string_list(payload.get("stale_evidence_segments")))
    lines = [
        f"# Quality Summary: {plan.project_id}",
        "",
        f"- Status: {payload.get('status', 'unknown')}",
        f"- Segments: {len(payload.get('checked_segments', []))}/{payload.get('segment_count', 0)} checked",
        f"- Missing Manim: {_format_inline_list(missing_manim)}",
        f"- Missing evidence: {_format_inline_list(missing_evidence)}",
        f"- Stale evidence: {_format_inline_list(stale_evidence)}",
        "",
        "## Segment Review",
        "",
    ]

    for segment in plan.segments:
        sid = segment.id
        render = render_by_segment.get(sid, {})
        code = code_by_segment.get(sid, {})
        binding = binding_by_segment.get(sid, {})
        segment_status = _segment_status(
            sid,
            render=render,
            code=code,
            binding=binding,
            missing_manim=missing_manim,
            missing_evidence=missing_evidence,
            stale_evidence=stale_evidence,
        )
        lines.extend([
            f"### {sid} - {segment.title}",
            "",
            f"- Status: {segment_status}",
            f"- Render: {render.get('status', 'missing')}",
            f"- Code quality: {code.get('status', 'missing')}",
            f"- Formula binding: {binding.get('status', 'not-required')}",
        ])
        issues = _segment_issues(
            sid,
            render=render,
            code=code,
            binding=binding,
            missing_manim=missing_manim,
            missing_evidence=missing_evidence,
            stale_evidence=stale_evidence,
        )
        lines.append(f"- Issues: {_format_inline_list(issues)}")
        frame_paths = _string_list(render.get("frame_paths"))
        if frame_paths:
            lines.append("- Keyframes:")
            for index, frame_path in enumerate(frame_paths[:3], start=1):
                lines.append(f"  - ![{sid} frame {index}]({_markdown_path(frame_path)})")
        lines.append("")

    color = payload.get("semantic_color_consistency")
    if isinstance(color, dict):
        lines.extend([
            "## Semantic Colors",
            "",
            f"- Status: {color.get('status', 'unknown')}",
            f"- Issues: {_format_inline_list(_string_list(color.get('issues')))}",
            "",
        ])

    return "\n".join(lines).rstrip() + "\n"


def _findings_by_segment(raw_findings: object) -> dict[str, dict[str, object]]:
    findings: dict[str, dict[str, object]] = {}
    if not isinstance(raw_findings, list):
        return findings
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        segment_id = item.get("segment_id")
        if segment_id is not None:
            findings[str(segment_id)] = item
    return findings


def _segment_status(
    segment_id: str,
    *,
    render: dict[str, object],
    code: dict[str, object],
    binding: dict[str, object],
    missing_manim: set[str],
    missing_evidence: set[str],
    stale_evidence: set[str],
) -> str:
    if (
        segment_id in missing_manim
        or segment_id in missing_evidence
        or segment_id in stale_evidence
        or render.get("status") == "block"
        or code.get("status") == "block"
        or binding.get("status") == "block"
    ):
        return "block"
    return "pass"


def _segment_issues(
    segment_id: str,
    *,
    render: dict[str, object],
    code: dict[str, object],
    binding: dict[str, object],
    missing_manim: set[str],
    missing_evidence: set[str],
    stale_evidence: set[str],
) -> list[str]:
    issues: list[str] = []
    if segment_id in missing_manim:
        issues.append("missing approved Manim output")
    if segment_id in missing_evidence:
        issues.append("missing render evidence")
    if segment_id in stale_evidence:
        issues.append("stale render evidence")
    for finding in (render, code, binding):
        issues.extend(_string_list(finding.get("issues")))
    return issues


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _format_inline_list(items: set[str] | list[str]) -> str:
    values = sorted(items) if isinstance(items, set) else items
    return ", ".join(values) if values else "none"


def _markdown_path(path: str) -> str:
    return Path(path).resolve().as_posix()


def _has_block(findings: list[dict[str, object]]) -> bool:
    return any(finding.get("status") == "block" for finding in findings)
