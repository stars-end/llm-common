---
name: context-providers
description: LLM provider implementations (OpenAI, Anthropic, Zhipu/GLM).
tags: [context, providers, llm]
---

# LLM Providers Context

Provider implementations for different LLM APIs.

## Key Areas
- `llm_common/providers/` - Provider implementations
- BaseProvider interface - All providers inherit from this
- Error handling patterns - Standardized error responses

## Providers
- **OpenAI**: GPT-4, GPT-3.5-turbo
- **Anthropic**: Claude Opus, Sonnet, Haiku
- **Zhipu/GLM**: GLM-4, GLM-4-Air, GLM-4-Flash

## Usage Patterns
```python
from llm_common.providers import OpenAIProvider, AnthropicProvider

provider = OpenAIProvider(api_key="...")
response = provider.complete(messages=[...])
```
