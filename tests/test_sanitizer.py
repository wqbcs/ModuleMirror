from gh_similarity_detector.core.report.generator import ReportSanitizer


class TestReportSanitizerExtended:
    def setup_method(self):
        self.sanitizer = ReportSanitizer()

    def test_api_key_redacted(self):
        text = 'api_key = "sk-12345"'
        result = self.sanitizer.sanitize(text)
        assert "sk-12345" not in result
        assert "***REDACTED***" in result

    def test_password_redacted(self):
        text = 'password = "secret123"'
        result = self.sanitizer.sanitize(text)
        assert "secret123" not in result

    def test_private_key_redacted(self):
        text = 'private_key = "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC"'
        result = self.sanitizer.sanitize(text)
        assert "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC" not in result

    def test_access_key_redacted(self):
        text = 'access_key = "AKIAIOSFODNN7EXAMPLE"'
        result = self.sanitizer.sanitize(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_secret_key_redacted(self):
        text = 'secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
        result = self.sanitizer.sanitize(text)
        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in result

    def test_connection_string_redacted(self):
        text = 'connection_string = "postgresql://user:pass@host:5432/db"'
        result = self.sanitizer.sanitize(text)
        assert "postgresql://user:pass@host:5432/db" not in result

    def test_database_url_redacted(self):
        text = 'database_url = "mysql://root:pwd@localhost/mydb"'
        result = self.sanitizer.sanitize(text)
        assert "mysql://root:pwd@localhost/mydb" not in result

    def test_rsa_private_key_block_redacted(self):
        text = '-----BEGIN RSA PRIVATE KEY-----\nMIIEvgIBADANBgkq\n-----END RSA PRIVATE KEY-----'
        result = self.sanitizer.sanitize(text)
        assert "MIIEvgIBADANBgkq" not in result
        assert "***REDACTED PRIVATE KEY***" in result

    def test_normal_code_preserved(self):
        text = 'def hello():\n    print("world")\n    x = 42'
        result = self.sanitizer.sanitize(text)
        assert result == text
