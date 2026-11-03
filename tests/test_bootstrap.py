"""初始化与路径蓝图测试。"""

import sys

from manimind.bootstrap import (
    build_runtime_layout,
    check_external_paths,
    check_reference_archives,
    check_tools,
    ensure_workspace,
    local_tool_bin,
    resolve_tool,
    sanitize_identifier,
)


def test_sanitize_identifier_normalizes_project_id() -> None:
    assert sanitize_identifier("Demo Project 01") == "demo-project-01"


def test_build_runtime_layout_uses_repo_conventions(tmp_path) -> None:
    layout = build_runtime_layout("Demo Project", root=tmp_path)

    assert layout.project_context_dir == str(
        tmp_path / "runtime" / "projects" / "demo-project"
    )
    assert layout.session_context_root == str(tmp_path / "runtime" / "sessions")
    assert layout.output_dir == str(tmp_path / "outputs" / "demo-project")


def test_check_external_paths_matches_real_repo_layout(tmp_path) -> None:
    (tmp_path / "resources" / "skills" / "html-animation").mkdir(parents=True)
    (tmp_path / "resources" / "references" / "hyperframes").mkdir(parents=True)
    (tmp_path / "resources" / "skills" / "manim").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "resources" / "skills" / "manim" / "SKILL.md").write_text("", encoding="utf-8")

    result = check_external_paths(tmp_path)

    assert result == {
        "html_skill_root": True,
        "hyperframes_root": True,
        "manim_skill_file": True,
        "docs_root": True,
    }


def test_check_reference_archives_is_optional(tmp_path) -> None:
    (tmp_path / "ClaudeCode").mkdir()
    (tmp_path / "ClaudeCode" / "src.zip").write_text("", encoding="utf-8")
    (tmp_path / "ClaudeCode" / "anthropic-ai-claude-code-2.1.88.tgz").write_text(
        "",
        encoding="utf-8",
    )

    result = check_reference_archives(tmp_path)
    assert result == {
        "claude_code_source_zip": True,
        "claude_code_release_tgz": True,
    }


def test_ensure_workspace_returns_required_and_optional_checks(tmp_path) -> None:
    workspace = ensure_workspace(tmp_path)
    assert "external_paths" in workspace
    assert "reference_archives" in workspace


def test_check_tools_finds_repository_local_environment(tmp_path, monkeypatch) -> None:
    bin_dir = local_tool_bin(tmp_path)
    bin_dir.mkdir(parents=True)
    suffix = ".exe" if sys.platform == "win32" else ""
    for name in ("node", "python", "bun", "ffmpeg", "xelatex", "dvisvgm", "manimgl"):
        (bin_dir / f"{name}{suffix}").write_text("", encoding="utf-8")

    monkeypatch.setattr("manimind.bootstrap.which", lambda _name: None)

    assert resolve_tool("ffmpeg", tmp_path) == str(bin_dir / f"ffmpeg{suffix}")
    assert check_tools(tmp_path) == {
        "node": True,
        "python": True,
        "bun": True,
        "ffmpeg": True,
        "xelatex": True,
        "dvisvgm": True,
        "manimgl": True,
        "manim": False,
    }
