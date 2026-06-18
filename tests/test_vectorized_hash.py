"""
向量化RollingHash性能测试

Author: ModuleMirror
"""

import pytest
import time
from gh_similarity_detector.core.fingerprint.vectorized_hash import VectorizedRollingHash
from gh_similarity_detector.core.fingerprint.winnowing import RollingHash


class TestVectorizedRollingHash:
    def test_single_sequence_small(self):
        vh = VectorizedRollingHash()
        rh = RollingHash()
        
        seq = ["def", "func", "(", "x", ")", ":"]
        
        v_result = vh.hash_sequence(seq)
        r_result = rh.hash_sequence(seq)
        
        assert v_result == r_result
    
    def test_single_sequence_large(self):
        vh = VectorizedRollingHash()
        rh = RollingHash()
        
        seq = [f"token_{i}" for i in range(100)]
        
        v_result = vh.hash_sequence(seq)
        r_result = rh.hash_sequence(seq)
        
        assert v_result == r_result
    
    def test_batch_sequences(self):
        vh = VectorizedRollingHash()
        
        sequences = [
            [f"token_{i}" for i in range(20)]
            for _ in range(100)
        ]
        
        results = vh.hash_sequences_batch(sequences)
        
        assert len(results) == 100
        assert all(isinstance(r, int) for r in results)
    
    def test_kgrams_vectorized(self):
        vh = VectorizedRollingHash()
        
        tokens = [f"token_{i}" for i in range(100)]
        k = 5
        
        result = vh.hash_kgrams_vectorized(tokens, k)
        
        assert len(result) == len(tokens) - k + 1
        assert all(h > 0 for h in result)
    
    def test_empty_sequence(self):
        vh = VectorizedRollingHash()
        
        assert vh.hash_sequence([]) == 0
        assert len(vh.hash_sequences_batch([])) == 0
    
    def test_performance_comparison_single(self):
        vh = VectorizedRollingHash()
        rh = RollingHash()
        
        seq = [f"token_{i}" for i in range(100)]
        
        v_time = time.perf_counter()
        for _ in range(1000):
            vh.hash_sequence(seq)
        v_time = time.perf_counter() - v_time
        
        r_time = time.perf_counter()
        for _ in range(1000):
            rh.hash_sequence(seq)
        r_time = time.perf_counter() - r_time
        
        print(f"\n向量化: {v_time:.4f}s, 原始: {r_time:.4f}s")
        print(f"加速比: {r_time / v_time:.2f}x")
    
    def test_performance_comparison_batch(self):
        vh = VectorizedRollingHash()
        rh = RollingHash()
        
        sequences = [
            [f"token_{i}" for i in range(50)]
            for _ in range(100)
        ]
        
        v_time = time.perf_counter()
        for _ in range(100):
            vh.hash_sequences_batch(sequences)
        v_time = time.perf_counter() - v_time
        
        r_time = time.perf_counter()
        for _ in range(100):
            for seq in sequences:
                rh.hash_sequence(seq)
        r_time = time.perf_counter() - r_time
        
        print(f"\n批量向量化: {v_time:.4f}s, 批量原始: {r_time:.4f}s")
        print(f"加速比: {r_time / v_time:.2f}x")
