import pytest
from gh_similarity_detector.core.module.extractor import ModuleExtractor
from gh_similarity_detector.models.entities import CodeFile
from gh_similarity_detector.models.enums import ModuleType
from gh_similarity_detector.config.config import DetectionConfig


@pytest.fixture
def config():
    return DetectionConfig(min_token_length=5, supported_languages=["python"])


@pytest.fixture
def extractor(config):
    return ModuleExtractor(config)


SAMPLE_CODE = '''
def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    result = a + b
    return result

class Calculator:
    def __init__(self, value=0):
        self.value = value

    def add(self, x):
        self.value += x
        return self.value

    def multiply(self, x):
        self.value *= x
        return self.value
'''


class TestModuleExtractor:
    def test_extract_functions(self, extractor):
        f = CodeFile(path="calc.py", content=SAMPLE_CODE, language="python")
        modules = extractor.extract_modules(f, ModuleType.FUNCTION)
        names = [m.name for m in modules]
        assert "calculate_sum" in names
        assert "__init__" in names
        assert "add" in names

    def test_extract_classes(self, extractor):
        f = CodeFile(path="calc.py", content=SAMPLE_CODE, language="python")
        modules = extractor.extract_modules(f, ModuleType.CLASS)
        names = [m.name for m in modules]
        assert "Calculator" in names

    def test_extract_file_module(self, extractor):
        f = CodeFile(path="calc.py", content=SAMPLE_CODE, language="python")
        modules = extractor.extract_modules(f, ModuleType.FILE)
        assert len(modules) == 1
        assert modules[0].name == "calc"

    def test_module_has_source_code(self, extractor):
        f = CodeFile(path="calc.py", content=SAMPLE_CODE, language="python")
        modules = extractor.extract_modules(f, ModuleType.FUNCTION)
        for m in modules:
            assert len(m.source_code) > 0

    def test_module_line_range(self, extractor):
        f = CodeFile(path="calc.py", content=SAMPLE_CODE, language="python")
        modules = extractor.extract_modules(f, ModuleType.FUNCTION)
        for m in modules:
            assert m.start_line >= 1
            assert m.end_line >= m.start_line

    def test_unsupported_language(self, extractor):
        f = CodeFile(path="test.rs", content="fn main() {}", language="rust")
        modules = extractor.extract_modules(f, ModuleType.FUNCTION)
        assert modules == []
