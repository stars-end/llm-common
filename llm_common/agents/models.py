"""Data models for E2E Smoke Agent."""

from dataclasses import dataclass, field
from typing import Literal, Any


@dataclass
class AgentErrorData:
    """Error detected during smoke test execution."""
    type: str  # ui_error, api_5xx, console_error, navigation_error, etc.
    severity: Literal["blocker", "high", "medium", "low"]
    message: str
    url: str | None = None
    details: dict = field(default_factory=dict)


@dataclass
class StepResult:
    """Result of executing a single story step."""
    step_id: str
    status: Literal["pass", "fail", "skip"]
    actions_taken: list[dict] = field(default_factory=list)
    errors: list[AgentErrorData] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class StoryResult:
    """Result of executing a complete story."""
    story_id: str
    status: Literal["pass", "fail"]
    step_results: list[StepResult] = field(default_factory=list)
    errors: list[AgentErrorData] = field(default_factory=list)


@dataclass
class SmokeRunReport:
    """Complete smoke test run report."""
    run_id: str
    environment: str
    base_url: str
    story_results: list[StoryResult]
    total_errors: dict[str, int]
    started_at: str
    completed_at: str
    metadata: dict = field(default_factory=dict)


@dataclass
class StoryStep:
    """A single step in a user story."""
    id: str
    description: str
    exploration_budget: int = 0


@dataclass
class Story:
    """User story specification."""
    id: str
    persona: str
    steps: list[StoryStep]
    metadata: dict = field(default_factory=dict)


@dataclass
class GLMResponse:
    """Response from GLM API."""
    content: str | None
    tool_calls: list[dict] | None
    finish_reason: str
    usage: dict = field(default_factory=dict)
