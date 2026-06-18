"""
SIMD 批处理测试

Author: ModuleMirror
"""

import numpy as np

from gh_similarity_detector.core.fingerprint.simd_batch import (
    SIMDBatchProcessor,
    BatchFingerprint,
)


class TestSIMDBatchProcessor:
    def test_prepare_batch_empty(self):
        processor = SIMDBatchProcessor()
        hashes, modules, positions = processor.prepare_batch([])
        assert len(hashes) == 0
        assert len(modules) == 0
        assert len(positions) == 0

    def test_prepare_batch_single(self):
        processor = SIMDBatchProcessor()
        fingerprints = [{"module_id": 1, "fingerprints": [100, 200, 300]}]
        hashes, modules, positions = processor.prepare_batch(fingerprints)
        assert len(hashes) == 3
        assert list(hashes) == [100, 200, 300]
        assert list(modules) == [1, 1, 1]
        assert list(positions) == [0, 1, 2]

    def test_prepare_batch_multiple(self):
        processor = SIMDBatchProcessor()
        fingerprints = [
            {"module_id": 1, "fingerprints": [100, 200]},
            {"module_id": 2, "fingerprints": [300, 400, 500]},
        ]
        hashes, modules, positions = processor.prepare_batch(fingerprints)
        assert len(hashes) == 5
        assert list(modules) == [1, 1, 2, 2, 2]

    def test_batch_jaccard_identical(self):
        processor = SIMDBatchProcessor()
        set1 = np.array([100, 200, 300], dtype=np.int64)
        set2 = np.array([100, 200, 300], dtype=np.int64)
        result = processor.batch_jaccard(set1, set2)
        assert result == 100.0

    def test_batch_jaccard_disjoint(self):
        processor = SIMDBatchProcessor()
        set1 = np.array([100, 200, 300], dtype=np.int64)
        set2 = np.array([400, 500, 600], dtype=np.int64)
        result = processor.batch_jaccard(set1, set2)
        assert result == 0.0

    def test_batch_jaccard_partial(self):
        processor = SIMDBatchProcessor()
        set1 = np.array([100, 200, 300], dtype=np.int64)
        set2 = np.array([200, 300, 400], dtype=np.int64)
        result = processor.batch_jaccard(set1, set2)
        assert 0 < result < 100
        assert abs(result - 50.0) < 1.0

    def test_batch_jaccard_empty(self):
        processor = SIMDBatchProcessor()
        set1 = np.array([], dtype=np.int64)
        set2 = np.array([100, 200], dtype=np.int64)
        assert processor.batch_jaccard(set1, set2) == 0.0
        assert processor.batch_jaccard(set2, set1) == 0.0
        assert processor.batch_jaccard(set1, set1) == 100.0

    def test_sort_by_hash(self):
        processor = SIMDBatchProcessor()
        hashes = np.array([300, 100, 200], dtype=np.int64)
        modules = np.array([1, 2, 3], dtype=np.int32)
        positions = np.array([0, 0, 0], dtype=np.int32)
        sorted_h, sorted_m, sorted_p = processor.sort_by_hash(hashes, modules, positions)
        assert list(sorted_h) == [100, 200, 300]
        assert list(sorted_m) == [2, 3, 1]

    def test_find_duplicates(self):
        processor = SIMDBatchProcessor()
        hashes = np.array([100, 200, 100, 300, 200], dtype=np.int64)
        modules = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        duplicates = processor.find_duplicates(hashes, modules)
        assert 1 in duplicates
        assert 3 in duplicates[1]
        assert 2 in duplicates
        assert 5 in duplicates[2]

    def test_find_duplicates_no_duplicates(self):
        processor = SIMDBatchProcessor()
        hashes = np.array([100, 200, 300, 400], dtype=np.int64)
        modules = np.array([1, 2, 3, 4], dtype=np.int32)
        duplicates = processor.find_duplicates(hashes, modules)
        assert len(duplicates) == 0

    def test_batch_jaccard_many(self):
        processor = SIMDBatchProcessor()
        query = np.array([100, 200, 300], dtype=np.int64)
        candidates = [
            np.array([100, 200, 300], dtype=np.int64),
            np.array([400, 500], dtype=np.int64),
            np.array([200, 300, 400], dtype=np.int64),
        ]
        results = processor.batch_jaccard_many(query, candidates)
        assert len(results) == 3
        assert results[0] == 100.0
        assert results[1] == 0.0


class TestBatchFingerprint:
    def test_to_dict(self):
        fp = BatchFingerprint(
            module_id=1,
            hash_values=np.array([100, 200]),
            positions=np.array([0, 1]),
        )
        d = fp.to_dict()
        assert d["module_id"] == 1
        assert d["hash_values"] == [100, 200]
        assert d["positions"] == [0, 1]
