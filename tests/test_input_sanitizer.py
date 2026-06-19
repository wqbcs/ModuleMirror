"""
输入消毒测试 - 路径遍历 + 命令注入 + ReDoS
"""

import pytest

from gh_similarity_detector.utils.sanitizer import (
    sanitize_path,
    sanitize_command_input,
    sanitize_url,
    check_regex_safety,
    sanitize_string,
    PathTraversalError,
    CommandInjectionError,
    ReDoSVulnerabilityError,
)


class TestSanitizePath:
    def test_valid_relative_path(self):
        assert sanitize_path("src/main.py") == "src/main.py"

    def test_valid_nested_path(self):
        assert sanitize_path("a/b/c/file.py") == "a/b/c/file.py"

    def test_traversal_double_dot(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("../../etc/passwd")

    def test_traversal_tilde(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("~/secret")

    def test_traversal_backslash(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("..\\windows\\system32")

    def test_absolute_path_blocked(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("/etc/passwd")

    def test_absolute_path_allowed(self):
        result = sanitize_path("/tmp/workspace", allow_absolute=True)
        assert result == "/tmp/workspace"

    def test_empty_path(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("")

    def test_blank_path(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("   ")

    def test_path_too_long(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("a/" * 3000)

    def test_path_too_deep(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("/".join([f"d{i}" for i in range(25)]))

    def test_base_dir_confinement(self):
        with pytest.raises(PathTraversalError):
            sanitize_path("../../../etc/passwd", base_dir="/workspace")


class TestSanitizeCommandInput:
    def test_valid_input(self):
        assert sanitize_command_input("user_repo") == "user_repo"

    def test_valid_url(self):
        assert (
            sanitize_command_input("https://github.com/user/repo") == "https://github.com/user/repo"
        )

    def test_semicolon_injection(self):
        with pytest.raises(CommandInjectionError):
            sanitize_command_input("test; rm -rf /")

    def test_pipe_injection(self):
        with pytest.raises(CommandInjectionError):
            sanitize_command_input("test | cat /etc/passwd")

    def test_ampersand_injection(self):
        with pytest.raises(CommandInjectionError):
            sanitize_command_input("test && malicious")

    def test_backtick_injection(self):
        with pytest.raises(CommandInjectionError):
            sanitize_command_input("test `rm -rf /`")

    def test_dollar_injection(self):
        with pytest.raises(CommandInjectionError):
            sanitize_command_input("test $HOME")

    def test_backslash_injection(self):
        with pytest.raises(CommandInjectionError):
            sanitize_command_input("test\\nmalicious")

    def test_empty_input(self):
        with pytest.raises(CommandInjectionError):
            sanitize_command_input("")

    def test_too_long_input(self):
        with pytest.raises(CommandInjectionError):
            sanitize_command_input("a" * 5000)


class TestSanitizeUrl:
    def test_valid_github_https(self):
        result = sanitize_url("https://github.com/user/repo")
        assert result == "https://github.com/user/repo"

    def test_valid_github_api(self):
        result = sanitize_url("https://api.github.com/repos/user/repo")
        assert "api.github.com" in result

    def test_valid_gist(self):
        result = sanitize_url("https://gist.github.com/user/12345")
        assert "gist.github.com" in result

    def test_invalid_domain(self):
        with pytest.raises(PathTraversalError):
            sanitize_url("https://evil.com/payload")

    def test_invalid_scheme(self):
        with pytest.raises(PathTraversalError):
            sanitize_url("ftp://github.com/user/repo")

    def test_empty_url(self):
        with pytest.raises(PathTraversalError):
            sanitize_url("")

    def test_git_scheme_allowed(self):
        result = sanitize_url("git@github.com:user/repo.git")
        assert "github.com" in result


class TestCheckRegexSafety:
    def test_safe_regex(self):
        assert check_regex_safety(r"^\d+$") == r"^\d+$"

    def test_safe_word_regex(self):
        assert check_regex_safety(r"\w+@\w+\.\w+") == r"\w+@\w+\.\w+"

    def test_nested_quantifier(self):
        with pytest.raises(ReDoSVulnerabilityError):
            check_regex_safety(r"(a+)+")

    def test_nested_star(self):
        with pytest.raises(ReDoSVulnerabilityError):
            check_regex_safety(r"(a*)*")

    def test_empty_pattern(self):
        with pytest.raises(ReDoSVulnerabilityError):
            check_regex_safety("")

    def test_too_long_pattern(self):
        with pytest.raises(ReDoSVulnerabilityError):
            check_regex_safety("a" * 600)

    def test_invalid_regex(self):
        with pytest.raises(ReDoSVulnerabilityError):
            check_regex_safety(r"[unclosed")


class TestSanitizeString:
    def test_normal_string(self):
        assert sanitize_string("hello world") == "hello world"

    def test_control_chars_removed(self):
        result = sanitize_string("hello\x00world\x1f")
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_whitespace_trimmed(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_truncation(self):
        result = sanitize_string("a" * 5000, max_length=100)
        assert len(result) == 100

    def test_empty_string(self):
        assert sanitize_string("") == ""

    def test_none_passthrough(self):
        assert sanitize_string("") == ""
