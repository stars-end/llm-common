"""Agents module for llm-common."""

from llm_common.agents.schemas import (
    SubTask,
    PlannedTask,
    ExecutionPlan,
    ToolCall,
    SubTaskResult,
)
from llm_common.agents.planner import TaskPlanner
from llm_common.agents.executor import AgenticExecutor
from llm_common.agents.tool_context import ToolContextManager
from llm_common.agents.research_agent import ResearchAgent
from llm_common.agents.ui_smoke_agent import UISmokeAgent, BrowserAdapter
from llm_common.agents.utils import load_stories_from_directory
from llm_common.providers.zai_client import GLMConfig, GLMVisionClient

# Tool framework (bd-sdxe)
from llm_common.agents.tools import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolResult,
    ToolRegistry,
)

# Answer synthesis (bd-sdxe)
from llm_common.agents.synthesizer import (
    AnswerSynthesizer,
    StructuredAnswer,
)

__all__ = [
    # Schemas
    "SubTask",
    "PlannedTask",
    "ExecutionPlan",
    "ToolCall",
    "SubTaskResult",
    # Core agents
    "TaskPlanner",
    "AgenticExecutor",
    "ToolContextManager",
    "ResearchAgent",
    "UISmokeAgent",
    "BrowserAdapter",
    "load_stories_from_directory",
    # Provider utilities
    "GLMConfig",
    "GLMVisionClient",
    # Tool framework (bd-sdxe)
    "BaseTool",
    "ToolMetadata",
    "ToolParameter",
    "ToolResult",
    "ToolRegistry",
    # Answer synthesis (bd-sdxe)
    "AnswerSynthesizer",
    "StructuredAnswer",
]

