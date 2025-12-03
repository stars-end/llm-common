# Post-Merge Action Plan - Retrieval Module

**Current Status:** PR #2 (feature-bd-svse-retrieval) under review  
**Next Actions:** Execute after merge approval

---

## Step 1: Tag Version 0.2.0 (Immediately After Merge)

### Commands

```bash
cd ~/llm-common
git checkout master
git pull origin master  # Ensure we have the merged PR

# Tag the release
git tag -a v0.2.0 -m "Release v0.2.0: Add retrieval module (RAG interfaces)

This release adds the retrieval module to llm-common, providing
shared abstractions for retrieval-augmented generation (RAG).

New features:
- RetrievedChunk: Pydantic model for retrieved content
- RetrievalBackend: Abstract base class for retrieval implementations
- Comprehensive test suite (21 new tests)
- Integration documentation

Breaking changes: None
New dependencies: typing-extensions

Feature-Key: bd-svse, affordabot-rdx
"

# Push tag to remote
git push origin v0.2.0

# Verify tag
git tag -l "v0.2.0" -n9
```

### Update pyproject.toml

```bash
# Update version in pyproject.toml
sed -i 's/version = "0.1.0"/version = "0.2.0"/' pyproject.toml

# Commit version bump
git add pyproject.toml
git commit -m "chore: Bump version to 0.2.0

Feature-Key: bd-svse"
git push origin master
```

---

## Step 2: Plan First Concrete Backend (ChromaDB)

### Why ChromaDB First?

- **Simple**: Local, embedded vector database
- **No external deps**: Runs in-process
- **Good for dev/testing**: Easy to set up and tear down
- **Production-capable**: Can scale for small-medium datasets

### Branch Strategy

```bash
cd ~/llm-common
git checkout master
git pull origin master
git checkout -b feature-bd-svse-chroma-backend
```

### Implementation Scope

**Files to create:**

```
llm_common/retrieval/backends/
├── __init__.py                 # Export ChromaBackend
├── chroma_backend.py          # ChromaDB implementation (~150 lines)
└── README.md                   # Backend-specific docs

tests/retrieval/backends/
├── __init__.py
└── test_chroma_backend.py     # Integration tests (~100 lines)

examples/
└── chroma_rag_example.py      # End-to-end RAG demo (~150 lines)
```

**Dependencies to add:**

```toml
[tool.poetry.dependencies]
chromadb = { version = "^0.4.0", optional = true }

[tool.poetry.extras]
chroma = ["chromadb"]
```

### ChromaBackend API

```python
from llm_common.retrieval import RetrievalBackend, RetrievedChunk
import chromadb

class ChromaBackend(RetrievalBackend):
    """ChromaDB-based retrieval backend.
    
    Args:
        collection_name: Name of the ChromaDB collection
        persist_directory: Optional directory to persist data
        embedding_function: Optional custom embedding function
    """
    
    def __init__(
        self,
        collection_name: str = "documents",
        persist_directory: str | None = None,
        embedding_function = None,
    ):
        if persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function
        )
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float | None = None,
        filters: dict[str, any] | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve from ChromaDB."""
        # Query collection
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filters  # ChromaDB metadata filters
        )
        
        # Convert to RetrievedChunk
        chunks = []
        for i, doc_id in enumerate(results['ids'][0]):
            score = 1.0 - results['distances'][0][i]  # Convert distance to similarity
            
            if min_score and score < min_score:
                continue
            
            chunks.append(RetrievedChunk(
                content=results['documents'][0][i],
                score=score,
                source=results['metadatas'][0][i].get('source', 'unknown'),
                metadata=results['metadatas'][0][i],
                chunk_id=doc_id
            ))
        
        return chunks
    
    async def close(self):
        """Cleanup (ChromaDB handles this automatically)."""
        pass
    
    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ):
        """Add documents to the collection."""
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
```

### Test Plan

```python
# tests/retrieval/backends/test_chroma_backend.py

@pytest.mark.integration
async def test_chroma_basic_retrieval():
    """Test basic retrieval with ChromaDB."""
    backend = ChromaBackend(collection_name="test_collection")
    
    # Add test documents
    backend.add_documents(
        documents=[
            "The capital of France is Paris.",
            "The capital of Germany is Berlin.",
            "The capital of Italy is Rome.",
        ],
        metadatas=[
            {"country": "France", "source": "geography.txt"},
            {"country": "Germany", "source": "geography.txt"},
            {"country": "Italy", "source": "geography.txt"},
        ],
        ids=["doc1", "doc2", "doc3"]
    )
    
    # Query
    results = await backend.retrieve("France capital", top_k=2)
    
    # Assertions
    assert len(results) > 0
    assert "Paris" in results[0].content
    assert results[0].score > 0.5
```

### Example Usage

