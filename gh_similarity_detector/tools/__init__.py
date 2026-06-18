"""
工具模块

Author: ModuleMirror
"""

from .profile_detect import (
    check_scalene_installed,
    check_memray_installed,
    run_scalene_profile,
    run_memray_profile,
    profile_similarity_detect,
)
from .mkdocs_setup import generate_mkdocs_config

__all__ = [
    "check_scalene_installed",
    "check_memray_installed",
    "run_scalene_profile",
    "run_memray_profile",
    "profile_similarity_detect",
    "generate_mkdocs_config",
]
