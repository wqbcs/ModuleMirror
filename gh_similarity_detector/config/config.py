"""
配置管理模块

定义和管理系统配置。

Author: GitHub 项目代码相似度检测工具
"""

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import List, Set, Optional
import os
import yaml
from ..models.enums import ModuleType, ReportFormat

_dotenv_loaded = False


def load_dotenv(env_path: str = ".env") -> None:
    """加载 .env 文件到环境变量（不覆盖已存在的），仅执行一次"""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    path = Path(env_path)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass
class DetectionConfig:
    """检测配置

    Attributes:
        module_granularity: 模块粒度
        supported_languages: 支持的语言列表
        min_token_length: 最小 token 长度
        similarity_threshold: 相似度阈值
        winnowing_window_size: Winnowing 窗口大小
        winnowing_kgram_size: Winnowing k-gram 大小
        exclude_dirs: 排除目录集合
        exclude_file_patterns: 排除文件模式列表
        report_format: 报告格式
        output_path: 输出路径
        parallelism: 并行度
        github_token: GitHub API token
        api_file_limit: API 文件数限制
        enable_cache: 是否启用缓存
        cache_dir: 缓存目录
    """

    module_granularity: ModuleType = ModuleType.FUNCTION
    supported_languages: List[str] = field(default_factory=lambda: ["python", "java", "javascript"])
    min_token_length: int = 50
    similarity_threshold: float = 70.0
    winnowing_window_size: int = 5
    winnowing_kgram_size: int = 15
    exclude_dirs: Set[str] = field(
        default_factory=lambda: {
            "node_modules",
            "venv",
            ".git",
            "__pycache__",
            "dist",
            "build",
            ".idea",
            "target",
            "vendor",
            ".vscode",
            ".github",
            "tests",
            "test",
            "docs",
        }
    )
    exclude_file_patterns: List[str] = field(
        default_factory=lambda: [
            "*.min.js",
            "*.min.css",
            "*.test.*",
            "*.spec.*",
            "package-lock.json",
            "yarn.lock",
            "poetry.lock",
            "*.md",
            "*.txt",
            "*.json",
            "*.yaml",
            "*.yml",
            "*.png",
            "*.jpg",
            "*.gif",
            "*.svg",
            "*.pyc",
            "*.pyo",
            "*.class",
            "*.jar",
        ]
    )
    report_format: ReportFormat = ReportFormat.HTML
    output_path: Path = field(default_factory=lambda: Path("./report"))
    parallelism: int = 4
    github_token: Optional[str] = None
    api_file_limit: int = 1000
    enable_cache: bool = True
    cache_dir: Path = field(default_factory=lambda: Path(".cache"))
    max_diff_lines: int = 200
    deterministic_seed: int = 42
    enable_idempotency_check: bool = True
    use_process_pool: bool = False

    @classmethod
    def strict(cls) -> "DetectionConfig":
        """严格预设：高精度，少量匹配"""
        return cls(
            similarity_threshold=85.0,
            min_token_length=30,
            winnowing_window_size=8,
            winnowing_kgram_size=20,
            module_granularity=ModuleType.FUNCTION,
        )

    @classmethod
    def balanced(cls) -> "DetectionConfig":
        """均衡预设：精度与召回平衡"""
        return cls()

    @classmethod
    def quick(cls) -> "DetectionConfig":
        """快速预设：低精度，大量匹配，快速扫描"""
        return cls(
            similarity_threshold=50.0,
            min_token_length=80,
            winnowing_window_size=3,
            winnowing_kgram_size=10,
            module_granularity=ModuleType.FILE,
        )

    @classmethod
    def from_preset(cls, preset: str) -> "DetectionConfig":
        """从预设名称创建配置

        Args:
            preset: 预设名称 (strict/balanced/quick)

        Returns:
            配置对象
        """
        presets = {
            "strict": cls.strict,
            "balanced": cls.balanced,
            "quick": cls.quick,
        }
        factory = presets.get(preset.lower())
        if factory is None:
            raise ValueError(f"未知预设: {preset}，可选: {list(presets.keys())}")
        return factory()

    def __post_init__(self) -> None:
        load_dotenv()

        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)

        if self.github_token is None:
            self.github_token = os.getenv("GITHUB_TOKEN")

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "DetectionConfig":
        """从 YAML 文件加载配置

        Args:
            yaml_path: YAML 文件路径

        Returns:
            配置对象
        """
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return cls()

        if "module_granularity" in data:
            data["module_granularity"] = ModuleType(data["module_granularity"])

        if "report_format" in data:
            data["report_format"] = ReportFormat(data["report_format"])

        known_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}

        return cls(**filtered_data)

    def to_yaml(self, yaml_path: str) -> None:
        """保存配置到 YAML 文件

        Args:
            yaml_path: YAML 文件路径
        """
        data = {
            "module_granularity": self.module_granularity.value,
            "supported_languages": self.supported_languages,
            "min_token_length": self.min_token_length,
            "similarity_threshold": self.similarity_threshold,
            "winnowing_window_size": self.winnowing_window_size,
            "winnowing_kgram_size": self.winnowing_kgram_size,
            "exclude_dirs": list(self.exclude_dirs),
            "exclude_file_patterns": self.exclude_file_patterns,
            "report_format": self.report_format.value,
            "output_path": str(self.output_path),
            "parallelism": self.parallelism,
            "api_file_limit": self.api_file_limit,
            "enable_cache": self.enable_cache,
            "cache_dir": str(self.cache_dir),
            "max_diff_lines": self.max_diff_lines,
            "deterministic_seed": self.deterministic_seed,
            "enable_idempotency_check": self.enable_idempotency_check,
            "use_process_pool": self.use_process_pool,
        }

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def validate(self) -> bool:
        if self.similarity_threshold < 0 or self.similarity_threshold > 100:
            raise ValueError(f"相似度阈值必须在 0-100 之间，当前值: {self.similarity_threshold}")

        if self.min_token_length < 0:
            raise ValueError(f"最小 token 长度必须 >= 0，当前值: {self.min_token_length}")

        if self.winnowing_window_size < 1:
            raise ValueError(f"Winnowing 窗口大小必须 >= 1，当前值: {self.winnowing_window_size}")

        if self.winnowing_kgram_size < 1:
            raise ValueError(f"k-gram 大小必须 >= 1，当前值: {self.winnowing_kgram_size}")

        if self.winnowing_kgram_size <= self.winnowing_window_size:
            raise ValueError(
                f"k-gram 大小 ({self.winnowing_kgram_size}) 必须大于窗口大小 ({self.winnowing_window_size})"
            )

        if self.parallelism < 1:
            raise ValueError(f"并行度必须 >= 1，当前值: {self.parallelism}")

        if self.api_file_limit < 1:
            raise ValueError(f"API 文件数限制必须 >= 1，当前值: {self.api_file_limit}")

        valid_languages = {"python", "java", "javascript", "typescript", "go", "rust", "c", "cpp"}
        for lang in self.supported_languages:
            if lang not in valid_languages:
                raise ValueError(f"不支持的语言: {lang}，支持的语言: {valid_languages}")

        return True
