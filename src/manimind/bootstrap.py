"""ManiMind 初始化工具：负责目录准备与依赖检测。"""

from __future__ import annotations

import os
from pathlib import Path
import re
from shutil import which
import sys

from .models import RuntimeLayout


WORKSPACE_DIRECTORIES = [
    "configs",
    "scripts",
    "src/manimind",
    "tests",
    "resources/skills/html-animation",
    "resources/skills/manim",
    "resources/references/hyperframes",
    "runtime/projects",
    "runtime/sessions",
    "runtime/cache",
    "outputs",
    "logs",
]

EXTERNAL_PATHS = {
    "html_skill_root": "resources/skills/html-animation",
    "hyperframes_root": "resources/references/hyperframes",
    "manim_skill_file": "resources/skills/manim/SKILL.md",
    "docs_root": "docs",
}

REFERENCE_ARCHIVES = {
    "claude_code_source_zip": "ClaudeCode/src.zip",
    "claude_code_release_tgz": "ClaudeCode/anthropic-ai-claude-code-2.1.88.tgz",
}


def repo_root() -> Path:
    """返回仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def sanitize_identifier(value: str) -> str:
    """将项目或会话标识转换为稳定目录名。"""
    normalized = re.sub(r"[^0-9A-Za-z_-]+", "-", value).strip("-").lower()
    if not normalized:
        raise ValueError("identifier must contain at least one ASCII letter or digit")
    return normalized


def build_runtime_layout(project_id: str, root: Path | None = None) -> RuntimeLayout:
    """生成符合仓库约定的产物路径蓝图。"""
    base = root or repo_root()
    safe_project_id = sanitize_identifier(project_id)
    return RuntimeLayout(
        project_context_dir=str(base / "runtime" / "projects" / safe_project_id),
        session_context_root=str(base / "runtime" / "sessions"),
        output_dir=str(base / "outputs" / safe_project_id),
        bootstrap_report=str(base / "runtime" / "bootstrap-report.json"),
        doctor_report=str(base / "runtime" / "doctor-report.json"),
    )


def ensure_workspace(root: Path | None = None) -> dict[str, object]:
    """创建或校验工作区目录。"""
    base = root or repo_root()
    created: list[str] = []

    for relative_dir in WORKSPACE_DIRECTORIES:
        target = base / relative_dir
        target.mkdir(parents=True, exist_ok=True)
        created.append(relative_dir)

    return {
        "root": str(base),
        "created_or_verified": created,
        "external_paths": check_external_paths(base),
        "reference_archives": check_reference_archives(base),
    }


def check_external_paths(root: Path | None = None) -> dict[str, bool]:
    """检查第三方能力路径是否存在。"""
    base = root or repo_root()
    return {
        name: (base / relative_path).exists()
        for name, relative_path in EXTERNAL_PATHS.items()
    }


def check_reference_archives(root: Path | None = None) -> dict[str, bool]:
    """检查参考源码压缩包是否存在（可选，不影响运行时）。"""
    base = root or repo_root()
    return {
        name: (base / relative_path).exists()
        for name, relative_path in REFERENCE_ARCHIVES.items()
    }


def local_tool_bin(root: Path | None = None) -> Path:
    """Return the platform-specific bin directory of the local render environment."""
    base = root or repo_root()
    scripts_dir = "Scripts" if sys.platform == "win32" else "bin"
    return base / "manimgl_env" / scripts_dir


def resolve_tool(name: str, root: Path | None = None) -> str | None:
    """Prefer a tool installed in ``manimgl_env`` before searching ``PATH``."""
    executable = f"{name}.exe" if sys.platform == "win32" else name
    local_executable = local_tool_bin(root) / executable
    if local_executable.exists():
        return str(local_executable)
    return which(name)


def prepend_local_tool_path(root: Path | None = None) -> None:
    """Expose repository-local render tools to child processes for this run."""
    bin_dir = local_tool_bin(root)
    if not bin_dir.exists():
        return
    current = os.environ.get("PATH", "")
    entries = current.split(os.pathsep) if current else []
    value = str(bin_dir)
    if value not in entries:
        os.environ["PATH"] = os.pathsep.join([value, *entries])


def check_tools(root: Path | None = None) -> dict[str, bool]:
    """检查关键工具是否可用。"""
    return {
        "node": resolve_tool("node", root) is not None,
        "python": resolve_tool("python", root) is not None,
        "bun": resolve_tool("bun", root) is not None,
        "ffmpeg": resolve_tool("ffmpeg", root) is not None,
        "xelatex": resolve_tool("xelatex", root) is not None,
        "dvisvgm": resolve_tool("dvisvgm", root) is not None,
        "manimgl": resolve_tool("manimgl", root) is not None,
        "manim": resolve_tool("manim", root) is not None,
    }
