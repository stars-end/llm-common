from llm_common.agents.auth import AuthConfig, AuthManager
from llm_common.agents.token_utils import sign_token, verify_token
from llm_common.agents.callbacks import (
    AgentCallbacks,
    ToolCallInfo,
    ToolCallResult,
)
from llm_common.agents.context_pointers import (
    ContextPointer,
    ContextRelevanceSelector,
    FileContextPointerStore,
    format_selected_contexts,
)
from llm_common.agents.exceptions import (
    ElementNotFoundError,
    NavigationError,
)
from llm_common.agents.executor import AgenticExecutor, StreamEvent
from llm_common.agents.message_history import Message, MessageHistory

# Orchestrator (Dexter RAG V2)
from llm_common.agents.orchestrator import IterativeOrchestrator, OrchestratorResult

# Phases (Dexter RAG V2)
from llm_common.agents.phases import (
    Entity,
    ReflectionResult,
    ReflectPhase,
    Understanding,
    UnderstandPhase,
)
from llm_common.agents.planner import TaskPlanner
from llm_common.agents.provenance import (
    Evidence,
    EvidenceEnvelope,
    format_tool_result,
    validate_citations,
)
from llm_common.agents.research_agent import ResearchAgent
from llm_common.agents.runtime import AgentRuntime
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
from llm_common.agents.tool_selector import ToolSelectionConfig, ToolSelector

# Tool framework (bd-sdxe)
from llm_common.agents.tools import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolRegistry,
    ToolResult,
)
from llm_common.agents.ui_smoke_agent import BrowserAdapter, UISmokeAgent
from llm_common.agents.utils import load_stories_from_directory, load_story
from llm_common.providers.zai_client import GLMConfig, GLMVisionClient, StreamChunk

__all__ = [
    "ElementNotFoundError",
    "NavigationError",
    # Message History
    "Message",
    "MessageHistory",
    # Schemas
    "SubTask",
    "PlannedTask",
    "ExecutionPlan",
    "ToolCall",
    "SubTaskResult",
    # Callbacks
    "AgentCallbacks",
    "ToolCallInfo",
    "ToolCallResult",
    # Provenance (dmzy.4)
    "Evidence",
    "EvidenceEnvelope",
    "validate_citations",
    "format_tool_result",
    # Core agents
    "TaskPlanner",
    "AgenticExecutor",
    "StreamEvent",
    "ToolContextManager",
    "ResearchAgent",
    "AgentRuntime",
    "UISmokeAgent",
    "BrowserAdapter",
    "load_story",
    "load_stories_from_directory",
    "AuthConfig",
    "AuthManager",
    # Provider utilities
    "GLMConfig",
    "GLMVisionClient",
    "StreamChunk",
    # Tool framework (bd-sdxe)
    "BaseTool",
    "ToolMetadata",
    "ToolParameter",
    "ToolResult",
    "ToolRegistry",
    # Tool selection
    "ToolSelectionConfig",
    "ToolSelector",
    # Context pointers
    "ContextPointer",
    "FileContextPointerStore",
    "ContextRelevanceSelector",
    "format_selected_contexts",
    # Answer synthesis (bd-sdxe)
    "AnswerSynthesizer",
    "StructuredAnswer",
    # Phases (Dexter RAG V2)
    "Entity",
    "Understanding",
    "UnderstandPhase",
    "ReflectionResult",
    "ReflectPhase",
    # Orchestrator (Dexter RAG V2)
    "IterativeOrchestrator",
    "OrchestratorResult",
    "sign_token",
    "verify_token",
]


def __getattr__(name: str):
    if name in {"UISmokeRunner", "uismoke_main"}:
        try:
            from llm_common.agents.uismoke_runner import UISmokeRunner
            from llm_common.agents.uismoke_runner import main as uismoke_main
        except ImportError as e:
            raise ImportError(
                "UISmokeRunner requires the optional Playwright dependency. "
                "Install Playwright (and browsers) in the consuming environment to use uismoke."
            ) from e

        return {"UISmokeRunner": UISmokeRunner, "uismoke_main": uismoke_main}[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
