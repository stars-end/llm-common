"""
Unified Verification Framework for GLM-4.6V powered E2E testing.

This package provides a consistent verification framework across
affordabot (RAG pipeline) and prime-radiant (user stories).
"""

from .framework import (
    UnifiedVerifier,
    VerificationStory,
    VerificationConfig,
    VerificationReport,
    StoryResult,
    StoryCategory,
    StoryStatus,
)
from .report_generator import ReportGenerator
from .artifact_manager import ArtifactManager

__all__ = [
    # Core classes
    "UnifiedVerifier",
    "VerificationStory",
    "VerificationConfig",
    "VerificationReport",
    "StoryResult",
    # Enums
    "StoryCategory",
    "StoryStatus",
    # Utilities
    "ReportGenerator",
    "ArtifactManager",
]
