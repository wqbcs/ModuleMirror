"""
FingerprintGenerator 直接单元测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.fingerprint.generator import FingerprintGenerator
from gh_similarity_detector.config.config import DetectionConfig
from gh_similarity_detector.models.entities import Module


def _make_module(id="test.py", code="def hello(): return 1", language="python"):
    return Module(
        id=id,
        name=id,
        file_path=id,
        source_code=code,
        module_type="function",
        start_line=1,
        end_line=1,
        language=language,
    )


class TestFingerprintGenerator:
    def test_generate_python(self):
        config = DetectionConfig(supported_languages=["python"])
        gen = FingerprintGenerator(config)
        module = _make_module(code="def hello():\n    print('hello')\n")
        result = gen.generate_fingerprints(module)
        assert result is not None

    def test_generate_java(self):
        config = DetectionConfig(supported_languages=["java"])
        gen = FingerprintGenerator(config)
        module = _make_module(
            id="Main.java",
            code="public class Main { public static void main(String[] args) {} }",
            language="java",
        )
        result = gen.generate_fingerprints(module)
        assert result is not None

    def test_generate_javascript(self):
        config = DetectionConfig(supported_languages=["javascript"])
        gen = FingerprintGenerator(config)
        module = _make_module(
            id="hello.js",
            code="function hello() { console.log('hello'); }",
            language="javascript",
        )
        result = gen.generate_fingerprints(module)
        assert result is not None

    def test_generate_empty_code(self):
        config = DetectionConfig()
        gen = FingerprintGenerator(config)
        module = _make_module(code="")
        result = gen.generate_fingerprints(module)
        assert result is not None

    def test_generate_unsupported_language(self):
        config = DetectionConfig()
        gen = FingerprintGenerator(config)
        module = _make_module(id="test.xyz", code="code", language="brainfuck")
        result = gen.generate_fingerprints(module)
        assert result is not None

    def test_generate_batch(self):
        config = DetectionConfig()
        gen = FingerprintGenerator(config)
        modules = {
            "a.py": [_make_module(id="a.py", code="def a(): return 1")],
            "b.py": [_make_module(id="b.py", code="def b(): return 2")],
        }
        results = gen.generate_fingerprints_batch(modules)
        assert len(results) == 2
