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

## 1) MVP Stance (explicit)

**MVP = Structured-only advisor responses.**  
Streaming is post‑MVP unless required.

## 2) Workstream Scope (llm-common specific)

This repo should provide **boring, stable building blocks** that reduce regression risk:
- One documented `ToolResult` envelope and provenance model usable by both app repos.
- (Optional) one documented streaming event schema if/when streaming is enabled.
- A tagged release that both repos pin to (no branch pins).

## 3) Beads Issues (Jules-dispatchable)

Epic: `llm-common-cmm`
- `llm-common-cmm.1` Docs: llm-common workstream spec
- `llm-common-cmm.2` Contract: ToolResult + provenance
- `llm-common-cmm.3` Contract: StreamEvent schema (optional / post‑MVP)
- `llm-common-cmm.4` Release + pinning plan (apps + scripts)

## 4) Dependency Notes (cross-repo)

Hard dependency:
- `llm-common-cmm.4` should land **before** implementation-heavy tasks in Prime and Affordabot (`bd-yn9g.2`, `affordabot-ahpb.2`).

## 5) Open Questions (shared)

See canonical spec: `prime-radiant-ai/docs/bd-yn9g/SPEC.md`.

