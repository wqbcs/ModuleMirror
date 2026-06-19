"""
SSRF 防护测试
"""

import pytest

from gh_similarity_detector.infrastructure.resilience.ssrf_protection import (
    SSRFProtector,
    SSRFError,
    validate_outbound_url,
    default_ssrf_protector,
)


class TestSSRFProtectorURLValidation:
    def test_valid_github_url(self):
        result = default_ssrf_protector.validate_url("https://github.com/user/repo")
        assert result == "https://github.com/user/repo"

    def test_valid_api_url(self):
        result = default_ssrf_protector.validate_url("https://api.github.com/repos/user/repo")
        assert "api.github.com" in result

    def test_valid_raw_content_url(self):
        result = default_ssrf_protector.validate_url(
            "https://raw.githubusercontent.com/user/repo/main/file.py"
        )
        assert "raw.githubusercontent.com" in result

    def test_valid_ssh_url(self):
        result = default_ssrf_protector.validate_url("git@github.com:user/repo.git")
        assert "github.com" in result

    def test_invalid_domain(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("https://evil.com/payload")

    def test_internal_localhost(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("http://localhost/admin")

    def test_internal_127_ip(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("http://127.0.0.1/admin")

    def test_internal_10_ip(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("http://10.0.0.1/secret")

    def test_internal_192_ip(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("http://192.168.1.1/secret")

    def test_internal_172_ip(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("http://172.16.0.1/secret")

    def test_invalid_scheme(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("ftp://github.com/user/repo")

    def test_file_scheme_blocked(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("file:///etc/passwd")

    def test_empty_url(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("")

    def test_no_scheme(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("github.com/user/repo")

    def test_url_too_long(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("https://github.com/" + "a" * 5000)

    def test_control_chars_in_url(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("https://github.com/\x00user/repo")

    def test_link_local_ip(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_url("http://169.254.169.254/metadata")


class TestSSRFProtectorCustomConfig:
    def test_custom_domains(self):
        protector = SSRFProtector(allowed_domains=frozenset({"internal.corp"}))
        result = protector.validate_url("https://internal.corp/api")
        assert "internal.corp" in result

    def test_custom_domains_block_github(self):
        protector = SSRFProtector(allowed_domains=frozenset({"internal.corp"}))
        with pytest.raises(SSRFError):
            protector.validate_url("https://github.com/user/repo")

    def test_allow_private_ip(self):
        protector = SSRFProtector(
            allowed_domains=frozenset({"192.168.1.1", "github.com"}),
            allow_private_ip=True,
        )
        result = protector.validate_url("http://192.168.1.1/api")
        assert "192.168.1.1" in result

    def test_custom_schemes(self):
        protector = SSRFProtector(allowed_schemes=frozenset({"https"}))
        with pytest.raises(SSRFError):
            protector.validate_url("http://github.com/user/repo")


class TestSSRFProtectorResolvedIP:
    def test_valid_public_ip(self):
        result = default_ssrf_protector.validate_resolved_ip("140.82.121.3")
        assert result == "140.82.121.3"

    def test_private_ip_blocked(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_resolved_ip("10.0.0.1")

    def test_loopback_blocked(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_resolved_ip("127.0.0.1")

    def test_invalid_ip(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_resolved_ip("not-an-ip")

    def test_ipv6_private_blocked(self):
        with pytest.raises(SSRFError):
            default_ssrf_protector.validate_resolved_ip("::1")

    def test_allow_private_ip_mode(self):
        protector = SSRFProtector(allow_private_ip=True)
        result = protector.validate_resolved_ip("10.0.0.1")
        assert result == "10.0.0.1"


class TestValidateOutboundURL:
    def test_valid(self):
        result = validate_outbound_url("https://github.com/user/repo")
        assert "github.com" in result

    def test_invalid(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://localhost/secret")
