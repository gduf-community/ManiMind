"""
环境检测报告生成器 - 复用 bootstrap.check_tools()，生成结构化报告。

严格按照 docs/agent-data-protocol.md 第 0.5 节的数据格式定义。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


@dataclass
class ToolCheckResult:
    """单个工具的检测结果，对应协议中的 ToolCheckResult。"""
    name: str
    available: bool
    version: Optional[str] = None
    path: Optional[str] = None
    details: Optional[str] = None


@dataclass
class EnvReport:
    """环境检测的完整输出，对应协议中的 EnvReport。"""
    generated_at: datetime
    python: ToolCheckResult
    node: ToolCheckResult
    manim: ToolCheckResult
    ffmpeg: ToolCheckResult
    overall_status: Literal["ok", "warning", "error"] = "ok"
    warnings: list[str] = field(default_factory=list)


class EnvReporter:
    """调用 bootstrap.check_tools()，生成标准化的环境检测报告。"""

    def generate(self) -> EnvReport:
        """执行环境检测并返回 EnvReport。"""
        from manimind.bootstrap import check_tools

        result = check_tools()

        # 注意：check_tools() 返回 {tool_name: True/False}，True 表示可用
        def make_result(name: str) -> ToolCheckResult:
            available = result.get(name, False)
            return ToolCheckResult(
                name=name,
                available=available,
                version=None,
                path=None,
                details=None,
            )

        python = make_result("python")
        node = make_result("node")
        manim_available = result.get("manimgl", result.get("manim", False))
        manim = ToolCheckResult(
            name="manimgl",
            available=manim_available,
            details="ManimGL is the default renderer; ManimCE remains optional.",
        )
        ffmpeg = make_result("ffmpeg")

        # 计算总体状态
        all_available = python.available and node.available and manim.available and ffmpeg.available
        any_missing = not all_available

        overall_status = "ok" if all_available else "warning"

        warnings: list[str] = []
        if any_missing:
            missing = []
            if not python.available:
                missing.append("python")
            if not node.available:
                missing.append("node")
            if not manim.available:
                missing.append("manimgl")
            if not ffmpeg.available:
                missing.append("ffmpeg")
            warnings.append(f"缺少或未检测到工具: {', '.join(missing)}")

        return EnvReport(
            generated_at=datetime.now(),
            python=python,
            node=node,
            manim=manim,
            ffmpeg=ffmpeg,
            overall_status=overall_status,
            warnings=warnings,
        )
