"""Agents module for llm-common."""

from llm_common.agents.executor import AgenticExecutor, StreamEvent
from llm_common.agents.message_history import MessageHistory
from llm_common.agents.planner import TaskPlanner
from llm_common.agents.provenance import (
    Evidence,
    EvidenceEnvelope,
    ValidatedCitations,
    validate_citations,
)
from llm_common.agents.research_agent import ResearchAgent
from llm_common.agents.schemas import (
    ExecutionPlan,
    PlannedTask,
    SubTask,
    SubTaskResult,
    ToolCall,
)

# Answer synthesis (bd-sdxe)
from llm_common.agents.synthesizer import (
    AnswerSynthesizer,
    StructuredAnswer,
)
from llm_common.agents.tool_context import ToolContextManager

# Tool framework (bd-sdxe)
from llm_common.agents.tools import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolRegistry,
    ToolResult,
)
from llm_common.agents.ui_smoke_agent import BrowserAdapter, UISmokeAgent
from llm_common.agents.utils import load_stories_from_directory
from llm_common.providers.zai_client import GLMConfig, GLMVisionClient

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
    "StreamEvent",
    "ToolContextManager",
    "ResearchAgent",
    "UISmokeAgent",
    "BrowserAdapter",
    "load_stories_from_directory",
    # Message history
    "MessageHistory",
    # Provenance
    "Evidence",
    "EvidenceEnvelope",
    "ValidatedCitations",
    "validate_citations",
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

