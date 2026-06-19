"""
ResultSink 结果解耦测试

Author: ModuleMirror
"""

import json

from gh_similarity_detector.core.result_sink import (
    ResultSink,
    JsonFileSink,
    InMemorySink,
    CompositeSink,
)


class TestJsonFileSink:
    def test_write_and_flush(self, tmp_path):
        sink = JsonFileSink(str(tmp_path / "results.json"))
        sink.write({"similarity": 0.95, "module": "a"})
        sink.flush()
        output = tmp_path / "results.json"
        assert output.exists()
        data = json.loads(output.read_text())
        assert len(data) == 1
        assert data[0]["similarity"] == 0.95

    def test_write_batch(self, tmp_path):
        sink = JsonFileSink(str(tmp_path / "batch.json"))
        sink.write_batch([{"id": 1}, {"id": 2}])
        sink.flush()
        data = json.loads((tmp_path / "batch.json").read_text())
        assert len(data) == 2

    def test_creates_parent_dirs(self, tmp_path):
        sink = JsonFileSink(str(tmp_path / "deep" / "nested" / "out.json"))
        sink.write({"x": 1})
        sink.flush()
        assert (tmp_path / "deep" / "nested" / "out.json").exists()


class TestInMemorySink:
    def test_write_and_count(self):
        sink = InMemorySink()
        sink.write({"a": 1})
        sink.write({"b": 2})
        assert sink.count == 2

    def test_write_batch(self):
        sink = InMemorySink()
        sink.write_batch([{"i": i} for i in range(5)])
        assert sink.count == 5

    def test_max_size_eviction(self):
        sink = InMemorySink(max_size=3)
        for i in range(10):
            sink.write({"i": i})
        assert sink.count == 3

    def test_get_latest(self):
        sink = InMemorySink()
        for i in range(5):
            sink.write({"i": i})
        latest = sink.get_latest(2)
        assert len(latest) == 2
        assert latest[0]["i"] == 3
        assert latest[1]["i"] == 4

    def test_flush_noop(self):
        sink = InMemorySink()
        sink.write({"x": 1})
        sink.flush()
        assert sink.count == 1


class TestCompositeSink:
    def test_writes_to_all_sinks(self):
        s1 = InMemorySink()
        s2 = InMemorySink()
        composite = CompositeSink([s1, s2])
        composite.write({"val": 42})
        assert s1.count == 1
        assert s2.count == 1

    def test_error_isolation(self):
        class FailingSink(ResultSink):
            def write(self, result): raise RuntimeError("fail")
            def write_batch(self, results): raise RuntimeError("fail")
            def flush(self): raise RuntimeError("fail")

        ok_sink = InMemorySink()
        composite = CompositeSink([FailingSink(), ok_sink])
        composite.write({"x": 1})
        assert ok_sink.count == 1

    def test_flush_all(self):
        s1 = InMemorySink()
        s2 = InMemorySink()
        composite = CompositeSink([s1, s2])
        composite.write({"a": 1})
        composite.flush()
