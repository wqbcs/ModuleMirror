"""
配置管理测试
"""

import pytest
from pathlib import Path
from gh_similarity_detector.config.config import DetectionConfig, load_dotenv
from gh_similarity_detector.models.enums import ModuleType


class TestDetectionConfig:

    def test_default_values(self):
        config = DetectionConfig()
        assert config.module_granularity == ModuleType.FUNCTION
        assert config.similarity_threshold == 70.0
        assert config.winnowing_window_size == 5
        assert config.winnowing_kgram_size == 15
        assert config.parallelism == 4
        assert config.enable_cache is True

    def test_validate_valid(self):
        config = DetectionConfig()
        assert config.validate() is True

    def test_validate_threshold_out_of_range(self):
        config = DetectionConfig(similarity_threshold=150)
        with pytest.raises(ValueError, match="相似度阈值"):
            config.validate()

    def test_validate_negative_tokens(self):
        config = DetectionConfig(min_token_length=-1)
        with pytest.raises(ValueError, match="最小 token"):
            config.validate()

    def test_validate_kgram_le_window(self):
        config = DetectionConfig(winnowing_kgram_size=5, winnowing_window_size=5)
        with pytest.raises(ValueError, match="k-gram"):
            config.validate()

    def test_validate_invalid_language(self):
        config = DetectionConfig(supported_languages=["cobol"])
        with pytest.raises(ValueError, match="不支持的语言"):
            config.validate()

    def test_validate_parallelism(self):
        config = DetectionConfig(parallelism=0)
        with pytest.raises(ValueError, match="并行度"):
            config.validate()

    def test_from_yaml_and_to_yaml(self, tmp_path):
        yaml_path = str(tmp_path / "config.yaml")
        config = DetectionConfig(
            similarity_threshold=85.0,
            supported_languages=["python", "java"],
            parallelism=8,
        )
        config.to_yaml(yaml_path)

        loaded = DetectionConfig.from_yaml(yaml_path)
        assert loaded.similarity_threshold == 85.0
        assert loaded.supported_languages == ["python", "java"]
        assert loaded.parallelism == 8

    def test_string_path_conversion(self):
        config = DetectionConfig(output_path="/tmp/reports", cache_dir="/tmp/cache")
        assert isinstance(config.output_path, Path)
        assert isinstance(config.cache_dir, Path)


class TestLoadDotenv:

    def test_load_dotenv_missing_file(self):
        load_dotenv("/nonexistent/.env")

    def test_load_dotenv_creates_env_vars(self, tmp_path):
        env_path = str(tmp_path / ".env")
        with open(env_path, 'w') as f:
            f.write("TEST_GH_SIM_VAR=hello\n# comment\nANOTHER_VAR=world\n")

        import os
        import gh_similarity_detector.config.config as config_mod
        config_mod._dotenv_loaded = False
        os.environ.pop("TEST_GH_SIM_VAR", None)
        os.environ.pop("ANOTHER_VAR", None)

        load_dotenv(env_path)

        assert os.environ.get("TEST_GH_SIM_VAR") == "hello"
        assert os.environ.get("ANOTHER_VAR") == "world"

        os.environ.pop("TEST_GH_SIM_VAR", None)
        os.environ.pop("ANOTHER_VAR", None)
