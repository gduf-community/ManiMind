"""Agent 编排器 — 按 Pipeline 阶段串联 Explorer → Planner → Coordinator。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ingest import load_source_bundle
from ..ingest.pdf_reader import PaperContent
from ..models import PipelineStage
from ..render import DEFAULT_MANIM_BACKEND, ManimBackend
from .base import LlmClientProtocol
from .explorer import ExplorerAgent
from .html_worker import HtmlWorkerAgent
from .manim_worker import ManimWorkerAgent
from .planner import PlannerAgent
from .svg_worker import SvgWorkerAgent
from .coordinator import CoordinatorAgent
from .reviewer import ReviewerAgent


@dataclass
class PipelineResult:
    """编排器运行结果。"""
    success: bool
    project_id: str
    session_id: str
    stage_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)

    @property
    def stage_count(self) -> int:
        return len(self.stage_results)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class Orchestrator:
    """Agent 编排器 — 按阶段自动调度 Explorer、Planner、Coordinator。

    用法::

        orchestrator = Orchestrator(plan, llm_client, session_id)
        result = orchestrator.run(paper_path="paper.pdf", note_paths=["notes.md"])
    """

    def __init__(
        self,
        plan,
        llm_client: LlmClientProtocol | None = None,
        code_llm_client: LlmClientProtocol | None = None,
        session_id: str = "default",
        render_manim_outputs: bool = False,
        manim_backend: ManimBackend | str = DEFAULT_MANIM_BACKEND,
    ):
        self.plan = plan
        self.llm_client = llm_client
        self.code_llm_client = code_llm_client or llm_client
        self.session_id = session_id
        self.render_manim_outputs = render_manim_outputs
        self.manim_backend = ManimBackend(manim_backend)

    def run(
        self,
        paper_path: str | None = None,
        note_paths: list[str] | None = None,
        stages: list[PipelineStage] | None = None,
    ) -> PipelineResult:
        """运行完整 Pipeline。

        Args:
            paper_path: PDF 论文路径（可选）
            note_paths: Markdown 笔记路径列表（可选）
            stages: 要运行的阶段列表，默认按顺序全跑

        Returns:
            PipelineResult: 包含每个阶段的运行结果和最终产物清单。
        """
        if stages is None:
            stages = [
                PipelineStage.PRESTART,
                PipelineStage.INGEST,
                PipelineStage.SUMMARIZE,
                PipelineStage.PLAN,
                PipelineStage.DISPATCH,
                PipelineStage.REVIEW,
            ]

        result = PipelineResult(
            success=True,
            project_id=self.plan.project_id,
            session_id=self.session_id,
        )

        # 加载输入源
        source_bundle = load_source_bundle(
            paper_path=paper_path,
            note_paths=note_paths,
        )

        paper: PaperContent | None = source_bundle.paper
        paper_text = paper.text if paper and paper.exists else None
        notes = [n.__dict__ for n in source_bundle.notes] if source_bundle.notes else None
        assets = _dataclass_to_dict(source_bundle.assets) if source_bundle.assets else None

        env_data = {}
        if source_bundle.env_report:
            er = source_bundle.env_report
            env_data = {
                "overall_status": er.overall_status,
                "python": _tool_to_dict(er.python),
                "node": _tool_to_dict(er.node),
                "manim": _tool_to_dict(er.manim),
                "ffmpeg": _tool_to_dict(er.ffmpeg),
                "warnings": er.warnings,
            }

        # 按阶段执行
        for stage in stages:
            stage_result = self._run_stage(
                stage, paper_text, notes, assets, env_data, result
            )
            result.stage_results.append(stage_result)
            if not stage_result.get("success"):
                result.success = False
                result.errors.append({
                    "stage": stage.value,
                    "error": stage_result.get("error", "unknown"),
                })

            result.outputs[stage.value] = stage_result

        return result

    def _run_stage(
        self,
        stage: PipelineStage,
        paper_text: str | None,
        notes: list[dict] | None,
        assets: dict | None,
        env_data: dict,
        pipeline_result: PipelineResult,
    ) -> dict[str, Any]:
        """执行单个 Pipeline 阶段。"""

        pid = self.plan.project_id

        # ---- PRESTART: Explorer 环境检查 ----
        if stage == PipelineStage.PRESTART:
            agent = ExplorerAgent(self.plan, self.llm_client, self.session_id)
            return agent.run(PipelineStage.PRESTART, "prestart.check", env_report=env_data)

        # ---- INGEST: Explorer 材料分析 ----
        if stage == PipelineStage.INGEST:
            agent = ExplorerAgent(self.plan, self.llm_client, self.session_id)
            return agent.run(
                PipelineStage.INGEST,
                "ingest.sources",
                paper_text=paper_text,
                notes=notes,
                assets=assets,
            )

        # ---- SUMMARIZE: Explorer + Planner 并行分析 ----
        if stage == PipelineStage.SUMMARIZE:
            explorer = ExplorerAgent(self.plan, self.llm_client, self.session_id)
            explorer_result = explorer.run(
                PipelineStage.SUMMARIZE,
                "summarize.research",
                paper_text=paper_text,
                notes=notes,
            )

            if not explorer_result.get("success"):
                return explorer_result

            planner = PlannerAgent(self.plan, self.llm_client, self.session_id)
            planner_result = planner.run(
                PipelineStage.SUMMARIZE,
                "planner.summarize",
                research_summary=explorer._read_context(f"{pid}.research.summary"),
                glossary=explorer._read_context(f"{pid}.glossary"),
                formula_catalog=explorer._read_context(f"{pid}.formula.catalog"),
            )

            return {
                "success": explorer_result["success"] and planner_result.get("success", False),
                "task_id": "summarize.combined",
                "explorer": explorer_result,
                "planner": planner_result,
            }

        # ---- PLAN: Explorer + Planner + Coordinator ----
        if stage == PipelineStage.PLAN:
            explorer = ExplorerAgent(self.plan, self.llm_client, self.session_id)
            explorer_result = explorer.run(
                PipelineStage.PLAN,
                "explorer.plan",
                research_summary=explorer._read_context(f"{pid}.research.summary"),
                glossary=explorer._read_context(f"{pid}.glossary"),
                formula_catalog=explorer._read_context(f"{pid}.formula.catalog"),
                assets=assets,
            )

            planner = PlannerAgent(self.plan, self.llm_client, self.session_id)
            planner_result = planner.run(PipelineStage.PLAN, "planner.plan")

            if not planner_result.get("success"):
                return planner_result

            coordinator = CoordinatorAgent(self.plan, self.llm_client, self.session_id)
            coord_result = coordinator.run(PipelineStage.PLAN, "plan.storyboard")

            return {
                "success": coord_result.get("success", False),
                "task_id": "plan.combined",
                "explorer": explorer_result,
                "planner": planner_result,
                "coordinator": coord_result,
            }

        # ---- DISPATCH: Coordinator 任务分发 + 三个 Worker 并行渲染 ----
        if stage == PipelineStage.DISPATCH:
            coordinator = CoordinatorAgent(self.plan, self.llm_client, self.session_id)
            coord_result = coordinator.run(PipelineStage.DISPATCH, "dispatch.tasks")

            if not coord_result.get("success"):
                return coord_result

            worker_results = {}
            html_worker = HtmlWorkerAgent(self.plan, self.code_llm_client, self.session_id)
            worker_results["html"] = html_worker.run(PipelineStage.DISPATCH, "render.html")

            manim_worker = ManimWorkerAgent(self.plan, self.code_llm_client, self.session_id)
            worker_results["manim"] = manim_worker.run(
                PipelineStage.DISPATCH,
                "render.manim",
                render_outputs=getattr(self, "render_manim_outputs", False),
                render_backend=self.manim_backend,
            )

            svg_worker = SvgWorkerAgent(self.plan, self.code_llm_client, self.session_id)
            worker_results["svg"] = svg_worker.run(PipelineStage.DISPATCH, "render.svg")

            failed_workers = [
                name
                for name, worker_result in worker_results.items()
                if not worker_result.get("success", False)
            ]
            return {
                "success": len(failed_workers) == 0,
                "task_id": "dispatch.combined",
                "coordinator": coord_result,
                "workers": worker_results,
                "failed_workers": failed_workers,
            }

        # ---- REVIEW: 审核所有产物 ----
        if stage == PipelineStage.REVIEW:
            reviewer = ReviewerAgent(self.plan, self.code_llm_client, self.session_id)
            return reviewer.run(PipelineStage.REVIEW, "review.outputs")

        return {"success": False, "error": f"Unknown stage: {stage.value}"}


def _tool_to_dict(tool) -> dict[str, Any]:
    return {
        "available": tool.available,
        "version": tool.version,
        "path": tool.path,
        "details": tool.details,
    }


def _dataclass_to_dict(obj) -> dict[str, Any]:
    """将 dataclass 转为 JSON 安全的字典（处理 datetime 等类型）。"""
    import dataclasses
    from datetime import datetime

    if dataclasses.is_dataclass(obj):
        result = {}
        for f in dataclasses.fields(obj):
            value = getattr(obj, f.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif dataclasses.is_dataclass(value):
                value = _dataclass_to_dict(value)
            elif isinstance(value, list):
                value = [
                    _dataclass_to_dict(v) if dataclasses.is_dataclass(v) else v
                    for v in value
                ]
            result[f.name] = value
        return result
    return obj
