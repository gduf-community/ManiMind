"""PDF 文本提取器 — 基于 pypdf，解析论文 PDF 为结构化 PaperContent。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class PaperContent:
    """PDF 解析输出，对应 agent-data-protocol.md 第 0.2 节。"""
    path: str
    exists: bool
    text: str | None = None
    extracted_at: datetime = field(default_factory=datetime.now)
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "exists": self.exists,
            "text": self.text,
            "extracted_at": self.extracted_at.isoformat(),
            "parse_warnings": self.parse_warnings,
        }


class PdfReader:
    """PDF 文本提取器，处理编码和公式混排场景。"""

    # 用于过滤不可打印字符但保留 LaTeX/数学符号
    _LATEX_SAFE_CHARS = set("\\{}[]()_^$%&@#\n\t\x0c")

    def __init__(self, file_path: str):
        self.file_path = file_path

    def read(self) -> PaperContent:
        """读取 PDF 文件并提取文本。

        Returns:
            PaperContent: 包含提取的全文文本或错误标记。
        """
        path = Path(self.file_path)
        if not path.exists():
            return PaperContent(
                path=str(path),
                exists=False,
                text=None,
                parse_warnings=["PDF 文件不存在"],
            )

        warnings: list[str] = []
        text_parts: list[str] = []

        try:
            from pypdf import PdfReader as PyPdfReader

            reader = PyPdfReader(str(path))

            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    warnings.append("PDF 已加密且无法自动解密")

            for i, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        cleaned = self._clean_text(page_text)
                        text_parts.append(cleaned)
                except Exception as e:
                    warnings.append(f"第 {i + 1} 页提取失败: {e}")

        except ImportError:
            warnings.append("pypdf 未安装，无法解析 PDF")
        except Exception as e:
            warnings.append(f"PDF 解析异常: {e}")

        full_text = "\n\n".join(text_parts) if text_parts else None
        if text_parts and len(text_parts) < 2:
            warnings.append("PDF 内容较短，可能提取不完整")

        return PaperContent(
            path=str(path),
            exists=True,
            text=full_text,
            parse_warnings=warnings,
        )

    def _clean_text(self, text: str) -> str:
        """清洗提取的文本，保留 LaTeX 公式字符，移除非法控制字符。"""
        result: list[str] = []
        for ch in text:
            cp = ord(ch)
            if cp < 0x20:
                if ch in self._LATEX_SAFE_CHARS:
                    result.append(ch)
                elif ch in ("\n", "\t", "\r"):
                    result.append(ch)
                else:
                    result.append(" ")
            elif 0x80 <= cp <= 0x9F:
                result.append(" ")
            else:
                result.append(ch)
        return "".join(result)
