# llm-common: Dexter RAG V2 Implementation Handoff

Epic: `llm-common-sw5`
Version: `0.8.0`

## Overview
Successfully implemented core Dexter RAG V2 agent primitives, consolidated streaming APIs, and improved orchestrator robustness.

## Key Changes

### 1. ZaiClient Consolidation
- Merged `stream_completion_enhanced` back into `stream_completion`.
- Added support for GLM-4.7 features (parallel tool calls, thinking blocks, usage metrics) via the OpenAI-compatible interface.
- Maintained backward compatibility for legacy callers.

### 2. IterativeOrchestrator Improvements
- **Evidence Collection**: Fixed nested extraction from `SubTaskResult` -> `ToolResult` -> `evidence`.
- **Reflection Logic**: Corrected the off-by-one error in `ReflectPhase` where the last iteration was skipping final evaluation. It now correctly forces completion at `max_iterations - 1`.
- **Streaming Parallelism**: Updated `AgenticExecutor.run_stream` to execute tool calls in parallel using `asyncio.as_completed`.
- **Event Consistency**: Added missing `plan` events and ensured `evidence` and `answer` events are always yielded at the end of the stream.

### 3. Testing
- Added `tests/agents/test_orchestrator.py` covering:
    - End-to-end sync execution.
    - Full event stream verification.
    - Max iteration enforcement (2 iters).
    - Evidence envelope merging.

### 4. Versioning & Changelog
- Bumped version to `0.8.0` in `pyproject.toml`.
- Updated `CHANGELOG.md` with detailed entries for RAG V2.

## Maintenance Notes
- **Streaming**: The orchestrator now expects a streaming-capable LLM client. `ZaiClient` is the recommended provider.
- **Tools**: All tools should return `ToolResult` with populated `evidence` (list of `EvidenceEnvelope`) to ensure citations work in the frontend.

## Verification
Run `poetry run pytest tests/agents/test_orchestrator.py` to verify core logic.
