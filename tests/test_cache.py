import pytest
import tempfile
from gh_similarity_detector.infrastructure.cache.fingerprint_cache import FingerprintCache
from gh_similarity_detector.models.entities import Module
from gh_similarity_detector.models.enums import ModuleType
from gh_similarity_detector.models.entities import FingerprintSet


@pytest.fixture
def cache_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def cache(cache_dir):
    return FingerprintCache(cache_dir)


@pytest.fixture
def sample_module():
    return Module(
        name="test_func",
        file_path="test.py",
        module_type=ModuleType.FUNCTION,
        source_code="def foo(x, y): return x + y",
        start_line=1,
        end_line=1,
        language="python",
        token_count=10
    )


class TestFingerprintCache:
    def test_put_and_get(self, cache, sample_module):
        fp_set = FingerprintSet(
            module_id=sample_module.id,
            winnowing_fingerprints={100, 200, 300},
            ast_fingerprints={400, 500},
            token_count=10
        )
        cache.put(sample_module, fp_set)
        
        result = cache.get(sample_module)
        assert result is not None
        assert result.winnowing_fingerprints == {100, 200, 300}
        assert result.ast_fingerprints == {400, 500}

    def test_cache_miss(self, cache, sample_module):
        result = cache.get(sample_module)
        assert result is None

    def test_content_change_invalidates(self, cache, sample_module):
        fp_set = FingerprintSet(
            module_id=sample_module.id,
            winnowing_fingerprints={100, 200},
            token_count=5
        )
        cache.put(sample_module, fp_set)
        
        modified = Module(
            name="test_func",
            file_path="test.py",
            module_type=ModuleType.FUNCTION,
            source_code="def foo(x, y): return x * y",
            start_line=1,
            end_line=1,
            language="python",
            token_count=10
        )
        result = cache.get(modified)
        assert result is None

    def test_flush_persists(self, cache_dir, sample_module):
        cache1 = FingerprintCache(cache_dir)
        fp_set = FingerprintSet(
            module_id=sample_module.id,
            winnowing_fingerprints={100},
            token_count=5
        )
        cache1.put(sample_module, fp_set)
        cache1.flush()
        
        cache2 = FingerprintCache(cache_dir)
        result = cache2.get(sample_module)
        assert result is not None
        assert result.winnowing_fingerprints == {100}

    def test_invalidate(self, cache, sample_module):
        fp_set = FingerprintSet(
            module_id=sample_module.id,
            winnowing_fingerprints={100},
            token_count=5
        )
        cache.put(sample_module, fp_set)
        cache.invalidate(sample_module.id)
        assert cache.get(sample_module) is None

    def test_content_hash_deterministic(self):
        h1 = FingerprintCache.compute_content_hash("def foo(): pass")
        h2 = FingerprintCache.compute_content_hash("def foo(): pass")
        assert h1 == h2
        
        h3 = FingerprintCache.compute_content_hash("def bar(): pass")
        assert h1 != h3
