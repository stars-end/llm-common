# Big‑Bang Frontend Stack Unification (Prime Stack)

**Prime Radiant Epic:** `bd-yn9g`  
**Affordabot Epic:** `affordabot-ahpb`  
**llm-common Epic:** `llm-common-cmm`  

## 0) Purpose

This is the **llm-common mirror** of the canonical big‑bang frontend unification spec.

> **Canonical copy**: `prime-radiant-ai/docs/bd-yn9g/SPEC.md`.  
> This file exists so agents working in `llm-common` have full context while implementing contract and release work.

The `llm-common` workstream’s responsibility is to make cross-repo work safe by stabilizing:
- versioning and pins
- shared contracts (ToolResult/provenance, optional streaming events)

## 0.1 Jules Dispatch (llm-common-specific)

Jules-ready packets live in `docs/bd-llm-common-cmm/JULES_DISPATCH.md`. Use them to dispatch self-contained library work with:
- explicit verification gates (`poetry run pytest -v`),
- stable public API exports,
- and release/pinning notes so downstream repos don’t drift.

## 1) MVP Stance (explicit)

**MVP = Structured-only advisor responses.**  
Streaming is post‑MVP unless required.

## 2) Workstream Scope (llm-common specific)

This repo should provide **boring, stable building blocks** that reduce regression risk:
- One documented `ToolResult` envelope and provenance model usable by both app repos.
- (Optional) one documented streaming event schema if/when streaming is enabled.
- A tagged release that both repos pin to (no branch pins).

Dexter audit reference (local snapshot):
- `docs/bd-llm-common-cmm/DEXTER_AUDIT.md`

## 3) Beads Issues (Jules-dispatchable)

Epic: `llm-common-cmm`
- `llm-common-cmm.1` Docs: llm-common workstream spec
- `llm-common-cmm.2` Contract: ToolResult + provenance
- `llm-common-cmm.3` Contract: StreamEvent schema (optional / post‑MVP)
- `llm-common-cmm.4` Release + pinning plan (apps + scripts)
- `llm-common-cmm.5` Docs: Dexter audit refresh + rewrite spec updates (this PR)
- `llm-common-cmm.6` Chore: version/tag alignment
- `llm-common-cmm.7` Task: publish JSON Schema artifacts in releases
- `llm-common-cmm.8` Task: MessageHistory helper (Dexter-style)
- `llm-common-cmm.9` Docs: bundle Dexter ports (glm-4.5-air tool selection, context pointers, message history)
- `llm-common-cmm.10` Feature: Dexter ports bundle (llm-common primitives)
- `llm-common-cmm.11` Task: tool selection helper + model config (glm-4.5-air default)
- `llm-common-cmm.12` Task: context pointer store + relevance selection library

## 4) Dependency Notes (cross-repo)

Hard dependency:
- `llm-common-cmm.4` should land **before** implementation-heavy tasks in Prime and Affordabot (`bd-yn9g.2`, `affordabot-ahpb.2`).

## 5) Open Questions (shared)

See canonical spec: `prime-radiant-ai/docs/bd-yn9g/SPEC.md`.
