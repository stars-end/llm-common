# Jules Dispatch Packets (llm-common-cmm)

Scope: **docs + Beads prep only** (no implementation in this PR).

This file is the “handoff sheet” for dispatching self-contained tasks to remote agents (Jules) in `llm-common`.

## 0) Non‑Negotiables (for every agent)

1. Work on a **feature branch** named `feature-<issue-id>` (example: `feature-llm-common-cmm.11`).
2. Open a **PR early** (as soon as tests are wired and running).
3. Merge regularly (merge/rebase `origin/master` daily for multi-day work).
4. **Do not merge unless CI is green**.
5. Every commit must include `Feature-Key: <issue-id or epic-id>`.

## 1) Verification Gates (llm-common)

Use these as “merge blockers” at milestones:
- Unit tests: `poetry run pytest -v`
- Public API sanity: `poetry run python -c "import llm_common; print('ok')"`

If the change is a shared contract, require a downstream spot-check:
- Prime: `make verify-local` (and `make verify-pr PR=<N>` if it touches multiple areas)
- Affordabot: `make verify-local` (and `make verify-pr PR=<N>` for P0/P1)

## 2) What “Jules‑Ready” Means Here

An issue is Jules‑ready if it has:
- explicit dependencies (other Beads IDs),
- stable API + tests expectations,
- and a documented release/rollout note (because apps pin llm-common by tag).

## 3) Workstream Split (do not blur boundaries)

- **llm-common** owns reusable primitives and shared contracts.
- App repos own product wiring and domain tools.

llm-common should not grow UI code or product-specific prompts; keep it boring.

## 4) Jules‑Ready Packets

### Not Jules‑Ready (human decisions)

- Tool selection fallback policy details (must remain bounded; no “select all tools” default)

## 5) Fire-and-forget packet docs (read these first)

- `docs/bd-llm-common-cmm/packets/llm-common-cmm.11.md`
- `docs/bd-llm-common-cmm/packets/llm-common-cmm.12.md`

### Packet: `llm-common-cmm.11` — TOOL_SELECTION_HELPER_AND_MODEL_CONFIG

**Repo:** `llm-common`  
**Branch:** `feature-llm-common-cmm.11`  
**Goal:** Provide a shared `ToolSelector` helper: schema-grounded tool selection using a dedicated small model (default `glm-4.5-air`) with a stable config surface and tests.

**Implementation expectations:**
1. Public API is importable from `llm_common` (document export path).
2. Config is stable and minimal (env vars; no app-specific config formats).
3. Selection output is structured (Pydantic model) and testable (goldens / fixtures).
4. Fallback policy is bounded and safe (no “select all tools” default).

**Verification:**
- `poetry run pytest -v`

**Stop condition:**
- Both apps can consume the helper without copying code.

### Packet: `llm-common-cmm.12` — CONTEXT_POINTER_STORE_AND_RELEVANCE_SELECTION_LIBRARY

**Repo:** `llm-common`  
**Branch:** `feature-llm-common-cmm.12`  
**Goal:** Provide a shared pointer store + relevance selection helper (Dexter-style) so both apps share a storage format and selection logic.

**Implementation expectations:**
1. Pointer schema + hashing strategy documented (args-hash/content-addressable decision).
2. Deterministic pointer summaries exist (for selection + debugging).
3. Relevance selector uses structured output and has a safe fallback policy.

**Verification:**
- `poetry run pytest -v`

**Stop condition:**
- Apps can adopt incrementally (store pointers first, then enable selection).
