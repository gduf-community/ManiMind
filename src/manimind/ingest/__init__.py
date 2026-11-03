"""
输入摄取层 —— 统一入口。
提供 load_source_bundle() 给 Explorer 使用。

严格按照 docs/agent-data-protocol.md 第 0 节定义的 SourceBundle 格式。
"""

from dataclasses import dataclass
from typing import Optional

from .markdown_reader import MarkdownNote, MarkdownReader
from .env_reporter import EnvReport, EnvReporter
from .asset_scanner import AssetList, AssetScanner
from .pdf_reader import PaperContent, PdfReader


@dataclass
class SourceBundle:
    """输入摄取层的统一输出，给 Explorer 使用。"""
    paper: Optional[PaperContent] = None
    notes: list[MarkdownNote] = None
    assets: Optional[AssetList] = None
    env_report: Optional[EnvReport] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


def load_source_bundle(
    paper_path: str | None = None,
    note_paths: list[str] | None = None,
) -> SourceBundle:
    """加载所有输入源，返回统一 SourceBundle。

    Args:
        paper_path: PDF 论文路径（可选）
        note_paths: Markdown 笔记路径列表（可选）
    """
    bundle = SourceBundle()

    # 解析 PDF 论文
    if paper_path:
        reader = PdfReader(paper_path)
        bundle.paper = reader.read()

    # 扫描资产
    scanner = AssetScanner()
    bundle.assets = scanner.scan()

    # 读取笔记
    if note_paths:
        for path in note_paths:
            try:
                note = MarkdownReader(path).read()
                bundle.notes.append(note)
            except Exception as e:
                print(f"[警告] 读取笔记失败: {path} — {e}")

    # 环境检测
    reporter = EnvReporter()
    bundle.env_report = reporter.generate()

    return bundle
