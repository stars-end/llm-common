from dataclasses import dataclass
from typing import Any, Callable, Protocol


@dataclass
class ToolCallInfo:
    name: str
    args: dict[str, Any]


@dataclass
class ToolCallResult:
    name: str
    args: dict[str, Any]
    summary: str
    success: bool


class AgentCallbacks(Protocol):
    """Protocol for agent execution callbacks."""

    on_iteration_start: Callable[[int], None] | None
    on_thinking: Callable[[str], None] | None
    on_tool_calls_start: Callable[[list[ToolCallInfo]], None] | None
    on_tool_call_complete: Callable[[ToolCallResult], None] | None
    on_iteration_complete: Callable[[int], None] | None
    on_answer_start: Callable[[], None] | None
    on_answer_stream: Callable[[Any], None] | None
