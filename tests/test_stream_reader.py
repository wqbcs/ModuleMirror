"""
StreamReader 测试

Author: ModuleMirror
"""

import tempfile

from gh_similarity_detector.infrastructure.io.stream_reader import StreamReader


class TestStreamReader:
    def test_read_lines(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            f.flush()
            reader = StreamReader()
            lines = list(reader.read_lines(f.name))
            assert len(lines) == 3
            assert lines[0] == "line1"

    def test_read_chunks(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write("A" * 1000)
            f.flush()
            reader = StreamReader(chunk_size=300)
            chunks = list(reader.read_chunks(f.name))
            assert len(chunks) >= 3

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.flush()
            reader = StreamReader()
            lines = list(reader.read_lines(f.name))
            assert lines == []

    def test_file_not_found(self):
        reader = StreamReader()
        lines = list(reader.read_lines("/nonexistent/file.py"))
        assert lines == []
