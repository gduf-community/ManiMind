"""Shared pytest hooks.

1. manimlib 在 import 时用 argparse 解析 sys.argv（manimlib/config.py 的 parse_cli），
   pytest 自己的参数（-k、-m、--collect-only 等）会让它报 unrecognized arguments 并
   SystemExit(2)。收集阶段临时把 sys.argv 截成只剩程序名，与
   tests/lesson_native_harness.py 的 load_lesson/native_run 做法一致。
2. 按源码信号自动给测试模块打 ``native`` 标记，日常可用 ``-m "not native"`` 跑快速层。
3. ``REQUIREMENTS`` 逐条登记依赖本机环境的测试：缺少仓库内 ``manimgl_env``、被 Git 忽略的
   ``outputs/`` 媒体或外部 CLI 时，加上 ``media``/``local``/``external`` 标记并跳过且写明原因，
   不再报失败（例如在 git worktree 或 CI 里）。环境齐全时照常运行。只按测试 id 精确登记，
   不按文件整体跳过；新增此类测试时在这里补一行。
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

import pytest

NATIVE_SIGNALS = ("manimlib", "lesson_native_harness", "native_run")
_native_cache: dict[Path, bool] = {}

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "manimgl_env"


def _env_tools():
    if not (ENV / "bin/ffmpeg").exists():
        return "仓库内没有 manimgl_env/bin/ffmpeg（bash scripts/setup-manimgl.sh 安装）"
    return None


def _env_in_repository():
    # sandbox-exec 只放行仓库内的解释器；符号链接到别处的 manimgl_env 会被拒绝执行。
    if not (ENV / "bin/python").exists() or ENV.is_symlink():
        return "需要仓库内真实的 manimgl_env（不能是符号链接），渲染沙箱才能执行"
    return None


def _local(relative):
    def check():
        if not (ROOT / relative).exists():
            return f"缺少本机媒体 {relative}（outputs/ 不入 Git，只在原制作机的主检出里）"
        return None
    return check


def _canvas_libraries():
    if not (ROOT / "tools/hyperframes/node_modules/katex/dist").is_dir():
        return "缺少 tools/hyperframes/node_modules（在 tools/hyperframes 里运行 npm ci）"
    return None


def _canvas_render():
    missing = _canvas_libraries() or _env_tools()
    if missing:
        return missing
    try:
        from manimind.canvas import render
        render.node()
        render.browser_path()
    except (RuntimeError, FileNotFoundError) as exc:
        return f"Canvas 渲染环境不全：{exc}"
    return None


def _codex():
    if not shutil.which("codex"):
        return ("本机没有 Codex CLI。注：冻结代码 codex_cli_team.role_request 先检查 CLI 再校验图片，"
                "所以无 CLI 时报不出“外来图片被拒”，待解冻时调整顺序")
    return None


CH02 = "outputs/math-derivative-ch02-basics-20261102"
CH03 = "outputs/math-derivative-ch03-rules-20261102"
REQUIREMENTS = {
    "media": (_env_tools, [
        "tests/test_traceable_film_v2.py::test_current_actual_pixels_pass",
        "tests/test_traceable_film_v2.py::test_actual_v2_source_pin_is_required",
        "tests/test_traceable_film_v2.py::test_self_consistent_but_false_frame_index_is_rejected",
        "tests/test_traceable_film_v2.py::test_same_rgb_bytes_with_wrong_dimensions_are_rejected",
        "tests/test_traceable_film_v2.py::test_regression_requires_distinct_real_context",
        "tests/test_traceable_film_v2.py::test_lossless_preparation_accepts_native_jpeg_timestamps",
        "tests/test_traceable_film_v3.py::test_supervisor_and_original_index_are_immutable",
        "tests/test_traceable_film_v3.py::test_frozen_render_accepts_the_new_review_only_supervisor",
        "tests/test_traceable_film_v3.py::test_dangling_output_symlink_is_rejected_before_any_target_write",
        "tests/test_traceable_film_v3.py::test_all_review_assets_are_checked_not_only_selected_pngs",
        "tests/test_chapter_package_clock.py::test_real_eight_clip_clock_and_order",
        "tests/test_unit_film.py::test_actual_ffmpeg_mix_burn_copy_decode_and_visible_caption_pixels",
    ]),
    "sandbox": (_env_in_repository, [
        "tests/test_freeform_agent.py::test_real_sandbox_allows_tex_but_blocks_private_reads_and_writes",
        "tests/test_visual_first.py::test_real_silent_runtime_smoke",
    ]),
    "canvas": (_canvas_libraries, [
        "tests/test_canvas_project.py::test_assemble_builds_a_silent_hyperframes_composition",
        "tests/test_canvas_project.py::test_span_project_keeps_film_time",
    ]),
    "canvas_render": (_canvas_render, [
        "tests/test_canvas_render.py::test_hyperframes_renders_the_fixture_and_frames_do_not_depend_on_render_order",
    ]),
    "local": None,  # filled below, one path per test
    "external": (_codex, [
        "tests/test_codex_cli_team.py::test_foreign_images_are_rejected_before_native_process",
    ]),
}
LOCAL_MEDIA = {
    "tests/test_derivative_ch02_traceable_v010.py::test_old_02_and_03_consumers_stay_byte_identical": f"{CH03}/visual-v009/render.json",
    "tests/test_derivative_ch02_traceable_v011.py::test_full_original_voice_contract_and_models": f"{CH02}/visual-v010",
    "tests/test_derivative_ch02_traceable_v011.py::test_rendered_02_and_03_sources_permanently_frozen": f"{CH02}/visual-v010/render.json",
    "tests/test_derivative_ch02_traceable_v012.py::test_full_original_voice_complete_baseline_and_graphs": f"{CH02}/visual-v011",
    "tests/test_derivative_ch02_traceable_v012.py::test_all_rendered_02_and_03_dependencies_still_frozen": f"{CH02}/visual-v011/render.json",
    "tests/test_derivative_ch03_traceable_v010.py::test_frozen_consumers_and_versioned_source_manifest_stay_unchanged": f"{CH03}/visual-v009/render.json",
    "tests/test_derivative_ch03_traceable_v011.py::test_all_rendered_parents_remain_frozen": f"{CH03}/visual-v010/render.json",
    "tests/test_derivative_ch07_extremes_v003.py::test_inventory_binds_actual_v001_pixels_not_hidden_numeric_precision": "outputs/math-derivative-ch07-extremes-20261102/visual-v001/frames",
}
MARKER = {"media": "media", "sandbox": "media", "canvas": "local", "canvas_render": "media", "local": "local",
          "external": "external"}


def _requirement(nodeid):
    base = nodeid.split("[", 1)[0]
    if base in LOCAL_MEDIA:
        return "local", _local(LOCAL_MEDIA[base])
    for kind, entry in REQUIREMENTS.items():
        if entry and base in entry[1]:
            return kind, entry[0]
    return None, None


@pytest.hookimpl(hookwrapper=True)
def pytest_collection(session):
    original = sys.argv
    sys.argv = original[:1]
    try:
        yield
    finally:
        sys.argv = original


def _is_native(path: Path) -> bool:
    if path not in _native_cache:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        _native_cache[path] = any(signal in text for signal in NATIVE_SIGNALS)
    return _native_cache[path]


def pytest_collection_modifyitems(config, items):
    for item in items:
        if _is_native(Path(item.path)):
            item.add_marker(pytest.mark.native)
        kind, check = _requirement(item.nodeid)
        if kind:
            item.add_marker(getattr(pytest.mark, MARKER[kind]))
            reason = check()
            if reason:
                item.add_marker(pytest.mark.skip(reason=reason))
