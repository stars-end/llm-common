# Packet: llm-common-cmm.11 — ToolSelector helper + model config (fire-and-forget)

This packet is designed for a senior engineer with no prior repo context. It is intentionally explicit.

## Goal

Create a shared **ToolSelector** implementation in `llm-common` so both product repos can:
- select tool calls using a **dedicated small model role** (default `glm-4.5-air`),
- enforce strict caps (≤ 5 tool calls),
- and follow a **bounded, safety-first fallback policy** (no “select all tools” default).

## Why (context)

Today, tool selection is effectively embedded inside the executor (`AgenticExecutor._resolve_tools`) and uses the general LLM client.
We want one reusable, testable component with explicit configuration and predictable failure behavior.

## Scope

### In-scope code
- Add: `llm_common/agents/tool_selector.py`
- Optional refactor: `llm_common/agents/executor.py` to call the new ToolSelector (recommended so all downstream integrations converge)
- Update: `llm_common/agents/__init__.py` to export ToolSelector + config model(s)
- Add tests under `tests/` (see below)

### Out of scope
- UI work
- Any changes to tool implementations themselves

## Canonical API (must implement)

### Config

Define a config model (Pydantic) and loader:

- `ToolSelectionConfig`:
  - `model: str = "glm-4.5-air"`
  - `fallback_model: str | None = None`
  - `max_calls: int = 5`
  - `timeout_s: int = 30`
  - `temperature: float = 0.0`
  - `fail_closed: bool = True`

Env vars (final names; implement these):
- `LLM_COMMON_TOOL_SELECTION_MODEL` (default: `glm-4.5-air`)
- `LLM_COMMON_TOOL_SELECTION_FALLBACK_MODEL` (default: unset)
- `LLM_COMMON_TOOL_SELECTION_MAX_CALLS` (default: `5`)
- `LLM_COMMON_TOOL_SELECTION_TIMEOUT_S` (default: `30`)
- `LLM_COMMON_TOOL_SELECTION_FAIL_CLOSED` (default: `true`)

### Selector

Implement:

```python
class ToolSelector:
    def __init__(self, client: LLMClient, config: ToolSelectionConfig | None = None): ...

    async def select_tool_calls(
        self,
        *,
        task: PlannedTask,
        tool_registry: ToolRegistry,
        query: str | None = None,
        context: dict | None = None,
    ) -> list[ToolCall]:
        ...
```

Rules:
- Must use `tool_registry.get_tools_schema()` as the source of truth.
- Must return a list of `ToolCall` (from `llm_common.agents.schemas`).
- Must enforce `max_calls`:
  - If the model returns more, truncate deterministically (keep first N).
- Must not crash on invalid JSON; it must follow fallback policy.

### Prompt contract (tool selection)

System prompt must:
- embed the tool schema (from registry)
- instruct the model to return **JSON matching** a schema like:

```json
{ "calls": [ { "tool": "tool_name", "args": { "k": "v" } } ] }
```

Use `response_format={"type":"json_object"}`.

## Fallback policy (must implement)

1. Try selection with `config.model`.
2. If selection fails (network error OR parse/validation error):
   - If `fallback_model` is set: retry once with `fallback_model`.
3. If still failing:
   - If `fail_closed=True`: return `[]` and allow caller to surface a structured error.
   - If `fail_closed=False`: return `[]` (do **not** expand scope by calling all tools).

Explicitly forbidden behavior:
- Do not “select all tools” as a fallback default.

## Integration guidance (recommended)

Update `llm_common/agents/executor.py`:
- Replace the body of `_resolve_tools()` with a call to `ToolSelector.select_tool_calls(...)`.
- This ensures all downstream callers (Prime/Affordabot) converge on a single implementation.

## Tests (required)

Add unit tests that run without network:

1. **Max calls cap**:
   - stub `LLMClient.chat_completion` to return 7 tool calls → assert only 5 returned.
2. **Fallback model path**:
   - primary model returns invalid JSON → fallback model returns valid JSON → assert calls returned and fallback was attempted.
3. **Fail closed**:
   - both primary and fallback fail → assert `[]` returned.

If the repo uses pytest fixtures for LLM stubs, follow existing patterns in `tests/`.

## Verification (must run)

- `poetry run pytest -v`

## Downstream contract notes

Downstream integrations will assume:
- `ToolSelector` is importable from `llm_common.agents`
- env var names above work consistently in both app repos

