# llm-common

Shared LLM framework for affordabot and prime-radiant-ai.

## Features

- **Multi-Provider Support**: z.ai, OpenRouter, and any OpenAI-compatible endpoint
- **Web Search**: z.ai web search with intelligent caching
- **Retrieval**: Interfaces and models for retrieval-augmented generation (RAG)
- **Structured Outputs**: Built-in support for instructor and Pydantic models
- **Cost Tracking**: Per-request cost monitoring and budget alerts
- **Retry Logic**: Exponential backoff with jitter for reliability
- **Verification**: UISmoke Universal Runner for cross-repo automated story testing
- **Type Safety**: Full mypy strict mode compliance

## Installation

```bash
# Via Poetry
poetry add llm-common

# Via pip
pip install llm-common
```

## Versioning and Pinning

This project follows [Semantic Versioning](https://semver.org/). We recommend pinning your dependency to a specific Git tag to ensure build stability.

### Poetry

In your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
llm-common = {git = "ssh://git@github.com/stars-end/llm-common.git", tag = "v0.7.4"}
```

### Pip

In your `requirements.txt`:

```
git+ssh://git@github.com/stars-end/llm-common.git@v0.7.4#egg=llm-common
```

Replace `v0.7.4` with the desired version tag.

## Quick Start

### Basic LLM Usage

```python
from llm_common.providers import ZaiClient, OpenRouterClient
from llm_common.core import LLMMessage

# z.ai client
zai = ZaiClient(api_key="your-zai-key")
response = await zai.chat_completion(
    messages=[LLMMessage(role="user", content="Hello!")],
    model="glm-4.7"
)

# OpenRouter client (access to 400+ models)
router = OpenRouterClient(api_key="your-openrouter-key")
response = await router.chat_completion(
    messages=[LLMMessage(role="user", content="Hello!")],
    model="anthropic/claude-3.5-sonnet"
)
```

### Web Search with Caching

```python
from llm_common.web_search import WebSearchClient

search = WebSearchClient(
    zai_api_key="your-zai-key",
    cache_ttl=86400  # 24 hours
)

results = await search.search(
    query="California AB 1234 housing regulations",
    count=10,
    domains=["*.gov"],
    recency="1y"
)
```

### Retrieval (RAG)

```python
from llm_common.retrieval import RetrievalBackend, RetrievedChunk

# Implement a custom retrieval backend
class MyRetrieval(RetrievalBackend):
    async def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        # Your implementation here
        pass

# Use the backend
async with MyRetrieval() as backend:
    results = await backend.retrieve("What is RAG?", top_k=3)
    for chunk in results:
        print(f"{chunk.source}: {chunk.content}")
```

### Structured Outputs with instructor

```python
from pydantic import BaseModel
from llm_common.integrations import get_instructor_client

class Analysis(BaseModel):
    summary: str
    sentiment: str
    key_points: list[str]

client = get_instructor_client(
    provider="openrouter",
    api_key="your-key"
)

analysis = await client.chat.completions.create(
    model="anthropic/claude-3.5-sonnet",
    response_model=Analysis,
    messages=[{"role": "user", "content": "Analyze this bill..."}]
)
```

### UISmoke (Automated Verification)

UISmoke is a shared QA-engineer harness for executing autonomous UI stories using vision models.

```bash
# Run stories against a target URL
uismoke run --stories ./docs/TESTING/STORIES --base-url https://dev.example.ai --output ./artifacts/verification
```

Features:
### QA mode vs Gate mode
- `--mode qa`: Exit 0 if the harness completed and produced artifacts, even if product failures occurred. Use this for discovery/nightly runs where you want to triage all results. Exit 1 only on harness crash or misconfiguration.
- `--mode gate`: Exit 1 if any story does not pass. Use this for CI/PR gates where zero regressions are required.

### Triage Behavior (Hardened)
The triage tool (`uismoke triage`) classifies failures to minimize noise:
- **Bug**: Created only for reproducible failures where either the failure occurred in a deterministic step (`wait_for_selector`, `click`, etc.) or it's a specific assertion-type error (`verification_error`, `assert_text`, `403_forbidden`).
- **Triage**: Created for all other failures (timeouts, unknown flaky issues, harness errors).

## Architecture

```
llm_common/
├── core/           # Abstract interfaces and data models
├── providers/      # Provider implementations (Zai, OpenRouter, Unified)
├── retrieval/      # RAG interfaces (RetrievalBackend, RetrievedChunk)
├── web_search/     # Web search with caching
├── utils/          # Retry logic, cost tracking, logging
└── integrations/   # instructor, Pydantic helpers
```

This library is designed to be driven by primary repos (Prime Radiant, Affordabot) that track work in Beads. All commits should carry Feature-Keys from controlling epics (bd-svse, affordabot-rdx, etc.).

## Cost Optimization

The framework includes aggressive caching to reduce costs:

- **Web Search**: 80% cache hit rate target (reduces $450/month → $90/month)
- **Model Selection**: Free tier → Budget → Premium model degradation
- **Cost Tracking**: Per-request monitoring with budget alerts

## Development

```bash
# Setup
poetry install

# Run tests
poetry run pytest

# Type checking
poetry run mypy llm_common

# Formatting
poetry run black llm_common
poetry run ruff llm_common
```

## Documentation

See `docs/` for detailed documentation:

- [Integration and Retrieval Guide](docs/LLM_COMMON_WORKSTREAMS/INTEGRATION_AND_RETRIEVAL.md)
- [Implementation Status](IMPLEMENTATION_STATUS.md)

## License

MIT
