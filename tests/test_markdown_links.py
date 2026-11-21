"""Relative Markdown links in maintained docs must point at files that exist in the repository."""

from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCANNED_FILES = ("README.md", "AGENTS.md")
SCANNED_DIRS = ("ai", "docs", "作品")
# Not tracked by Git (see .gitignore): local media, runtime state and private archives.
UNTRACKED_PREFIXES = ("outputs/", "runtime/", "logs/", "media/", "archive/local/")

FENCE = re.compile(r"^(```|~~~).*?^\1", re.M | re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+(?:\s+[^)\s\"']+)*)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")


def markdown_files():
    files = [ROOT / name for name in SCANNED_FILES]
    for folder in SCANNED_DIRS:
        files.extend(sorted((ROOT / folder).rglob("*.md")))
    return [path for path in files if path.is_file()]


def relative_links(text):
    text = INLINE_CODE.sub("", FENCE.sub("", text))
    for match in LINK.finditer(text):
        target = match.group(1).strip().strip("<>").strip()
        if not target or target.startswith("#"):
            continue
        url = urlsplit(target)
        if url.scheme or url.netloc:
            continue
        path = unquote(url.path)
        if path:
            yield path


def broken_links(source):
    problems = []
    for target in relative_links(source.read_text(encoding="utf-8")):
        if target.startswith("/"):
            problems.append((target, "absolute_path"))
            continue
        resolved = (source.parent / target).resolve()
        if not resolved.is_relative_to(ROOT):
            problems.append((target, "outside_repository"))
            continue
        relative = resolved.relative_to(ROOT).as_posix()
        if relative.startswith(UNTRACKED_PREFIXES):
            continue
        if not resolved.exists():
            problems.append((target, "missing"))
    return problems


def test_parser_handles_images_spaces_titles_fragments_and_code():
    text = (
        "[a](<有 空格.md#标题>) ![p](图.png \"说明\") [web](https://example.com) [m](mailto:x@example.com)"
        " [top](#本页) `[code](not-a-link.md)`\n```\n[fenced](also-not.md)\n```\n[b](dir/b.md#x)"
    )
    assert list(relative_links(text)) == ["有 空格.md", "图.png", "dir/b.md"]


def test_untracked_and_missing_targets_are_classified(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/ok.md").write_text("ok", encoding="utf-8")
    source = tmp_path / "docs/index.md"
    source.write_text("[ok](ok.md) [media](../outputs/x.mp4) [gone](gone.md) [abs](/etc/hosts) [up](../../x.md)",
                      encoding="utf-8")
    assert broken_links(source) == [
        ("gone.md", "missing"), ("/etc/hosts", "absolute_path"), ("../../x.md", "outside_repository")]


def test_maintained_markdown_links_resolve():
    files = markdown_files()
    assert files, "no Markdown files scanned"
    failures = [f"{path.relative_to(ROOT).as_posix()}: {target} ({kind})"
                for path in files for target, kind in broken_links(path)]
    assert not failures, "Broken relative Markdown links:\n" + "\n".join(failures)
