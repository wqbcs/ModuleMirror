__version__ = "1.0.0"

from .core import DetectionPipeline
from .config.config import DetectionConfig
from .models.entities import Project, Module, CodeFile, FingerprintSet
from .models.results import SimilarityResult, PlagiarismResult, DetectionResult
from .models.enums import ModuleType, ReportFormat, ReuseSuggestion, TimeRelation, FingerprintType

__all__ = [
    "DetectionPipeline",
    "DetectionConfig",
    "Project",
    "Module",
    "CodeFile",
    "FingerprintSet",
    "SimilarityResult",
    "PlagiarismResult",
    "DetectionResult",
    "ModuleType",
    "ReportFormat",
    "ReuseSuggestion",
    "TimeRelation",
    "FingerprintType",
]
