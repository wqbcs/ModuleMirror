import pytest
from gh_similarity_detector.core.fingerprint.winnowing import Winnowing, CodeTokenizer, RollingHash
from gh_similarity_detector.models.entities import Module, FingerprintSet
from gh_similarity_detector.models.enums import ModuleType


@pytest.fixture
def winnowing():
    return Winnowing(window_size=5, kgram_size=15)


@pytest.fixture
def tokenizer():
    return CodeTokenizer()


class TestRollingHash:
    def test_same_sequence_same_hash(self):
        h = RollingHash()
        assert h.hash_sequence(["a", "b", "c"]) == h.hash_sequence(["a", "b", "c"])

    def test_different_sequence_different_hash(self):
        h = RollingHash()
        assert h.hash_sequence(["a", "b", "c"]) != h.hash_sequence(["x", "y", "z"])


class TestCodeTokenizer:
    def test_python_keywords_preserved(self, tokenizer):
        tokens = tokenizer.tokenize("def foo():", "python")
        assert "def" in tokens

    def test_identifiers_normalized(self, tokenizer):
        tokens = tokenizer.tokenize("foo bar baz", "python")
        assert tokens == ["ID", "ID", "ID"]

    def test_strings_normalized(self, tokenizer):
        tokens = tokenizer.tokenize('"hello" \'world\'', "python")
        assert tokens == ["STR", "STR"]

    def test_numbers_normalized(self, tokenizer):
        tokens = tokenizer.tokenize("42 3.14", "python")
        assert tokens == ["NUM", "NUM"]

    def test_comments_skipped(self, tokenizer):
        tokens1 = tokenizer.tokenize("x = 1", "python")
        tokens2 = tokenizer.tokenize("x = 1  # comment", "python")
        assert tokens1 == tokens2

    def test_whitespace_skipped(self, tokenizer):
        tokens1 = tokenizer.tokenize("a b c", "python")
        tokens2 = tokenizer.tokenize("a  b   c", "python")
        assert tokens1 == tokens2

    def test_rename_invariant(self, tokenizer):
        code1 = "def foo(x, y): return x + y"
        code2 = "def bar(a, b): return a + b"
        assert tokenizer.tokenize(code1, "python") == tokenizer.tokenize(code2, "python")


class TestWinnowing:
    def test_identical_code_same_fingerprints(self, winnowing):
        code = "def calculate(a, b): return a * b + a / b"
        fp1 = winnowing.generate_fingerprints_from_code(code, "python")
        fp2 = winnowing.generate_fingerprints_from_code(code, "python")
        assert fp1.winnowing_fingerprints == fp2.winnowing_fingerprints

    def test_rename_invariant(self, winnowing):
        code1 = "def process(data, config): result = transform(data, config); return result"
        code2 = "def handle(input, settings): output = convert(input, settings); return output"
        fp1 = winnowing.generate_fingerprints_from_code(code1, "python")
        fp2 = winnowing.generate_fingerprints_from_code(code2, "python")
        assert fp1.winnowing_fingerprints == fp2.winnowing_fingerprints

    def test_different_code_different_fingerprints(self, winnowing):
        code1 = "def sort_array(data): result = sorted(data, key=lambda x: x.name); return result"
        code2 = "def fetch_resource(url): response = http.get(url); return response.json()"
        fp1 = winnowing.generate_fingerprints_from_code(code1, "python")
        fp2 = winnowing.generate_fingerprints_from_code(code2, "python")
        assert fp1.winnowing_fingerprints != fp2.winnowing_fingerprints

    def test_format_change_invariant(self, winnowing):
        code1 = "def foo():\n    x=1\n    return x"
        code2 = "def foo():\n    x = 1\n    return x"
        fp1 = winnowing.generate_fingerprints_from_code(code1, "python")
        fp2 = winnowing.generate_fingerprints_from_code(code2, "python")
        assert fp1.winnowing_fingerprints == fp2.winnowing_fingerprints

    def test_generate_from_module(self, winnowing):
        module = Module(
            name="test_func",
            file_path="test.py",
            module_type=ModuleType.FUNCTION,
            source_code="def calculate(a, b): return a * b + a / b",
            start_line=1,
            end_line=1,
            language="python",
            token_count=10
        )
        fp = winnowing.generate_fingerprints(module)
        assert isinstance(fp, FingerprintSet)
        assert fp.module_id == module.id
        assert len(fp.winnowing_fingerprints) > 0

    def test_empty_code(self, winnowing):
        fp = winnowing.generate_fingerprints_from_code("", "python")
        assert len(fp.winnowing_fingerprints) == 0

    def test_short_code(self, winnowing):
        fp = winnowing.generate_fingerprints_from_code("x = 1", "python")
        assert len(fp.winnowing_fingerprints) > 0
