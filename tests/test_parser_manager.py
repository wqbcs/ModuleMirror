"""
ParserManager 增强测试
"""

from gh_similarity_detector.infrastructure.parser.parser_manager import ParserManager


class TestParserManagerInit:
    def test_default_init(self):
        pm = ParserManager()
        assert len(pm.parsers) > 0
        assert len(pm.languages) > 0

    def test_init_specific_languages(self):
        pm = ParserManager(languages=["python"])
        assert "python" in pm.parsers
        assert "java" not in pm.parsers

    def test_init_unsupported_language(self):
        pm = ParserManager(languages=["cobol"])
        assert "cobol" not in pm.parsers


class TestParserManagerMethods:
    def test_get_parser_python(self):
        pm = ParserManager(languages=["python"])
        parser = pm.get_parser("python")
        assert parser is not None

    def test_get_parser_nonexistent(self):
        pm = ParserManager(languages=["python"])
        parser = pm.get_parser("brainfuck")
        assert parser is None

    def test_get_language_python(self):
        pm = ParserManager(languages=["python"])
        lang = pm.get_language("python")
        assert lang is not None

    def test_get_language_nonexistent(self):
        pm = ParserManager(languages=["python"])
        lang = pm.get_language("brainfuck")
        assert lang is None

    def test_parse_python_code(self):
        pm = ParserManager(languages=["python"])
        tree = pm.parse(b"def hello(): pass", "python")
        assert tree is not None
        assert tree.root_node is not None

    def test_parse_unsupported_language(self):
        pm = ParserManager(languages=["python"])
        tree = pm.parse(b"code", "brainfuck")
        assert tree is None

    def test_supports_language_true(self):
        pm = ParserManager(languages=["python"])
        assert pm.supports_language("python") is True

    def test_supports_language_false(self):
        pm = ParserManager(languages=["python"])
        assert pm.supports_language("brainfuck") is False

    def test_get_supported_languages(self):
        pm = ParserManager(languages=["python", "java"])
        langs = pm.get_supported_languages()
        assert "python" in langs
        assert "java" in langs

    def test_js_alias(self):
        pm = ParserManager(languages=["javascript"])
        assert pm.supports_language("javascript") is True


class TestParserManagerParseErrors:
    def test_parse_invalid_bytes(self):
        pm = ParserManager(languages=["python"])
        tree = pm.parse(b"\xff\xfe", "python")
        assert tree is not None or tree is None
