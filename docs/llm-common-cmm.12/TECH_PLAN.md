# Packet: llm-common-cmm.12 — Context pointer store + relevance selection (fire-and-forget)

This packet is designed for a senior engineer with no prior repo context.

## Goal

Provide a shared, reusable mechanism to:
1. Persist large tool outputs as **pointers** (small metadata + stable ID),
2. Select only **relevant** pointers for a given synthesis step (avoid prompt bloat),
3. Load selected contexts in a predictable, testable way.

## Why (context)

`ToolContextManager.load_relevant_contexts(query_id)` currently loads *all* tool outputs for a query.
We need a scalable pattern shared across apps to prevent:
- prompt overflow,
- irrelevant context injection,
- and opaque regressions.

## Scope

### In-scope code
- Add: `llm_common/agents/context_pointers.py`
- Add tests under `tests/`
- Export new public APIs from `llm_common/agents/__init__.py`

### Out of scope
- DB migrations (filesystem backend is sufficient for MVP)

## Canonical API (must implement)

### Pointer schema

Define Pydantic models:

- `ContextPointer`:
  - `pointer_id: str` (stable short hash; 12–16 hex chars)
  - `query_id: str`
  - `task_id: str | None`
  - `tool_name: str`
  - `args: dict`
  - `created_at: str` (ISO8601)
  - `summary: str` (deterministic, no LLM required)
  - `result_path: str` (filesystem path)
  - `source_urls: list[str] = []` (optional metadata)

Deterministic pointer ID:
- `pointer_id = sha256(stable_json({tool_name,args,query_id,task_id}))[:12]`

Deterministic summary:
- mimic Dexter’s “tool description” approach:
  - include tool name + key args (`ticker`, `query`, `period`, `limit`, etc.) when present.

### Pointer store

Implement:

```python
class FileContextPointerStore:
    def __init__(self, base_dir: Path): ...
    async def save(self, *, query_id: str, task_id: str | None, tool_name: str, args: dict, result: Any) -> ContextPointer: ...
    def list(self, *, query_id: str) -> list[ContextPointer]: ...
    def load_result(self, *, pointer: ContextPointer) -> Any: ...
```

Storage format:
- Base dir: `base_dir / query_id /`
- Write:
  - `{pointer_id}.meta.json` (ContextPointer without large result)
  - `{pointer_id}.result.json` (full tool result, JSON-serialized via `default=str`)

Env vars (final names; implement these):
- `LLM_COMMON_POINTER_STORE_DIR` (default: `.llm-common/context`)

### Relevance selector

Implement:

```python
class ContextRelevanceSelector:
    def __init__(self, client: LLMClient, model: str | None = None, max_selected: int = 6): ...
    async def select(
        self,
        *,
        query: str,
        pointers: list[ContextPointer],
    ) -> list[ContextPointer]:
        ...
```

Selection prompt input must include only:
- current user query
- list of candidate pointer summaries + IDs (not full results)

Output must be structured JSON:
```json
{ "pointer_ids": ["a1b2c3d4e5f6", "deadbeefcafe"] }
```

Env vars (final names; implement these):
- `LLM_COMMON_CONTEXT_SELECTION_MODEL` (default: same as `LLM_COMMON_TOOL_SELECTION_MODEL` if set; else client default)
- `LLM_COMMON_CONTEXT_SELECTION_MAX_POINTERS` (default: `6`)
- `LLM_COMMON_CONTEXT_SELECTION_FAIL_CLOSED` (default: `true`)

Failure behavior:
- If selection fails and `FAIL_CLOSED=true`, return `[]` (caller can decide whether to proceed with no context or abort).
- Do not “select all pointers” on failure by default.

### Convenience: render selected contexts for synthesis

Provide:

```python
def format_selected_contexts(
    *,
    pointers: list[ContextPointer],
    store: FileContextPointerStore,
    max_chars: int = 20000,
) -> str:
    ...
```

Rules:
- Load results for selected pointers and concatenate with headings.
- Truncate deterministically to `max_chars`.

## Tests (required)

1. Pointer ID determinism (same inputs → same pointer_id).
2. Summary determinism (key args included).
3. Store roundtrip (save → list → load_result).
4. Selector parsing + max_selected cap (stub LLM response).
5. Fail-closed selection returns `[]` on invalid output.

## Verification (must run)

- `poetry run pytest -v`

## Downstream adoption notes

Prime/Affordabot integration tasks assume:
- `FileContextPointerStore` + `ContextRelevanceSelector` exist in `llm_common.agents` exports.
- pointer store dir can be overridden by env var per deployment.

