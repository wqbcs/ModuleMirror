"""
Polars DataFrame批处理测试

Author: ModuleMirror
"""

import pytest
import tempfile
import os

from gh_similarity_detector.core.similarity.polars_df import SimilarityDataFrame, HAS_POLARS


@pytest.mark.skipif(not HAS_POLARS, reason="polars未安装")
class TestSimilarityDataFrame:
    def test_from_empty_results(self):
        df = SimilarityDataFrame()
        df.from_results([])
        
        assert df.row_count == 0
    
    def test_from_results(self):
        results = [
            {
                "source_module": "module_a",
                "target_module": "module_b",
                "matches": [
                    {"similarity": 0.85, "source_file": "a.py", "target_file": "b.py"},
                    {"similarity": 0.72, "source_file": "a2.py", "target_file": "b2.py"},
                ]
            }
        ]
        
        df = SimilarityDataFrame()
        df.from_results(results)
        
        assert df.row_count == 2
    
    def test_filter_by_threshold(self):
        results = [
            {
                "source_module": "module_a",
                "target_module": "module_b",
                "matches": [
                    {"similarity": 0.95, "source_file": "a.py", "target_file": "b.py"},
                    {"similarity": 0.50, "source_file": "a2.py", "target_file": "b2.py"},
                ]
            }
        ]
        
        df = SimilarityDataFrame()
        df.from_results(results)
        df.filter_by_threshold(0.7)
        
        assert df.row_count == 1
    
    def test_group_by_module(self):
        results = [
            {
                "source_module": "module_a",
                "target_module": "module_b",
                "matches": [
                    {"similarity": 0.85, "source_file": "a.py", "target_file": "b.py"},
                    {"similarity": 0.75, "source_file": "a2.py", "target_file": "b2.py"},
                ]
            }
        ]
        
        df = SimilarityDataFrame()
        df.from_results(results)
        grouped = df.group_by_module()
        
        assert grouped.height == 1
        assert grouped["avg_similarity"][0] == pytest.approx(0.8, rel=0.01)
    
    def test_top_similar_pairs(self):
        results = [
            {
                "source_module": f"module_{i}",
                "target_module": f"module_{i+1}",
                "matches": [{"similarity": 0.8 + i * 0.01, "source_file": "a.py", "target_file": "b.py"}]
            }
            for i in range(20)
        ]
        
        df = SimilarityDataFrame()
        df.from_results(results)
        top_pairs = df.top_similar_pairs(top_k=5)
        
        assert top_pairs.height == 5
    
    def test_statistics(self):
        results = [
            {
                "source_module": "module_a",
                "target_module": "module_b",
                "matches": [
                    {"similarity": 0.9, "source_file": "a.py", "target_file": "b.py"},
                    {"similarity": 0.7, "source_file": "a2.py", "target_file": "b2.py"},
                ]
            }
        ]
        
        df = SimilarityDataFrame()
        df.from_results(results)
        stats = df.statistics()
        
        assert stats["total_rows"] == 2
        assert stats["unique_modules"] == 2
        assert stats["avg_similarity"] == pytest.approx(0.8, rel=0.01)
        assert stats["max_similarity"] == 0.9
        assert stats["min_similarity"] == 0.7
    
    def test_export_csv(self):
        results = [
            {
                "source_module": "module_a",
                "target_module": "module_b",
                "matches": [{"similarity": 0.85, "source_file": "a.py", "target_file": "b.py"}]
            }
        ]
        
        df = SimilarityDataFrame()
        df.from_results(results)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = df.export_csv(os.path.join(tmpdir, "results.csv"))
            
            assert os.path.exists(output_path)
            
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "module_a" in content
    
    def test_export_json(self):
        results = [
            {
                "source_module": "module_a",
                "target_module": "module_b",
                "matches": [{"similarity": 0.85, "source_file": "a.py", "target_file": "b.py"}]
            }
        ]
        
        df = SimilarityDataFrame()
        df.from_results(results)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = df.export_json(os.path.join(tmpdir, "results.json"))
            
            assert os.path.exists(output_path)
    
    def test_build_similarity_matrix(self):
        results = [
            {
                "source_module": "module_a",
                "target_module": "module_b",
                "matches": [{"similarity": 0.85, "source_file": "a.py", "target_file": "b.py"}]
            },
            {
                "source_module": "module_a",
                "target_module": "module_c",
                "matches": [{"similarity": 0.70, "source_file": "a.py", "target_file": "c.py"}]
            }
        ]
        
        df = SimilarityDataFrame()
        df.from_results(results)
        matrix = df.build_similarity_matrix()
        
        assert matrix.height > 0


class TestWithoutPolars:
    def test_without_polars(self):
        if not HAS_POLARS:
            with pytest.raises(ImportError):
                SimilarityDataFrame()
