"""上下文读写层 — runtime 目录的上下文存取与权限校验。"""

from .context_io import context_file_path, read_context, write_context

__all__ = ["context_file_path", "read_context", "write_context"]
