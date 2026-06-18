"""
大文件流式处理

避免全量加载 source_code 到内存，使用生成器逐块读取。
支持：
1. 逐行生成器（适合代码文件）
2. 固定大小分块（适合二进制/大文本）
3. 内存预算控制
"""

import os
from typing import Iterator, Optional
from pathlib import Path

from ...utils.logger import logger


DEFAULT_CHUNK_SIZE = 64 * 1024
MAX_FILE_SIZE_FOR_FULL_READ = 10 * 1024 * 1024


class StreamReader:
    """流式文件读取器

    对大文件使用生成器逐块读取，
    对小文件一次性读取。
    """

    def __init__(
        self,
        max_file_size: int = MAX_FILE_SIZE_FOR_FULL_READ,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        encoding: str = "utf-8",
    ):
        self._max_file_size = max_file_size
        self._chunk_size = chunk_size
        self._encoding = encoding
        self._bytes_read = 0
        self._files_processed = 0

    @property
    def should_stream(self, file_path: str) -> bool:
        """判断是否需要流式读取"""
        try:
            size = os.path.getsize(file_path)
            return size > self._max_file_size
        except OSError:
            return False

    def read_full(self, file_path: str) -> Optional[str]:
        """一次性读取文件（小文件）"""
        try:
            with open(file_path, "r", encoding=self._encoding, errors="replace") as f:
                content = f.read()
            self._bytes_read += len(content.encode(self._encoding))
            self._files_processed += 1
            return content
        except (IOError, OSError) as e:
            logger.error(f"文件读取失败: {file_path} - {e}")
            return None

    def read_lines(self, file_path: str) -> Iterator[str]:
        """逐行读取文件（生成器）

        适用于代码文件，每行yield一条。
        """
        try:
            with open(file_path, "r", encoding=self._encoding, errors="replace") as f:
                for line in f:
                    self._bytes_read += len(line.encode(self._encoding))
                    yield line.rstrip("\n\r")
            self._files_processed += 1
        except (IOError, OSError) as e:
            logger.error(f"逐行读取失败: {file_path} - {e}")

    def read_chunks(self, file_path: str) -> Iterator[str]:
        """分块读取文件（生成器）

        适用于大文件，每次yield chunk_size 字节。
        """
        try:
            with open(file_path, "r", encoding=self._encoding, errors="replace") as f:
                while True:
                    chunk = f.read(self._chunk_size)
                    if not chunk:
                        break
                    self._bytes_read += len(chunk.encode(self._encoding))
                    yield chunk
            self._files_processed += 1
        except (IOError, OSError) as e:
            logger.error(f"分块读取失败: {file_path} - {e}")

    def read_smart(self, file_path: str) -> str:
        """智能读取：小文件全量，大文件流式拼接

        对于超过 max_file_size 的文件，发出警告。
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return ""

        try:
            size = path.stat().st_size
        except OSError:
            return ""

        if size <= self._max_file_size:
            return self.read_full(file_path) or ""

        logger.warning(
            f"大文件流式读取: {file_path} ({size / 1024 / 1024:.1f}MB > "
            f"{self._max_file_size / 1024 / 1024:.0f}MB)"
        )
        parts = []
        for chunk in self.read_chunks(file_path):
            parts.append(chunk)
        return "".join(parts)

    @property
    def stats(self) -> dict:
        return {
            "bytes_read": self._bytes_read,
            "files_processed": self._files_processed,
            "max_file_size_mb": round(self._max_file_size / 1024 / 1024, 1),
            "chunk_size_kb": round(self._chunk_size / 1024, 1),
        }


stream_reader = StreamReader()
