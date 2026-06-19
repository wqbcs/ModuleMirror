"""
数据校验层测试
"""

import pytest
from pydantic import ValidationError

from gh_similarity_detector.utils.validation import (
    DetectRequest,
    PlagiarismRequest,
    ProjectModel,
    ModuleModel,
    FingerprintSetModel,
    SimilarityResultModel,
    DetectionTaskModel,
    SearchRequest,
    ReportRequest,
    validate_github_url,
    validate_project_name,
    validate_file_path,
)


class TestDetectRequest:
    def test_valid_request(self):
        req = DetectRequest(
            source_url="https://github.com/a/b", target_url="https://github.com/c/d"
        )
        assert req.threshold == 0.7

    def test_custom_threshold(self):
        req = DetectRequest(source_url="a", target_url="b", threshold=0.9)
        assert req.threshold == 0.9

    def test_threshold_out_of_range(self):
        with pytest.raises(ValidationError):
            DetectRequest(source_url="a", target_url="b", threshold=1.5)

    def test_empty_url(self):
        with pytest.raises(ValidationError):
            DetectRequest(source_url="   ", target_url="b")

    def test_path_traversal(self):
        with pytest.raises(ValidationError):
            DetectRequest(source_url="../etc/passwd", target_url="b")

    def test_preset_valid(self):
        req = DetectRequest(source_url="a", target_url="b", preset="strict")
        assert req.preset == "strict"

    def test_preset_invalid(self):
        with pytest.raises(ValidationError):
            DetectRequest(source_url="a", target_url="b", preset="invalid")

    def test_url_stripped(self):
        req = DetectRequest(source_url="  a  ", target_url="  b  ")
        assert req.source_url == "a"
        assert req.target_url == "b"


class TestPlagiarismRequest:
    def test_valid_request(self):
        req = PlagiarismRequest(target_url="a", candidate_urls=["b", "c"])
        assert len(req.candidate_urls) == 2

    def test_empty_candidates(self):
        with pytest.raises(ValidationError):
            PlagiarismRequest(target_url="a", candidate_urls=[])

    def test_too_many_candidates(self):
        with pytest.raises(ValidationError):
            PlagiarismRequest(target_url="a", candidate_urls=[str(i) for i in range(51)])

    def test_candidate_with_traversal(self):
        with pytest.raises(ValidationError):
            PlagiarismRequest(target_url="a", candidate_urls=["../etc"])


class TestProjectModel:
    def test_valid_project(self):
        p = ProjectModel(name="test/project", source="github")
        assert p.name == "test/project"
        assert p.language == "python"

    def test_empty_name(self):
        with pytest.raises(ValidationError):
            ProjectModel(name="   ", source="github")

    def test_negative_file_count(self):
        with pytest.raises(ValidationError):
            ProjectModel(name="test", source="github", file_count=-1)


class TestModuleModel:
    def test_valid_module(self):
        m = ModuleModel(
            name="foo",
            file_path="a.py",
            module_type="function",
            start_line=1,
            end_line=10,
            language="python",
        )
        assert m.start_line == 1

    def test_invalid_module_type(self):
        with pytest.raises(ValidationError):
            ModuleModel(
                name="foo",
                file_path="a.py",
                module_type="invalid",
                start_line=1,
                end_line=1,
                language="python",
            )

    def test_end_before_start(self):
        with pytest.raises(ValidationError):
            ModuleModel(
                name="foo",
                file_path="a.py",
                module_type="function",
                start_line=10,
                end_line=1,
                language="python",
            )

    def test_path_traversal(self):
        with pytest.raises(ValidationError):
            ModuleModel(
                name="foo",
                file_path="../etc/passwd",
                module_type="function",
                start_line=1,
                end_line=1,
                language="python",
            )


class TestFingerprintSetModel:
    def test_valid(self):
        f = FingerprintSetModel(module_id="m1", winnowing_fingerprints={1, 2, 3})
        assert len(f.winnowing_fingerprints) == 3

    def test_empty_module_id(self):
        with pytest.raises(ValidationError):
            FingerprintSetModel(module_id="   ")


class TestSimilarityResultModel:
    def test_valid(self):
        r = SimilarityResultModel(source_module_id="m1", target_module_id="m2", similarity=85.5)
        assert r.similarity == 85.5

    def test_similarity_over_100(self):
        with pytest.raises(ValidationError):
            SimilarityResultModel(source_module_id="m1", target_module_id="m2", similarity=150.0)

    def test_negative_similarity(self):
        with pytest.raises(ValidationError):
            SimilarityResultModel(source_module_id="m1", target_module_id="m2", similarity=-1.0)


class TestDetectionTaskModel:
    def test_valid(self):
        t = DetectionTaskModel(target_project="user/repo")
        assert t.status == "pending"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            DetectionTaskModel(target_project="user/repo", status="invalid")

    def test_progress_out_of_range(self):
        with pytest.raises(ValidationError):
            DetectionTaskModel(target_project="user/repo", progress=1.5)


class TestSearchRequest:
    def test_valid(self):
        s = SearchRequest(query="python detector")
        assert s.max_results == 20

    def test_empty_query(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="   ")

    def test_special_chars(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="<script>alert(1)</script>")

    def test_max_results_limit(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", max_results=200)


class TestReportRequest:
    def test_valid(self):
        r = ReportRequest(format="html")
        assert r.format == "html"

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            ReportRequest(format="pdf")


class TestValidateGitHubUrl:
    def test_valid_https(self):
        result = validate_github_url("https://github.com/user/repo")
        assert result == "https://github.com/user/repo"

    def test_valid_ssh(self):
        result = validate_github_url("git@github.com:user/repo.git")
        assert "github.com" in result

    def test_valid_short(self):
        result = validate_github_url("github.com/user/repo")
        assert "user" in result

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_github_url("https://gitlab.com/user/repo")

    def test_empty(self):
        with pytest.raises(ValueError):
            validate_github_url("")

    def test_blank(self):
        with pytest.raises(ValueError):
            validate_github_url("   ")


class TestValidateProjectName:
    def test_valid(self):
        assert validate_project_name("user/repo") == "user/repo"

    def test_empty(self):
        with pytest.raises(ValueError):
            validate_project_name("")

    def test_too_long(self):
        with pytest.raises(ValueError):
            validate_project_name("x" * 201)

    def test_special_chars(self):
        with pytest.raises(ValueError):
            validate_project_name("test;rm -rf /")


class TestValidateFilePath:
    def test_valid(self):
        assert validate_file_path("src/main.py") == "src/main.py"

    def test_traversal(self):
        with pytest.raises(ValueError):
            validate_file_path("../../etc/passwd")

    def test_empty(self):
        with pytest.raises(ValueError):
            validate_file_path("")
