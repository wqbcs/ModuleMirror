"""多仓库对比+批量检测测试"""

import json
import csv
import pytest
from unittest.mock import MagicMock

from gh_similarity_detector.core.comparison.multi_repo import (
    MultiRepositoryComparator,
    MultiProjectResult,
)
from gh_similarity_detector.core.comparison.batch_detector import (
    BatchDetector,
    BatchTask,
)


class TestMultiProjectResult:
    def test_empty(self):
        r = MultiProjectResult(mode="one_to_many")
        assert r.total_matches == 0
        assert r.project_count == 0
        assert r.error_count == 0

    def test_with_results(self):
        r = MultiProjectResult(mode="many_to_many")
        r.results["proj_a"] = [MagicMock()]
        r.results["proj_b"] = [MagicMock(), MagicMock()]
        assert r.total_matches == 3
        assert r.project_count == 2

    def test_with_errors(self):
        r = MultiProjectResult(mode="matrix")
        r.errors["proj_a"] = "timeout"
        assert r.error_count == 1

    def test_summary(self):
        r = MultiProjectResult(mode="one_to_many")
        r.results["proj_a"] = [MagicMock()]
        s = r.summary()
        assert s["mode"] == "one_to_many"
        assert s["project_count"] == 1


class TestMultiRepositoryComparator:
    def test_one_to_many(self):
        pipeline = MagicMock()
        pipeline.detect.return_value = [MagicMock()]
        comp = MultiRepositoryComparator(pipeline)
        result = comp.one_to_many("target_a", ["c1", "c2"])
        assert "target_a" in result.results
        assert result.mode == "one_to_many"

    def test_one_to_many_error(self):
        pipeline = MagicMock()
        pipeline.detect.side_effect = Exception("fail")
        comp = MultiRepositoryComparator(pipeline)
        result = comp.one_to_many("target_a", ["c1"])
        assert "target_a" in result.errors

    def test_many_to_many(self):
        pipeline = MagicMock()
        pipeline.detect.return_value = [MagicMock()]
        comp = MultiRepositoryComparator(pipeline)
        result = comp.many_to_many(["t1", "t2"], ["c1"], max_workers=1)
        assert len(result.results) == 2

    def test_matrix(self):
        pipeline = MagicMock()
        pipeline.detect.return_value = [MagicMock()]
        comp = MultiRepositoryComparator(pipeline)
        result = comp.matrix(["p1", "p2", "p3"])
        assert len(result.results) == 3


class TestBatchTask:
    def test_create(self):
        task = BatchTask(target="repo_a", candidates=["repo_b", "repo_c"])
        assert task.target == "repo_a"
        assert len(task.candidates) == 2

    def test_empty_candidates(self):
        task = BatchTask(target="repo_a")
        assert task.candidates == []


class TestBatchDetector:
    def test_load_txt(self, tmp_path):
        txt_file = tmp_path / "targets.txt"
        txt_file.write_text("repo_a\n# comment\nrepo_b\n\nrepo_c\n")
        tasks = BatchDetector.load_tasks(str(txt_file))
        assert len(tasks) == 3
        assert tasks[0].target == "repo_a"

    def test_load_csv(self, tmp_path):
        csv_file = tmp_path / "targets.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["target_a", "candidate_1", "candidate_2"])
            writer.writerow(["target_b", "candidate_3"])
        tasks = BatchDetector.load_tasks(str(csv_file))
        assert len(tasks) == 2
        assert tasks[0].target == "target_a"
        assert len(tasks[0].candidates) == 2

    def test_load_json_list(self, tmp_path):
        json_file = tmp_path / "targets.json"
        data = [
            {"target": "repo_a", "candidates": ["repo_b", "repo_c"]},
            {"target": "repo_d", "candidates": []},
        ]
        json_file.write_text(json.dumps(data))
        tasks = BatchDetector.load_tasks(str(json_file))
        assert len(tasks) == 2
        assert tasks[0].target == "repo_a"

    def test_load_json_single(self, tmp_path):
        json_file = tmp_path / "single.json"
        data = {"target": "repo_a", "candidates": ["repo_b"]}
        json_file.write_text(json.dumps(data))
        tasks = BatchDetector.load_tasks(str(json_file))
        assert len(tasks) == 1

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            BatchDetector.load_tasks("/nonexistent/file.txt")

    def test_load_unsupported_format(self, tmp_path):
        bad_file = tmp_path / "data.yaml"
        bad_file.write_text("key: value")
        with pytest.raises(ValueError):
            BatchDetector.load_tasks(str(bad_file))

    def test_execute(self):
        pipeline = MagicMock()
        pipeline.detect.return_value = [MagicMock()]
        detector = BatchDetector(pipeline)
        tasks = [
            BatchTask(target="t1", candidates=["c1"]),
            BatchTask(target="t2", candidates=["c2"]),
        ]
        result = detector.execute(tasks)
        assert result.completed == 2
        assert result.failed == 0

    def test_execute_with_default_candidates(self):
        pipeline = MagicMock()
        pipeline.detect.return_value = [MagicMock()]
        detector = BatchDetector(pipeline)
        tasks = [BatchTask(target="t1"), BatchTask(target="t2")]
        result = detector.execute(tasks, default_candidates=["c1"])
        assert result.completed == 2

    def test_execute_no_candidates(self):
        pipeline = MagicMock()
        detector = BatchDetector(pipeline)
        tasks = [BatchTask(target="t1")]
        result = detector.execute(tasks)
        assert result.failed == 1

    def test_execute_error(self):
        pipeline = MagicMock()
        pipeline.detect.side_effect = Exception("fail")
        detector = BatchDetector(pipeline)
        tasks = [BatchTask(target="t1", candidates=["c1"])]
        result = detector.execute(tasks)
        assert result.failed == 1
