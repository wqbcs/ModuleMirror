"""
高级分析模块集成测试 — DataFrame/批量检测/多仓库对比/结果对比

Author: ModuleMirror
"""

import json
import tempfile
from pathlib import Path

from gh_similarity_detector.core.similarity.polars_df import (
    SimilarityDataFrame,
    HAS_POLARS,
)
from gh_similarity_detector.core.comparison.batch_detector import (
    BatchDetector,
    BatchTask,
)
from gh_similarity_detector.core.comparison.multi_repo import (
    MultiProjectResult,
)
from gh_similarity_detector.core.comparison.result_comparator import (
    ResultComparator,
    MatchDiff,
    ResultComparison,
)


SAMPLE_RESULTS = [
    {
        "source_module": "project_a",
        "target_module": "project_b",
        "matches": [
            {"similarity": 0.85, "source_file": "a.py", "target_file": "b.py"},
            {"similarity": 0.72, "source_file": "c.py", "target_file": "d.py"},
        ],
    },
    {
        "source_module": "project_a",
        "target_module": "project_c",
        "matches": [
            {"similarity": 0.95, "source_file": "e.py", "target_file": "f.py"},
        ],
    },
]


class TestSimilarityDataFrame:
    def test_from_results(self):
        if not HAS_POLARS:
            return
        sdf = SimilarityDataFrame()
        sdf.from_results(SAMPLE_RESULTS)
        assert sdf.row_count == 3

    def test_filter_by_threshold(self):
        if not HAS_POLARS:
            return
        sdf = SimilarityDataFrame()
        sdf.from_results(SAMPLE_RESULTS)
        sdf.filter_by_threshold(0.8)
        assert sdf.row_count == 2

    def test_group_by_module(self):
        if not HAS_POLARS:
            return
        sdf = SimilarityDataFrame()
        sdf.from_results(SAMPLE_RESULTS)
        grouped = sdf.group_by_module()
        assert grouped.height > 0

    def test_top_similar_pairs(self):
        if not HAS_POLARS:
            return
        sdf = SimilarityDataFrame()
        sdf.from_results(SAMPLE_RESULTS)
        top = sdf.top_similar_pairs(top_k=5)
        assert top.height > 0

    def test_statistics(self):
        if not HAS_POLARS:
            return
        sdf = SimilarityDataFrame()
        sdf.from_results(SAMPLE_RESULTS)
        stats = sdf.statistics()
        assert stats["total_rows"] == 3
        assert stats["avg_similarity"] > 0

    def test_empty_results(self):
        if not HAS_POLARS:
            return
        sdf = SimilarityDataFrame()
        sdf.from_results([])
        assert sdf.row_count == 0
        stats = sdf.statistics()
        assert stats["total_rows"] == 0

    def test_export_csv(self):
        if not HAS_POLARS:
            return
        sdf = SimilarityDataFrame()
        sdf.from_results(SAMPLE_RESULTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.csv")
            result = sdf.export_csv(path)
            assert result == path
            assert Path(path).exists()

    def test_export_json(self):
        if not HAS_POLARS:
            return
        sdf = SimilarityDataFrame()
        sdf.from_results(SAMPLE_RESULTS)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.json")
            result = sdf.export_json(path)
            assert result == path
            assert Path(path).exists()


class TestBatchDetector:
    def test_load_txt(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("user/repo-a\nuser/repo-b\n# comment\n\nuser/repo-c\n")
            f.flush()
            tasks = BatchDetector.load_tasks(f.name)
            assert len(tasks) == 3
            assert tasks[0].target == "user/repo-a"

    def test_load_csv(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        ) as f:
            f.write("user/repo-a,user/repo-b,user/repo-c\n")
            f.flush()
            tasks = BatchDetector.load_tasks(f.name)
            assert len(tasks) == 1
            assert tasks[0].target == "user/repo-a"
            assert len(tasks[0].candidates) == 2

    def test_load_json(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                [
                    {"target": "user/repo-a", "candidates": ["user/repo-b"]},
                    {"target": "user/repo-c"},
                ],
                f,
            )
            f.flush()
            tasks = BatchDetector.load_tasks(f.name)
            assert len(tasks) == 2

    def test_load_invalid_format(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as f:
            f.write("<test/>")
            f.flush()
            try:
                BatchDetector.load_tasks(f.name)
                assert False, "Should raise ValueError"
            except ValueError as e:
                assert "不支持的文件格式" in str(e)

    def test_load_nonexistent_file(self):
        try:
            BatchDetector.load_tasks("/nonexistent/path.txt")
            assert False, "Should raise FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_batch_task_dataclass(self):
        task = BatchTask(target="user/repo-a", candidates=["user/repo-b"])
        assert task.target == "user/repo-a"
        assert task.candidates == ["user/repo-b"]


class TestResultComparator:
    def test_compare_identical(self):
        from gh_similarity_detector.models.results import DetectionResult

        old = DetectionResult(
            source_project="a", target_project="b", matches=[], statistics={}
        )
        new = DetectionResult(
            source_project="a", target_project="b", matches=[], statistics={}
        )
        comparator = ResultComparator()
        comparison = comparator.compare(old, new)
        assert comparison.unchanged_count >= 0

    def test_compare_added_match(self):
        comparison = ResultComparison(
            source_project="a",
            target_project="b",
            added_matches=[
                MatchDiff(
                    source_module="mod1",
                    target_module="mod2",
                    new_similarity=0.9,
                    change_type="added",
                )
            ],
        )
        summary = comparison.summary()
        assert summary["added"] == 1

    def test_compare_removed_match(self):
        comparison = ResultComparison(
            source_project="a",
            target_project="b",
            removed_matches=[
                MatchDiff(
                    source_module="mod1",
                    target_module="mod2",
                    old_similarity=0.7,
                    change_type="removed",
                )
            ],
        )
        summary = comparison.summary()
        assert summary["removed"] == 1

    def test_match_diff_delta(self):
        diff = MatchDiff(
            source_module="a",
            target_module="b",
            old_similarity=0.5,
            new_similarity=0.8,
            change_type="changed",
        )
        assert abs(diff.delta - 0.3) < 0.001
        assert abs(diff.abs_delta - 0.3) < 0.001

    def test_compare_batch(self):
        from gh_similarity_detector.models.results import DetectionResult

        old = [
            DetectionResult(
                source_project="a", target_project="b", matches=[], statistics={}
            )
        ]
        new = [
            DetectionResult(
                source_project="a", target_project="b", matches=[], statistics={}
            )
        ]
        comparator = ResultComparator()
        comparisons = comparator.compare_batch(old, new)
        assert len(comparisons) == 1

    def test_significant_changes(self):
        comparison = ResultComparison(
            source_project="a",
            target_project="b",
            changed_matches=[
                MatchDiff(
                    source_module="mod1",
                    target_module="mod2",
                    old_similarity=0.5,
                    new_similarity=0.8,
                    change_type="changed",
                )
            ],
            significance_threshold=0.2,
        )
        assert len(comparison.significant_changes) == 1


class TestMultiProjectResult:
    def test_summary(self):
        result = MultiProjectResult(
            mode="one_to_many",
            results={"proj_a": []},
            errors={"proj_b": "failed"},
        )
        summary = result.summary()
        assert summary["mode"] == "one_to_many"
        assert summary["project_count"] == 1
        assert summary["error_count"] == 1

    def test_total_matches(self):
        from gh_similarity_detector.models.results import DetectionResult

        r = DetectionResult(
            source_project="a", target_project="b", matches=[], statistics={}
        )
        result = MultiProjectResult(mode="one_to_many", results={"a": [r]})
        assert result.total_matches == 1


class TestPipelineAnalysisIntegration:
    def test_batch_detect_from_file(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("user/repo-a\nuser/repo-b\n")
            f.flush()
            result = DetectionPipeline.batch_detect_from_file(f.name)
            assert result["total_tasks"] == 2

    def test_compare_results_static(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline

        result = DetectionPipeline.compare_results([], [])
        assert result["total_comparisons"] == 0

    def test_compare_multi_repo_invalid_mode(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.config.config import DetectionConfig

        config = DetectionConfig()
        pipeline = DetectionPipeline(config)
        result = pipeline.compare_multi_repo(
            mode="invalid",
            targets=["a"],
            candidates=["b"],
        )
        assert "error" in result

    def test_tune_minhash_no_datasketch(self):
        from gh_similarity_detector.core.orchestration.pipeline import DetectionPipeline
        from gh_similarity_detector.core.similarity.minhash_tuner import HAS_DATASKETCH

        if not HAS_DATASKETCH:
            result = DetectionPipeline.tune_minhash({}, {})
            assert "error" in result

    def test_recommend_params_empty(self):
        from gh_similarity_detector.core.similarity.minhash_tuner import recommend_params

        best_num_perm, best_l = recommend_params([])
        assert best_num_perm == 128
        assert best_l == 64
