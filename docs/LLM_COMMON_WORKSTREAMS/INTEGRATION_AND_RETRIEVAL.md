# Integration and Retrieval

This document describes the retrieval interface design for llm-common, which provides shared abstractions for retrieval-augmented generation (RAG) across Prime Radiant and Affordabot projects.

## Overview

The retrieval module provides a unified interface for accessing knowledge bases, vector stores, and other information retrieval systems. This enables consistent RAG implementations across different projects and backends.

## Core Components

### 1. RetrievedChunk (`llm_common/retrieval/models.py`)

The `RetrievedChunk` model represents a single piece of retrieved content with its associated metadata.

**Fields:**
- `content` (str): The actual text content
- `score` (float): Relevance score between 0.0 and 1.0
- `source` (str): Source identifier (file path, URL, document ID)
- `metadata` (dict): Additional contextual information
- `chunk_id` (Optional[str]): Unique identifier for the chunk
- `embedding` (Optional[list[float]]): Embedding vector used for retrieval

**Example:**
```python
from llm_common.retrieval.models import RetrievedChunk

chunk = RetrievedChunk(
    content="The capital of France is Paris.",
    score=0.95,
    source="geography/europe.txt",
    metadata={"section": "capitals", "page": 42},
    chunk_id="geo_001"
)
```

### 2. RetrievalBackend (`llm_common/retrieval/base.py`)

The `RetrievalBackend` abstract base class defines the interface that all retrieval implementations must follow.

**Key Methods:**
- `retrieve(query, top_k, min_score, filters)`: Main retrieval method
- `health_check()`: Check backend availability
- `get_by_id(chunk_id)`: Retrieve specific chunk by ID
- `close()`: Clean up resources

**Example Implementation:**
```python
from llm_common.retrieval import RetrievalBackend, RetrievedChunk

class VectorStoreBackend(RetrievalBackend):
    def __init__(self, connection_string: str):
        self.connection = connect(connection_string)

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float | None = None,
        filters: dict[str, any] | None = None,
    ) -> list[RetrievedChunk]:
        # Embed query
        query_embedding = await self.embed(query)

        # Search vector store
        results = await self.connection.search(
            query_embedding,
            limit=top_k,
            filters=filters
        )

        # Convert to RetrievedChunk objects
        chunks = [
            RetrievedChunk(
                content=r.text,
                score=r.similarity,
                source=r.document_id,
                metadata=r.metadata
            )
            for r in results
        ]

        # Apply min_score filter
        if min_score is not None:
            chunks = [c for c in chunks if c.score >= min_score]

        return chunks

    async def close(self) -> None:
        await self.connection.close()
```

## Integration Patterns

### 1. Context Manager Pattern

Use async context managers for automatic resource cleanup:

```python
async with VectorStoreBackend(connection_string) as backend:
    results = await backend.retrieve("What is RAG?", top_k=3)
    for chunk in results:
        print(f"{chunk.source}: {chunk.content}")
# Backend automatically closed
```

### 2. Factory Pattern

Create backend instances based on configuration:

```python
def create_retrieval_backend(config: dict) -> RetrievalBackend:
    backend_type = config.get("type")

    if backend_type == "vector_store":
        return VectorStoreBackend(config["connection_string"])
    elif backend_type == "elasticsearch":
        return ElasticsearchBackend(config["es_config"])
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")
```

### 3. Caching Layer

Add caching to reduce redundant queries:

```python
class CachedRetrievalBackend(RetrievalBackend):
    def __init__(self, backend: RetrievalBackend):
        self.backend = backend
        self.cache: dict[str, list[RetrievedChunk]] = {}

    async def retrieve(self, query: str, **kwargs) -> list[RetrievedChunk]:
        cache_key = f"{query}:{kwargs}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        results = await self.backend.retrieve(query, **kwargs)
        self.cache[cache_key] = results
        return results
```

## Testing

### Unit Tests

Test models and abstract interfaces:

```python
# tests/retrieval/test_models.py
def test_retrieved_chunk_validation():
    chunk = RetrievedChunk(
        content="test",
        score=0.5,
        source="test.txt"
    )
    assert chunk.content == "test"

# tests/retrieval/test_base.py
@pytest.mark.asyncio
async def test_retrieve():
    backend = MockBackend()
    results = await backend.retrieve("query")
    assert len(results) > 0
```

### Integration Tests

Test with real backends:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_vector_store_integration():
    backend = VectorStoreBackend(TEST_CONNECTION_STRING)

    try:
        # Index test data
        await backend.index([
            {"content": "Paris is the capital of France.", "id": "1"},
            {"content": "Berlin is the capital of Germany.", "id": "2"},
        ])

        # Query
        results = await backend.retrieve("capital of France")

        # Verify
        assert len(results) > 0
        assert "Paris" in results[0].content
        assert results[0].score > 0.8
    finally:
        await backend.close()
```

## Feature Keys and Tracking

All work on llm-common should be tracked using Feature-Keys from the controlling epics:

- **bd-svse**: Prime Radiant / Smart Vector Search Engine work
- **affordabot-rdx**: Affordabot Redux work

**Commit Message Format:**
```
[bd-svse] Add RetrievalBackend interface

Implements abstract base class for retrieval backends
with retrieve(), health_check(), and resource management.
```

## Future Enhancements

Planned additions to the retrieval module:

1. **Hybrid Search**: Combine vector search with traditional keyword search
2. **Reranking**: Post-retrieval reranking using cross-encoders
3. **Streaming**: Support for streaming large result sets
4. **Batch Operations**: Efficient batch retrieval
5. **Metrics**: Built-in performance and relevance metrics
6. **Multi-Backend**: Federated search across multiple backends

## References

- [Prime Radiant Architecture](../../prime-radiant-ai/docs/ARCHITECTURE.md)
- [Affordabot Documentation](../../affordabot/docs/)
- [MULTI_REPO_AGENTS](../MULTI_REPO_AGENTS.md)
