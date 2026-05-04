"""Core abstractions and models."""

from llm_common.core.client import LLMClient
from llm_common.core.exceptions import (
    APIKeyError,
    BudgetExceededError,
    CacheError,
    LLMError,
    ModelNotFoundError,
    RateLimitError,
    TimeoutError,
)
from llm_common.core.models import (
    DEFAULT_TEXT_MODEL,
    DEFAULT_TEXT_PROVIDER,
    CostMetrics,
    LLMConfig,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    MessageRole,
    WebSearchResponse,
    WebSearchResult,
)

__all__ = [
    # Client
    "LLMClient",
    # Exceptions
    "LLMError",
    "BudgetExceededError",
    "APIKeyError",
    "ModelNotFoundError",
    "RateLimitError",
    "TimeoutError",
    "CacheError",
    # Models
    "DEFAULT_TEXT_MODEL",
    "DEFAULT_TEXT_PROVIDER",
    "LLMConfig",
    "LLMMessage",
    "LLMResponse",
    "LLMUsage",
    "MessageRole",
    "WebSearchResult",
    "WebSearchResponse",
    "CostMetrics",
]
