"""HTML Worker Agent — 生成 HTML 科普动画页面。"""

from __future__ import annotations

from typing import Any

from ..llm.templates.html_worker import DISPATCH_OUTPUT_SCHEMA, build_dispatch_user_message
from ..models import ContextScope, PipelineStage
from .base import BaseAgent


class HtmlWorkerAgent(BaseAgent):
    """HTML Worker — 生成 HTML 动画片段。

    DISPATCH 阶段:
        - 读取 storyboard.master + narration.script
        - 为 HTML/hybrid 镜头生成完整的 HTML/CSS/JS 动画页面
        - 写入长期上下文
    """

    role_id = "html_worker"

    def run(self, stage: PipelineStage, task_id: str, **kwargs: Any) -> dict[str, Any]:
        if stage != PipelineStage.DISPATCH:
            return {
                "success": False,
                "task_id": task_id,
                "error": f"HTML Worker only supports DISPATCH stage, got {stage.value}",
            }
        return self._run_dispatch(task_id, **kwargs)

    def _run_dispatch(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        pid = self.plan.project_id
        storyboard = kwargs.get("storyboard") or self._read_context(f"{pid}.storyboard.master")
        narration = kwargs.get("narration") or self._read_context(f"{pid}.narration.script")
        style_guide = kwargs.get("style_guide") or self._read_context(f"{pid}.style.guide")

        user_message = build_dispatch_user_message(
            storyboard=storyboard,
            narration=narration,
            style_guide=style_guide,
        )
        system_prompt = self._build_system_prompt_text(PipelineStage.DISPATCH)

        try:
            llm = self._require_llm()
            result = llm.chat_structured(system_prompt, user_message, DISPATCH_OUTPUT_SCHEMA)
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

        # 写入长期上下文
        outputs: list[str] = []
        for seg in result["html_segments"]:
            sid = seg["segment_id"]
            key = f"{pid}.html.{sid}.approved"
            self._write_context(key, seg, ContextScope.LONG_TERM)
            outputs.append(key)

        return {
            "success": True,
            "task_id": task_id,
            "outputs": outputs,
            "segment_count": len(result["html_segments"]),
        }

    def _build_system_prompt_text(self, stage: PipelineStage) -> str:
        return "\n".join(self.build_system_prompt(stage))


def _validate_output(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    segments = result.get("html_segments")
    if not isinstance(segments, list) or len(segments) == 0:
        errors.append("html_segments must be a non-empty array")
    else:
        for i, seg in enumerate(segments):
            if not seg.get("segment_id"):
                errors.append(f"html_segments[{i}] missing segment_id")
            if not seg.get("html_code"):
                errors.append(f"html_segments[{i}] missing html_code")
    return errors
