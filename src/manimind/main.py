"""ManiMind 命令行入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .bootstrap import check_tools, ensure_workspace, prepend_local_tool_path
from .context_assembly import (
    PromptSectionCache,
    build_context_packet,
    build_default_prompt_sections,
)
from .models import PipelineStage, SegmentModality, SegmentSpec, SourceBundle, TaskStatus
from .runtime_store import (
    load_execution_task_snapshot,
    persist_context_packet,
    persist_plan_snapshot,
    persist_task_update,
)
from .task_board import update_execution_task_status
from .workflow import build_project_plan

DEFAULT_SESSION_ID = "manual-session"


def _get_llm_client(args) -> object | None:
    """根据命令行参数创建 LLM 客户端（如果提供了 API key）。"""
    api_key = getattr(args, "llm_api_key", None)
    if not api_key:
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    from .llm.client import LlmClient
    base_url = getattr(args, "llm_base_url", None) or os.environ.get("OPENAI_BASE_URL")
    model = getattr(args, "llm_model", None) or os.environ.get("MANIMIND_MODEL", "gpt-4o")
    return LlmClient(api_key=api_key, base_url=base_url or None, model=model)


def _get_code_llm_client() -> object | None:
    """创建代码生成 LLM 客户端（从 CODE_LLM_* 环境变量）。"""
    import os
    api_key = os.environ.get("CODE_LLM_API_KEY")
    if not api_key:
        return None
    from .llm.client import LlmClient
    return LlmClient(
        api_key=api_key,
        base_url=os.environ.get("CODE_LLM_BASE_URL"),
        model=os.environ.get("CODE_LLM_MODEL", "gemini-2.5-pro"),
    )


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
    prepend_local_tool_path()
    parser = argparse.ArgumentParser(description="ManiMind 项目工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap", help="创建并校验工作区目录")
    subparsers.add_parser("doctor", help="检查工具链可用性")

    plan_parser = subparsers.add_parser("plan", help="从 JSON 清单构建项目计划")
    plan_parser.add_argument("manifest", type=Path)
    plan_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="本次计划构建对应的会话标识",
    )

    context_parser = subparsers.add_parser(
        "context-pack", help="按角色与阶段装配上下文包"
    )
    context_parser.add_argument("manifest", type=Path)
    context_parser.add_argument("role_id", type=str)
    context_parser.add_argument("stage", type=str)
    context_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="上下文装配对应的会话标识",
    )
    context_parser.add_argument(
        "--render-prompt-sections",
        action="store_true",
        help="额外输出提示词分段渲染结果",
    )
    context_parser.add_argument(
        "--allow-disallowed-stage",
        action="store_true",
        help="允许在角色未声明支持的阶段生成 context packet",
    )

    task_parser = subparsers.add_parser(
        "task-update", help="按状态机规则推进执行任务"
    )
    task_parser.add_argument("manifest", type=Path)
    task_parser.add_argument("task_id", type=str)
    task_parser.add_argument("status", type=str)
    task_parser.add_argument("actor_role", type=str)
    task_parser.add_argument(
        "--session-id",
        type=str,
        default=DEFAULT_SESSION_ID,
        help="任务更新对应的会话标识",
    )

    audit_parser = subparsers.add_parser(
        "quality-audit",
        help="复用确定性审核规则审计已有 Manim 产物与渲染证据",
    )
    audit_parser.add_argument("manifest", type=Path)
    audit_parser.add_argument(
        "--no-write",
        action="store_true",
        help="只打印审计结果，不写入 outputs/<project_id>/quality-audit.json",
    )

    assemble_parser = subparsers.add_parser(
        "assemble-video",
        help="把已通过渲染证据的 Manim 分段视频按清单顺序拼接成预览成片",
    )
    assemble_parser.add_argument("manifest", type=Path)
    assemble_parser.add_argument("--legacy-experiment", action="store_true",
                                 help="显式复现历史拼接实验，当前课程发布使用监督入口")
    assemble_parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="输出文件名，默认 <project_id>-final.mp4",
    )

    subtitles_parser = subparsers.add_parser(
        "build-subtitles",
        help="根据旁白脚本与分段视频真实时长生成 SRT 字幕文件",
    )
    subtitles_parser.add_argument("manifest", type=Path)
    subtitles_parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="输出文件名，默认 <project_id>.srt",
    )

    mux_subtitles_parser = subparsers.add_parser(
        "mux-subtitles",
        help="把 SRT 作为软字幕轨封装进项目 MP4",
    )
    mux_subtitles_parser.add_argument("manifest", type=Path)
    mux_subtitles_parser.add_argument("--video-path", type=Path, default=None)
    mux_subtitles_parser.add_argument("--subtitle-path", type=Path, default=None)
    mux_subtitles_parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="输出文件名，默认 <project_id>-final-subtitled.mp4",
    )

    burn_subtitles_parser = subparsers.add_parser(
        "burn-subtitles",
        help="把 SRT 字幕烧录进画面，生成平台通用审看片",
    )
    burn_subtitles_parser.add_argument("manifest", type=Path)
    burn_subtitles_parser.add_argument("--video-path", type=Path, default=None)
    burn_subtitles_parser.add_argument("--subtitle-path", type=Path, default=None)
    burn_subtitles_parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="输出文件名，默认 <project_id>-final-burned.mp4",
    )

    voiceover_parser = subparsers.add_parser(
        "build-voiceover",
        help="使用 Windows SAPI 或 macOS say 根据旁白脚本生成离线 WAV 旁白",
    )
    voiceover_parser.add_argument("manifest", type=Path)
    voiceover_parser.add_argument("--output-name", type=str, default=None)
    voiceover_parser.add_argument("--voice-name", type=str, default=None)
    voiceover_parser.add_argument("--rate", type=int, default=0)

    mux_voiceover_parser = subparsers.add_parser(
        "mux-voiceover",
        help="把旁白 WAV 合成进视频，必要时按旁白长度缩放视频节奏",
    )
    mux_voiceover_parser.add_argument("manifest", type=Path)
    mux_voiceover_parser.add_argument("--video-path", type=Path, default=None)
    mux_voiceover_parser.add_argument("--audio-path", type=Path, default=None)
    mux_voiceover_parser.add_argument("--output-name", type=str, default=None)

    # ---- agent-run: 运行单个 Agent ----
    agent_parser = subparsers.add_parser("agent-run", help="运行单个 Agent")
    agent_parser.add_argument("manifest", type=Path)
    agent_parser.add_argument("--role", type=str, required=True,
                              choices=["explorer", "planner", "coordinator"])
    agent_parser.add_argument("--stage", type=str, required=True)
    agent_parser.add_argument("--session-id", type=str, default=DEFAULT_SESSION_ID)
    agent_parser.add_argument("--paper-path", type=str, default=None)
    agent_parser.add_argument("--note-path", type=str, action="append", default=None)
    agent_parser.add_argument("--llm-api-key", type=str, default=None)
    agent_parser.add_argument("--llm-base-url", type=str, default=None)
    agent_parser.add_argument("--llm-model", type=str, default=None)

    # ---- pipeline-run: 运行完整 Pipeline ----
    pipeline_parser = subparsers.add_parser("pipeline-run", help="运行完整 Pipeline")
    pipeline_parser.add_argument("manifest", type=Path)
    pipeline_parser.add_argument("--legacy-experiment", action="store_true",
                                help="显式复现历史流水线，当前课程发布使用监督入口")
    pipeline_parser.add_argument("--session-id", type=str, default=DEFAULT_SESSION_ID)
    pipeline_parser.add_argument("--paper-path", type=str, default=None)
    pipeline_parser.add_argument("--note-path", type=str, action="append", default=None)
    pipeline_parser.add_argument("--llm-api-key", type=str, default=None)
    pipeline_parser.add_argument("--llm-base-url", type=str, default=None)
    pipeline_parser.add_argument("--llm-model", type=str, default=None)
    pipeline_parser.add_argument(
        "--render-manim",
        action="store_true",
        help="Manim Worker 生成代码后立即渲染视频并抽帧，作为审核证据",
    )
    pipeline_parser.add_argument(
        "--manim-backend",
        choices=["manimgl", "manimce"],
        default="manimgl",
        help="Manim 代码生成与渲染后端，默认 manimgl",
    )

    args = parser.parse_args()

    if args.command in {"assemble-video", "pipeline-run"} and not args.legacy_experiment:
        parser.error("历史实验入口已隔离。课程发布见 ai/README.md；复现旧实验需显式 --legacy-experiment。")

    if args.command == "bootstrap":
        print(json.dumps(ensure_workspace(), ensure_ascii=False, indent=2))
        return

    if args.command == "doctor":
        print(json.dumps(check_tools(), ensure_ascii=False, indent=2))
        return

    if args.command == "plan":
        plan = _build_plan_model_from_manifest(args.manifest)
        persisted = persist_plan_snapshot(
            plan=plan,
            session_id=args.session_id,
            source_manifest=str(args.manifest),
        )
        print(
            json.dumps(
                {
                    "plan": plan.to_dict(),
                    "persisted_paths": persisted,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "context-pack":
        plan = _build_plan_model_from_manifest(args.manifest)
        load_execution_task_snapshot(plan)
        stage = PipelineStage(args.stage)
        try:
            packet = build_context_packet(
                plan=plan,
                role_id=args.role_id,
                stage=stage,
                allow_disallowed_stage=args.allow_disallowed_stage,
            )
        except PermissionError as exc:
            raise SystemExit(str(exc)) from exc
        output: dict[str, object] = {"context_packet": packet}
        prompt_sections: list[str] | None = None
        if args.render_prompt_sections:
            cache = PromptSectionCache()
            prompt_sections = cache.resolve(build_default_prompt_sections(packet))
            output["prompt_sections"] = prompt_sections
        output["persisted_paths"] = persist_context_packet(
            plan=plan,
            session_id=args.session_id,
            packet=packet,
            prompt_sections=prompt_sections,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if args.command == "task-update":
        plan = _build_plan_model_from_manifest(args.manifest)
        load_execution_task_snapshot(plan)
        result = update_execution_task_status(
            plan=plan,
            task_id=args.task_id,
            new_status=TaskStatus(args.status),
            actor_role=args.actor_role,
        )
        mutation = {
            "success": result.success,
            "task_id": result.task_id,
            "from_status": result.from_status,
            "to_status": result.to_status,
            "reason": result.reason,
            "verification_nudge_needed": result.verification_nudge_needed,
            "invalidated_task_ids": result.invalidated_task_ids,
            "graph_errors": result.graph_errors,
        }
        persisted = persist_task_update(
            plan=plan,
            session_id=args.session_id,
            mutation=mutation,
        )
        print(
            json.dumps(
                {
                    "mutation": mutation,
                    "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
                    "persisted_paths": persisted,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "quality-audit":
        plan = _build_plan_model_from_manifest(args.manifest)
        from .review import run_quality_audit
        report = run_quality_audit(plan, write_report=not args.no_write)
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "assemble-video":
        plan = _build_plan_model_from_manifest(args.manifest)
        from .postproduce import assemble_manim_video
        result = assemble_manim_video(plan, output_name=args.output_name)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "build-subtitles":
        plan = _build_plan_model_from_manifest(args.manifest)
        from .postproduce import build_subtitle_file
        result = build_subtitle_file(plan, output_name=args.output_name)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "mux-subtitles":
        plan = _build_plan_model_from_manifest(args.manifest)
        from .postproduce import mux_subtitle_track
        result = mux_subtitle_track(
            plan,
            video_path=args.video_path,
            subtitle_path=args.subtitle_path,
            output_name=args.output_name,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "burn-subtitles":
        plan = _build_plan_model_from_manifest(args.manifest)
        from .postproduce import burn_subtitle_track
        result = burn_subtitle_track(
            plan,
            video_path=args.video_path,
            subtitle_path=args.subtitle_path,
            output_name=args.output_name,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "build-voiceover":
        plan = _build_plan_model_from_manifest(args.manifest)
        from .postproduce import build_voiceover_audio
        result = build_voiceover_audio(
            plan,
            output_name=args.output_name,
            voice_name=args.voice_name,
            rate=args.rate,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "mux-voiceover":
        plan = _build_plan_model_from_manifest(args.manifest)
        from .postproduce import mux_voiceover_track
        result = mux_voiceover_track(
            plan,
            video_path=args.video_path,
            audio_path=args.audio_path,
            output_name=args.output_name,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.command == "agent-run":
        plan = _build_plan_model_from_manifest(args.manifest)
        llm_client = _get_llm_client(args)
        stage = PipelineStage(args.stage)
        role = args.role
        task_id = f"{role}.{stage.value}"

        if role == "explorer":
            from .agents.explorer import ExplorerAgent
            agent = ExplorerAgent(plan, llm_client=llm_client, session_id=args.session_id)
        elif role == "planner":
            from .agents.planner import PlannerAgent
            agent = PlannerAgent(plan, llm_client=llm_client, session_id=args.session_id)
        elif role == "coordinator":
            from .agents.coordinator import CoordinatorAgent
            agent = CoordinatorAgent(plan, llm_client=llm_client, session_id=args.session_id)
        else:
            raise SystemExit(f"Unknown role: {role}")

        # 加载输入源
        paper_text = None
        notes = None
        if args.paper_path:
            from .ingest.pdf_reader import PdfReader
            paper = PdfReader(args.paper_path).read()
            paper_text = paper.text if paper.exists else None
        if args.note_path:
            from .ingest.markdown_reader import MarkdownReader
            notes = []
            for p in args.note_path:
                note = MarkdownReader(p).read()
                notes.append({"title": note.title, "body_text": note.body_text})

        result = agent.run(stage, task_id, paper_text=paper_text, notes=notes)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "pipeline-run":
        plan = _build_plan_model_from_manifest(args.manifest)
        llm_client = _get_llm_client(args)
        code_llm = _get_code_llm_client()
        from .agents.orchestrator import Orchestrator
        orchestrator = Orchestrator(
            plan,
            llm_client=llm_client,
            code_llm_client=code_llm,
            session_id=args.session_id,
            render_manim_outputs=args.render_manim,
            manim_backend=args.manim_backend,
        )
        result = orchestrator.run(
            paper_path=args.paper_path,
            note_paths=args.note_path,
        )
        result_outputs = result.outputs if isinstance(result.outputs, dict) else {}
        review_output = result_outputs.get("review")
        review = review_output if isinstance(review_output, dict) else {}
        review_verdict = review.get("verdict")
        output = {
            "success": result.success and review_verdict == "pass",
            "execution_completed": result.success,
            "review_verdict": review_verdict,
            "review_check": "approved" if review_verdict == "pass" else (
                "blocked" if review_verdict == "block" else "missing_or_invalid"),
            "scope": "legacy_experiment_not_release",
            "project_id": result.project_id,
            "session_id": result.session_id,
            "stage_count": result.stage_count,
            "error_count": result.error_count,
            "stage_results": result.stage_results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        if not output["success"]:
            raise SystemExit(1)
        return


if __name__ == "__main__":
    main()
