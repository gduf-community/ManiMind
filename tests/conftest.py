"""Shared pytest hooks.

1. manimlib 在 import 时用 argparse 解析 sys.argv（manimlib/config.py 的 parse_cli），
   pytest 自己的参数（-k、-m、--collect-only 等）会让它报 unrecognized arguments 并
   SystemExit(2)。收集阶段临时把 sys.argv 截成只剩程序名，与
   tests/lesson_native_harness.py 的 load_lesson/native_run 做法一致。
2. 按源码信号自动给测试模块打 ``native`` 标记，日常可用 ``-m "not native"`` 跑快速层。
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

NATIVE_SIGNALS = ("manimlib", "lesson_native_harness", "native_run")
_native_cache: dict[Path, bool] = {}


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
