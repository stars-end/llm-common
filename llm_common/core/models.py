"""Core data models for LLM framework."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, Enum):
    """Message role in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


class LLMMessage(BaseModel):
    """Single message in conversation."""

    model_config = ConfigDict(use_enum_values=True)

    role: MessageRole
    content: str | list[dict[str, Any]]
    name: str | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None


class LLMUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResponse(BaseModel):
    """Response from LLM completion."""

    id: str
    model: str
    content: str
    role: MessageRole = MessageRole.ASSISTANT
    finish_reason: str
    usage: LLMUsage
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Provider-specific metadata
    provider: str | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    """Configuration for LLM client."""

    api_key: str
    base_url: str | None = None
    default_model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0

    # Cost tracking
    track_costs: bool = True
    budget_limit_usd: float | None = None
    alert_threshold: float = 0.8  # Alert at 80% of budget

    # Provider-specific
    provider: Literal["zai", "openrouter", "openai", "anthropic"] = "openrouter"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebSearchResult(BaseModel):
    """Single web search result."""

    url: str
    title: str
    snippet: str
    content: str | None = None
    published_date: datetime | None = None
    domain: str
    relevance_score: float | None = None


class WebSearchResponse(BaseModel):
    """Response from web search."""

    query: str
    results: list[WebSearchResult]
    total_results: int
    search_time_ms: int
    cached: bool = False
    cost_usd: float | None = None
    provider: str = "zai"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CostMetrics(BaseModel):
    """Cost tracking metrics."""

    provider: str
    model: str
    operation: Literal["chat", "search", "embedding"]
    cost_usd: float
    tokens_used: int | None = None
    requests_count: int = 1
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
