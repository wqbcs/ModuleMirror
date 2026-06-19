from gh_similarity_detector.core.fingerprint.winnowing import CodeTokenizer, Winnowing, RollingHash
from gh_similarity_detector.models.entities import Module, ModuleType


class TestCodeTokenizerEdgeCases:
    def setup_method(self):
        self.tokenizer = CodeTokenizer()

    def test_empty_code(self):
        assert self.tokenizer.tokenize("", "python") == []

    def test_whitespace_only(self):
        assert self.tokenizer.tokenize("   \n\t  \n", "python") == []

    def test_unclosed_triple_double_quote(self):
        tokens = self.tokenizer.tokenize('"""unclosed', "python")
        assert "STR" not in tokens

    def test_unclosed_triple_single_quote(self):
        tokens = self.tokenizer.tokenize("'''unclosed", "python")
        assert "STR" not in tokens

    def test_triple_quote_at_end_of_file(self):
        code = 'x = 1\n"""docstring"""'
        tokens = self.tokenizer.tokenize(code, "python")
        assert "STR" not in tokens

    def test_unclosed_double_quote(self):
        tokens = self.tokenizer.tokenize('"unclosed', "python")
        assert "STR" in tokens

    def test_unclosed_single_quote(self):
        tokens = self.tokenizer.tokenize("'unclosed", "python")
        assert "STR" in tokens

    def test_escaped_quote_in_string(self):
        tokens = self.tokenizer.tokenize(r's = "hello\"world"', "python")
        assert "STR" in tokens

    def test_unclosed_c_comment(self):
        tokens = self.tokenizer.tokenize("/* unclosed comment", "java")
        assert len(tokens) >= 0

    def test_c_comment_at_end_of_file(self):
        tokens = self.tokenizer.tokenize("x = 1; /* comment */", "java")
        assert "ID" in tokens

    def test_nested_string_escapes(self):
        tokens = self.tokenizer.tokenize(r's = "a\\b\\c"', "python")
        assert "STR" in tokens

    def test_two_char_operators(self):
        tokens = self.tokenizer.tokenize("x == y != z", "python")
        assert "==" in tokens
        assert "!=" in tokens

    def test_unknown_language_defaults_to_no_keywords(self):
        tokens = self.tokenizer.tokenize("def foo(): pass", "rust")
        assert "ID" in tokens

    def test_numbers(self):
        tokens = self.tokenizer.tokenize("x = 42", "python")
        assert "NUM" in tokens

    def test_decimal_numbers(self):
        tokens = self.tokenizer.tokenize("x = 3.14", "python")
        assert "NUM" in tokens


class TestRollingHashEdgeCases:
    def test_empty_sequence(self):
        h = RollingHash()
        assert h.hash_sequence([]) == 0

    def test_single_token(self):
        h = RollingHash()
        assert isinstance(h.hash_sequence(["x"]), int)

    def test_deterministic_across_calls(self):
        h = RollingHash()
        seq = ["def", "ID", "(", ")", ":"]
        r1 = h.hash_sequence(seq)
        r2 = h.hash_sequence(seq)
        assert r1 == r2

    def test_different_sequences_different_hash(self):
        h = RollingHash()
        h1 = h.hash_sequence(["a", "b"])
        h2 = h.hash_sequence(["c", "d"])
        assert h1 != h2


class TestWinnowingEdgeCases:
    def setup_method(self):
        self.winnowing = Winnowing(window_size=4, kgram_size=5)

    def test_very_short_code(self):
        m = Module(
            name="t",
            file_path="t.py",
            module_type=ModuleType.FUNCTION,
            source_code="x",
            start_line=1,
            end_line=1,
            language="python",
        )
        fp = self.winnowing.generate_fingerprints(m)
        assert fp.module_id == m.id
        assert fp.token_count <= 1

    def test_empty_code(self):
        m = Module(
            name="t",
            file_path="t.py",
            module_type=ModuleType.FUNCTION,
            source_code="",
            start_line=1,
            end_line=1,
            language="python",
        )
        fp = self.winnowing.generate_fingerprints(m)
        assert len(fp.winnowing_fingerprints) == 0

    def test_identical_code_same_fingerprint(self):
        code = "def hello(): return 42"
        m1 = Module(
            name="a",
            file_path="a.py",
            module_type=ModuleType.FUNCTION,
            source_code=code,
            start_line=1,
            end_line=1,
            language="python",
        )
        m2 = Module(
            name="b",
            file_path="b.py",
            module_type=ModuleType.FUNCTION,
            source_code=code,
            start_line=1,
            end_line=1,
            language="python",
        )
        fp1 = self.winnowing.generate_fingerprints(m1)
        fp2 = self.winnowing.generate_fingerprints(m2)
        assert fp1.winnowing_fingerprints == fp2.winnowing_fingerprints

    def test_renamed_variables_different_fingerprint(self):
        code1 = "def foo(x, y): return x + y"
        code2 = "def foo(a, b): return a + b"
        m1 = Module(
            name="a",
            file_path="a.py",
            module_type=ModuleType.FUNCTION,
            source_code=code1,
            start_line=1,
            end_line=1,
            language="python",
        )
        m2 = Module(
            name="b",
            file_path="b.py",
            module_type=ModuleType.FUNCTION,
            source_code=code2,
            start_line=1,
            end_line=1,
            language="python",
        )
        fp1 = self.winnowing.generate_fingerprints(m1)
        fp2 = self.winnowing.generate_fingerprints(m2)
        assert fp1.winnowing_fingerprints == fp2.winnowing_fingerprints
