from gh_similarity_detector.infrastructure.engines.jscpd_adapter import JscpdAdapter


class TestJscpdAdapter:
    def test_init(self):
        adapter = JscpdAdapter()
        assert adapter.min_lines == 5
        assert adapter.min_tokens == 50

    def test_not_available_graceful(self):
        adapter = JscpdAdapter()
        if not adapter.is_available:
            results = adapter.detect("/tmp/nonexist1", "/tmp/nonexist2")
            assert results == []
