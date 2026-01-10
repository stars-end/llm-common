# Dexter RAG V2 (llm-common): Engineer Fix Summary

This doc is a **code review handoff** for Beads epic `llm-common-sw5` (Dexter RAG V2 primitives).
It is intended to help the engineer finish the llm-common implementation so downstream apps (Prime Radiant) can integrate safely.

---

## Spec Requirements (llm-common side)

1. `UnderstandPhase` extracts intent + entities (JSON-mode, deterministic).
2. `ReflectPhase` evaluates completeness with **max_iterations=2** guard (no infinite loops).
3. `IterativeOrchestrator` runs Understand → Plan → Execute → Reflect loop, collecting provenance.
4. Streaming supports GLM-4.7:
   - `tool_stream=True`
   - `reasoning_content`
   - streamed `tool_calls` (incremental arg assembly)
5. Tests exist for phases + orchestrator + streaming parser.
6. Versioning + exports are coherent so downstream can pin a release.

---

## Review Findings: Key Implementation Gaps

### 1) Evidence envelope collection likely broken

The orchestrator currently attempts to merge `result.evidence` from executor results, but executor returns dict-wrapped outputs and/or `SubTaskResult` objects. The evidence envelope can end up empty even when tools produce evidence.

Track as: `llm-common-sw5.3.8`

### 2) ReflectPhase max-iteration forcing is off-by-one

Reflect currently checks `iteration >= max_iterations`, but orchestrator iterates `range(max_iterations)` so this path is unreachable. Needs correction + regression test.

Track as: `llm-common-sw5.3.9` and `llm-common-sw5.2.6`

### 3) Streaming executor is sequential (violates “tools in parallel”)

`AgenticExecutor.run_stream()` streams tool results, but runs tool calls sequentially. The spec calls for tools to execute in parallel while still providing streamed progress events.

Track as: `llm-common-sw5.3.10`

### 4) Streaming API naming mismatch vs spec

Spec expects `ZaiClient.stream_completion(tool_stream=True)`. Implementation currently adds `stream_completion_enhanced()` and leaves `stream_completion()` as string-only.

Track as: `llm-common-sw5.4.7`

### 5) Orchestrator tests are missing

No tests currently reference `IterativeOrchestrator`; add unit + integration tests with mock tools and mock LLM.

Track as: `llm-common-sw5.3.6` / `llm-common-sw5.3.7`

### 6) Versioning mismatch

`pyproject.toml` version and the changelog entries are inconsistent (e.g. changelog contains a `0.5.0` entry while pyproject is `0.7.x`). Decide the canonical version story and fix ordering/tags before downstream pinning.

Track as: `llm-common-sw5.5.2` and `llm-common-sw5.5.6`

---

## Beads Task Map

Epic: `llm-common-sw5`

- UnderstandPhase: `llm-common-sw5.1.1`–`llm-common-sw5.1.6`
- ReflectPhase: `llm-common-sw5.2.1`–`llm-common-sw5.2.6`
- Orchestrator: `llm-common-sw5.3.1`–`llm-common-sw5.3.7`
  - Review blockers: `llm-common-sw5.3.8`–`llm-common-sw5.3.11`
- Streaming: `llm-common-sw5.4.1`–`llm-common-sw5.4.7`
- Exports/Release: `llm-common-sw5.5.1`–`llm-common-sw5.5.6`

Tip: `bd dep tree llm-common-sw5` and `bd ready` for sequencing.

---

## Downstream Integration Note (Prime Radiant)

Prime Radiant’s agent integration currently assumes:
- `ZaiClient()` can be created with no args
- `IterativeOrchestrator(client=..., tools=...)` signature
- orchestrator result has `.citations` and `.cost`

All of those assumptions are unsafe: llm-common should remain authoritative on APIs, and Prime Radiant should adapt to llm-common’s actual signatures and `OrchestratorResult` fields once llm-common is stabilized and released.

