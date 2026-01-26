---
name: context-testing
description: Test utilities and patterns for llm-common.
tags: [context, testing]
---

# Testing Context

## Commands
- `make test` - Run all tests
- `make ci-lite` - Lint + tests
- `poetry run pytest tests/` - Direct pytest invocation

## Test Structure
```
tests/
├── providers/      # Provider-specific tests
├── agents/         # Agent integration tests
└── utils/          # Utility function tests
```

## Mocking Patterns
Use `pytest.mock` for external API calls:

```python
from unittest.mock import Mock, patch

def test_openai_provider():
    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.return_value = {"choices": [{"message": {"content": "test"}}}
        # test code...
```

## CI Requirements
- All tests must pass before merge
- Coverage threshold: 80%
