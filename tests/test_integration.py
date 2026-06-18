import pytest
import tempfile
import os
from gh_similarity_detector import DetectionPipeline, DetectionConfig
from gh_similarity_detector.models.enums import ModuleType, ReportFormat


@pytest.fixture
def test_projects():
    base = tempfile.mkdtemp()
    os.makedirs(os.path.join(base, 'project_a'), exist_ok=True)
    os.makedirs(os.path.join(base, 'project_b'), exist_ok=True)

    with open(os.path.join(base, 'project_a', 'utils.py'), 'w') as f:
        f.write('''
def calculate_sum(numbers):
    total = 0
    for n in numbers:
        total += n
    return total

def calculate_average(numbers):
    if not numbers:
        return 0
    return calculate_sum(numbers) / len(numbers)

def filter_positive(numbers):
    return [n for n in numbers if n > 0]
''')

    with open(os.path.join(base, 'project_b', 'helpers.py'), 'w') as f:
        f.write('''
def compute_total(values):
    result = 0
    for v in values:
        result += v
    return result

def compute_mean(values):
    if not values:
        return 0
    return compute_total(values) / len(values)

def sort_descending(values):
    return sorted(values, reverse=True)
''')

    return base


class TestIntegration:
    def test_detect_similar_functions(self, test_projects):
        config = DetectionConfig(
            min_token_length=5,
            similarity_threshold=30.0,
            supported_languages=['python'],
            module_granularity=ModuleType.FUNCTION,
            report_format=ReportFormat.JSON,
            enable_cache=False,
        )
        pipeline = DetectionPipeline(config)
        source = os.path.join(test_projects, 'project_a')
        target = os.path.join(test_projects, 'project_b')
        results = pipeline.detect(source, [target])

        assert len(results) == 1
        assert len(results[0].matches) >= 2
        similarities = [m.similarity for m in results[0].matches]
        assert max(similarities) >= 90.0

    def test_match_has_snippet_info(self, test_projects):
        config = DetectionConfig(
            min_token_length=5,
            similarity_threshold=30.0,
            supported_languages=['python'],
            module_granularity=ModuleType.FUNCTION,
            enable_cache=False,
        )
        pipeline = DetectionPipeline(config)
        source = os.path.join(test_projects, 'project_a')
        target = os.path.join(test_projects, 'project_b')
        results = pipeline.detect(source, [target])

        for r in results:
            for m in r.matches:
                if m.matched_code_snippet:
                    assert 'source_file' in m.matched_code_snippet
                    assert 'target_file' in m.matched_code_snippet

    def test_db_add_and_lookup(self, test_projects):
        config = DetectionConfig(
            min_token_length=5,
            supported_languages=['python'],
            enable_cache=False,
        )
        db_path = os.path.join(test_projects, 'test_db.sqlite')
        pipeline = DetectionPipeline(config, db_path=db_path)

        source = os.path.join(test_projects, 'project_a')
        ok = pipeline.add_to_db(source)
        assert ok

        stats = pipeline.fingerprint_db.get_stats()
        assert stats['project_count'] == 1
        assert stats['module_count'] >= 2

        projects = pipeline.fingerprint_db.list_projects()
        assert len(projects) == 1

    def test_ncd_similarity(self, test_projects):
        from gh_similarity_detector.infrastructure.engines.ncd import NCD
        ncd = NCD()
        source = os.path.join(test_projects, 'project_a')
        target = os.path.join(test_projects, 'project_b')
        sim = ncd.compute_project_similarity(source, target, ['.py'])
        assert 0 <= sim <= 100
