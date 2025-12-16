"""E2E Smoke Agent package for LLM-powered UI testing.

This module provides:
- UISmokeAgent: Core agent that drives browser via vision LLM
- GLMVisionClient: Z.AI GLM-4.6V client with vision + tool calling
- Story loader and models for test specification
"""

from .exceptions import AgentError, ElementNotFoundError, NavigationError
from .glm_client import BROWSER_TOOLS, GLMConfig, GLMVisionClient
from .models import (
    AgentErrorData,
    GLMResponse,
    SmokeRunReport,
    StepResult,
    Story,
    StoryResult,
    StoryStep,
)
from .story_loader import load_stories_from_directory, load_story
from .ui_smoke_agent import UISmokeAgent

__all__ = [
    # Exceptions
    "AgentError",
    "NavigationError",
    "ElementNotFoundError",
    # GLM Client
    "GLMConfig",
    "GLMVisionClient",
    "GLMResponse",
    "BROWSER_TOOLS",
    # Models
    "AgentErrorData",
    "StepResult",
    "StoryResult",
    "SmokeRunReport",
    "Story",
    "StoryStep",
    # Loaders
    "load_story",
    "load_stories_from_directory",
    # Agent
    "UISmokeAgent",
]
