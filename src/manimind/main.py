"""ManiMind 命令行入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bootstrap import check_tools, ensure_workspace
from .context_assembly import (
    PromptSectionCache,
    build_context_packet,
    build_default_prompt_sections,
)
from .models import PipelineStage, SegmentModality, SegmentSpec, SourceBundle, TaskStatus
from .task_board import update_execution_task_status
from .workflow import build_project_plan


def _load_manifest(manifest_path: Path) -> dict:
    """加载项目清单。"""
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _build_segments(raw_segments: list[dict]) -> list[SegmentSpec]:
    """把清单中的镜头定义转换为数据模型。"""
    return [
        SegmentSpec(
            id=item["id"],
            title=item["title"],
            goal=item["goal"],
            narration=item["narration"],
            modality=SegmentModality(item.get("modality", "hybrid")),
            formulas=item.get("formulas", []),
            html_motion_notes=item.get("html_motion_notes", []),
            requires_svg_motion=item.get("requires_svg_motion", False),
            estimated_seconds=item.get("estimated_seconds", 20),
        )
        for item in raw_segments
    ]


def build_plan_from_manifest(manifest_path: Path) -> dict:
    """从 JSON 清单生成标准项目计划。"""
    payload = _load_manifest(manifest_path)
    source_bundle = SourceBundle(**payload["source_bundle"])
    segments = _build_segments(payload["segments"])
    plan = build_project_plan(
        project_id=payload["project_id"],
        title=payload["title"],
        source_bundle=source_bundle,
        segments=segments,
    )
    return plan.to_dict()


def _build_plan_model_from_manifest(manifest_path: Path):
    """从 JSON 清单构建项目计划模型对象。"""
    payload = _load_manifest(manifest_path)
    source_bundle = SourceBundle(**payload["source_bundle"])
    segments = _build_segments(payload["segments"])
    return build_project_plan(
        project_id=payload["project_id"],
        title=payload["title"],
        source_bundle=source_bundle,
        segments=segments,
    )


def main() -> None:
    """CLI 主流程。"""
    parser = argparse.ArgumentParser(description="ManiMind 项目工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap", help="创建并校验工作区目录")
    subparsers.add_parser("doctor", help="检查工具链可用性")

    plan_parser = subparsers.add_parser("plan", help="从 JSON 清单构建项目计划")
    plan_parser.add_argument("manifest", type=Path)

    context_parser = subparsers.add_parser(
        "context-pack", help="按角色与阶段装配上下文包"
    )
    context_parser.add_argument("manifest", type=Path)
    context_parser.add_argument("role_id", type=str)
    context_parser.add_argument("stage", type=str)
    context_parser.add_argument(
        "--render-prompt-sections",
        action="store_true",
        help="额外输出提示词分段渲染结果",
    )

    task_parser = subparsers.add_parser(
        "task-update", help="按状态机规则推进执行任务"
    )
    task_parser.add_argument("manifest", type=Path)
    task_parser.add_argument("task_id", type=str)
    task_parser.add_argument("status", type=str)
    task_parser.add_argument("actor_role", type=str)

    args = parser.parse_args()

    if args.command == "bootstrap":
        print(json.dumps(ensure_workspace(), ensure_ascii=False, indent=2))
        return

    if args.command == "doctor":
        print(json.dumps(check_tools(), ensure_ascii=False, indent=2))
        return

    if args.command == "plan":
        print(
            json.dumps(
                build_plan_from_manifest(args.manifest),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "context-pack":
        plan = _build_plan_model_from_manifest(args.manifest)
        stage = PipelineStage(args.stage)
        packet = build_context_packet(
            plan=plan,
            role_id=args.role_id,
            stage=stage,
        )
        output: dict[str, object] = {"context_packet": packet}
        if args.render_prompt_sections:
            cache = PromptSectionCache()
            output["prompt_sections"] = cache.resolve(
                build_default_prompt_sections(packet)
            )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if args.command == "task-update":
        plan = _build_plan_model_from_manifest(args.manifest)
        result = update_execution_task_status(
            plan=plan,
            task_id=args.task_id,
            new_status=TaskStatus(args.status),
            actor_role=args.actor_role,
        )
        print(
            json.dumps(
                {
                    "mutation": {
                        "success": result.success,
                        "task_id": result.task_id,
                        "from_status": result.from_status,
                        "to_status": result.to_status,
                        "reason": result.reason,
                        "verification_nudge_needed": result.verification_nudge_needed,
                    },
                    "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return


if __name__ == "__main__":
    main()