```python
# examples/chroma_rag_example.py

from llm_common.retrieval.backends import ChromaBackend
from llm_common import ZaiClient, LLMMessage

async def main():
    # 1. Setup retrieval backend
    backend = ChromaBackend(persist_directory="./chroma_db")
    
    # 2. Index documents (one-time)
    backend.add_documents(
        documents=[
            "California AB 1234 provides housing tax credits...",
            "California SB 567 regulates rental agreements...",
            # ... more documents
        ],
        metadatas=[
            {"bill": "AB 1234", "state": "CA", "year": 2024},
            {"bill": "SB 567", "state": "CA", "year": 2024},
        ]
    )
    
    # 3. Retrieve relevant context
    query = "What are the housing tax credit eligibility requirements?"
    chunks = await backend.retrieve(query, top_k=3)
    
    # 4. Format context for LLM
    context = "\n\n".join([f"[{c.source}] {c.content}" for c in chunks])
    
    # 5. Send to LLM
    llm = ZaiClient(api_key="...")
    response = await llm.chat_completion([
        LLMMessage(role="system", content=f"Context:\n{context}"),
        LLMMessage(role="user", content=query)
    ])
    
    print(response.content)
```

### PR Checklist

- [ ] `ChromaBackend` implementation
- [ ] Unit tests (mocked ChromaDB)
- [ ] Integration tests (real ChromaDB)
- [ ] Example usage (`chroma_rag_example.py`)
- [ ] Documentation updates
- [ ] README for backends directory
- [ ] Optional dependency properly configured
- [ ] CI passes

### Estimated Effort

- **Implementation**: 2-3 hours
- **Tests**: 1-2 hours
- **Documentation**: 30 minutes
- **Total**: ~4-5 hours

---

## Step 3: Downstream Coordination

### 3A: Affordabot Integration

**Goal:** Verify affordabot builds against v0.2.0 without using retrieval yet.

```bash
cd ~/affordabot

# Add llm-common as git submodule (or update existing)
git submodule add git@github.com:stars-end/llm-common.git packages/llm-common
cd packages/llm-common
git checkout v0.2.0
cd ../..

# Update pyproject.toml to reference local package
# [tool.poetry.dependencies]
# llm-common = { path = "./packages/llm-common", develop = true }

# Test build
poetry install
poetry run pytest  # Should pass without using retrieval

# Commit submodule
git add packages/llm-common .gitmodules pyproject.toml
git commit -m "[affordabot-rdx] Add llm-common v0.2.0 submodule

Feature-Key: affordabot-rdx"
git push
```

**Verification Steps:**

1. ✅ Affordabot installs successfully
2. ✅ Existing tests pass
3. ✅ Can import from llm_common (even if not used yet)
4. ✅ No version conflicts

**Future Work:**
- Use `WebSearchClient` for research step
- Implement housing policy Q&A with retrieval backend

---

### 3B: Prime Radiant Integration

**Goal:** Same as affordabot - verify build compatibility.

```bash
cd ~/prime-radiant-ai

# Add/update submodule
git submodule add git@github.com:stars-end/llm-common.git backend/llm-common
cd backend/llm-common
git checkout v0.2.0
cd ../..

# Update pyproject.toml
# llm-common = { path = "./backend/llm-common", develop = true }

# Test build
cd backend
poetry install
poetry run pytest

# Commit
git add backend/llm-common backend/pyproject.toml
git commit -m "[bd-svse] Add llm-common v0.2.0 submodule

Feature-Key: bd-svse"
git push
```

**Future Work:**
- Vector store for user conversation history
- Financial document retrieval
- Context enhancement for agent responses

---

## Timeline

| Step | When | Owner | Status |
|------|------|-------|--------|
| PR #2 review | Now | Reviewer | 🟡 In Progress |
| PR #2 merge | After approval | Maintainer | ⏳ Waiting |
| Tag v0.2.0 | Immediately after merge | You | 📋 Ready |
| ChromaDB backend | 1-2 days post-merge | You | 📋 Planned |
| Affordabot integration | After v0.2.0 tag | You | 📋 Planned |
| Prime Radiant integration | After v0.2.0 tag | You | 📋 Planned |

---

## Notes

- **Breaking Changes:** None in v0.2.0 (purely additive)
- **Backward Compatibility:** All existing imports continue to work
- **Optional Dependencies:** ChromaDB will be optional (`pip install llm-common[chroma]`)
- **Versioning:** Following semantic versioning (0.2.0 = minor feature addition)
- **Feature Keys:** 
  - Retrieval module: `bd-svse`, `affordabot-rdx`
  - ChromaDB backend: `bd-svse`
  - Downstream integrations: respective project keys

---

**Generated:** 2025-12-03  
**Status:** Ready to execute post-merge
