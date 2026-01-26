---
name: context-abstractions
description: Core LLM interfaces (BaseProvider, Message, Response).
tags: [context, abstractions, architecture]
---

# LLM Abstractions Context

Core interfaces that all providers implement.

## Key Interfaces

### BaseProvider
Abstract base class for all LLM providers.
- `complete(messages: List[Message]) -> Response`
- `stream(messages: List[Message]) -> Iterator[StreamChunk]`
- `validate_api_key() -> bool`

### Message
Standardized message format.
- `role: Literal["system", "user", "assistant"]`
- `content: str`
- `metadata: Optional[Dict[str, Any]]`

### Response
Standardized response format.
- `content: str`
- `usage: UsageStats`
- `model: str`
- `provider: str`

### StreamChunk
Streaming response chunk.
- `content: str`
- `done: bool`
- `usage: Optional[UsageStats]`

## Type Safety
All interfaces are strictly typed with mypy enforcement in CI.
