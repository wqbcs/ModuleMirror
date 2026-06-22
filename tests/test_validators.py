from gh_similarity_detector.cli.validators import InputValidator, ValidationError
from gh_similarity_detector.utils.exceptions import ConfigurationError

import pytest


class TestValidateRequired:
    def test_empty_string(self):
        err = InputValidator.validate_required("", "field")
        assert err is not None
        assert err.field == "field"

    def test_whitespace_only(self):
        err = InputValidator.validate_required("   ", "field")
        assert err is not None

    def test_valid_string(self):
        err = InputValidator.validate_required("hello", "field")
        assert err is None


class TestValidateThreshold:
    def test_valid_threshold(self):
        assert InputValidator.validate_threshold(70.0) is None

    def test_zero(self):
        assert InputValidator.validate_threshold(0) is None

    def test_hundred(self):
        assert InputValidator.validate_threshold(100) is None

    def test_negative(self):
        err = InputValidator.validate_threshold(-1)
        assert err is not None

    def test_over_hundred(self):
        err = InputValidator.validate_threshold(101)
        assert err is not None


class TestValidateFilePath:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert InputValidator.validate_file_path(str(f)) is None

    def test_nonexistent_file(self):
        err = InputValidator.validate_file_path("/nonexistent/file.txt")
        assert err is not None


class TestValidateDbPath:
    def test_existing_db(self, tmp_path):
        db = tmp_path / "test.db"
        db.write_text("data")
        assert InputValidator.validate_db_path(str(db)) is None

    def test_nonexistent_db(self):
        err = InputValidator.validate_db_path("/nonexistent/db.sqlite")
        assert err is not None


class TestValidateAll:
    def test_no_errors(self):
        InputValidator.validate_all([None, None])

    def test_with_errors(self):
        with pytest.raises(ConfigurationError):
            InputValidator.validate_all([
                ValidationError("f1", "error1"),
                ValidationError("f2", "error2"),
            ])

    def test_mixed(self):
        with pytest.raises(ConfigurationError):
            InputValidator.validate_all([None, ValidationError("f1", "error1")])
