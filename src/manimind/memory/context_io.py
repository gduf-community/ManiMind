"""上下文读写模块 — 独立于 Agent 的 runtime 文件系统操作。

提供原子读写、scope 校验、路径映射等功能，
可被 Agent、Orchestrator、CLI 命令等任何代码使用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import ContextScope


def context_file_path(key: str, scope: ContextScope, runtime_dirs: dict[str, str]) -> Path:
    """将上下文 key 映射到 runtime 文件路径。

    Args:
        key: 上下文 key（如 "project.research.summary"）
        scope: 上下文范围（long_term / short_term）
        runtime_dirs: 包含 "project_context_dir" 和 "session_context_root" 的字典
    """
    if scope == ContextScope.LONG_TERM:
        base = Path(runtime_dirs["project_context_dir"])
    else:
        base = Path(runtime_dirs["session_context_root"])
    safe_name = key.replace(".", "-")
    return base / f"{safe_name}.json"


def read_context(
    key: str,
    runtime_dirs: dict[str, str],
    session_id: str = "default",
) -> Any | None:
    """从 runtime 读取指定 key 的上下文正文。

    先查长期上下文，再查当前会话的短期上下文。

    Args:
        key: 上下文 key
        runtime_dirs: 包含 project_context_dir 和 session_context_root 的字典
        session_id: 会话标识（短期上下文时使用）
    """
    for scope in (ContextScope.LONG_TERM, ContextScope.SHORT_TERM):
        path = context_file_path(key, scope, _scope_dirs(runtime_dirs, session_id, scope))
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload.get("content") if isinstance(payload, dict) else payload
    return None


def write_context(
    key: str,
    content: Any,
    runtime_dirs: dict[str, str],
    session_id: str = "default",
    scope: ContextScope = ContextScope.SHORT_TERM,
    writer_role: str = "system",
    metadata: dict[str, Any] | None = None,
) -> Path:
    """向 runtime 原子写入上下文正文。

    Args:
        key: 上下文 key
        content: 要写入的内容
        runtime_dirs: 包含 project_context_dir 和 session_context_root 的字典
        session_id: 会话标识
        scope: 上下文范围
        writer_role: 写入者角色标识
        metadata: 额外元数据
    """
    path = context_file_path(key, scope, _scope_dirs(runtime_dirs, session_id, scope))
    path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "key": key,
        "scope": scope.value,
        "writer_role": writer_role,
        "session_id": session_id,
        "content": content,
    }
    if metadata:
        payload["metadata"] = metadata

    tmp_path = path.with_name(f".{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    tmp_path.replace(path)
    return path


def _scope_dirs(
    runtime_dirs: dict[str, str],
    session_id: str,
    scope: ContextScope,
) -> dict[str, str]:
    """调整 runtime_dirs，在 scope 为短期时拼接 session_id。"""
    if scope == ContextScope.SHORT_TERM:
        return {
            **runtime_dirs,
            "session_context_root": str(
                Path(runtime_dirs["session_context_root"]) / session_id
            ),
        }
    return runtime_dirs
