# llm-common

Shared LLM utilities and interfaces for Prime Radiant and Affordabot projects.

## Overview

This library provides common abstractions and utilities for LLM-based applications, including:

- **Retrieval**: Interfaces and models for retrieval-augmented generation (RAG)
- **Models**: Shared data models and type definitions
- **Utilities**: Common helper functions and tools

## Installation

```bash
pip install -e .
```

## Usage

### Retrieval

```python
from llm_common.retrieval import RetrievalBackend, RetrievedChunk

# Implement a custom retrieval backend
class MyRetrieval(RetrievalBackend):
    async def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        # Your implementation here
        pass
```

## Development

Run tests:

```bash
pytest tests/
```

## Architecture

This library is designed to be driven by primary repos (Prime Radiant, Affordabot) that track work in Beads. All commits should carry Feature-Keys from controlling epics (bd-svse, affordabot-rdx, etc.).

## Documentation

See `docs/` for detailed documentation on each module and integration guides.
