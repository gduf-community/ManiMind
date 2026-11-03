"""PDF 读取器单元测试。"""

import tempfile
from pathlib import Path

import pytest

from manimind.ingest.pdf_reader import PaperContent, PdfReader


def test_pdf_reader_file_not_found() -> None:
    """PDF 文件不存在 → 返回 exists=False，带警告。"""
    reader = PdfReader("/nonexistent/path/paper.pdf")
    result = reader.read()

    assert isinstance(result, PaperContent)
    assert result.exists is False
    assert result.text is None
    assert any("不存在" in w for w in result.parse_warnings)


def test_pdf_reader_paper_content_fields() -> None:
    """PaperContent 包含所有必需字段。"""
    reader = PdfReader("/nonexistent/path/paper.pdf")
    result = reader.read()

    assert hasattr(result, "path")
    assert hasattr(result, "exists")
    assert hasattr(result, "text")
    assert hasattr(result, "extracted_at")
    assert hasattr(result, "parse_warnings")
    assert isinstance(result.path, str)
    assert isinstance(result.parse_warnings, list)


def test_pdf_reader_to_dict() -> None:
    """PaperContent.to_dict() 可序列化。"""
    content = PaperContent(path="test.pdf", exists=False, text=None)
    d = content.to_dict()
    assert d["path"] == "test.pdf"
    assert d["exists"] is False
    assert d["text"] is None
    assert "extracted_at" in d


def test_pdf_reader_clean_text_removes_control_chars() -> None:
    """_clean_text 移除非法控制字符但保留 LaTeX 符号。"""
    reader = PdfReader("dummy.pdf")
    dirty = "Hello\x00World\nE=mc^2\tTest\x01\x02"
    cleaned = reader._clean_text(dirty)
    # 不应含有 NUL 或 SOH/STX
    assert "\x00" not in cleaned
    assert "\x01" not in cleaned
    assert "\x02" not in cleaned
    # 应保留正常内容
    assert "Hello" in cleaned
    assert "World" in cleaned
    assert "E=mc^2" in cleaned
    assert "\n" in cleaned
    assert "\t" in cleaned
