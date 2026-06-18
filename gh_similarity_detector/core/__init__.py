"""
核心模块

DetectionPipeline 已迁移到 orchestration/pipeline.py，此处保留重导出以兼容旧导入路径。
"""

from .orchestration.pipeline import DetectionPipeline

__all__ = ["DetectionPipeline"]
