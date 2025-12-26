# Dexter Audit (Local `~/dexter`, 2025-12)

**Audited repo:** `~/dexter`  
**Audited commit:** `1ba02db47d5d8647de6f3f2eb17eae0a93d07cef` (“Add insider trades tool”)  
**Goal of this audit:** Identify which Dexter patterns should become shared, stable building blocks in `llm-common` to reduce cross-repo regressions during the big-bang rewrite.

## 1) What Dexter Implements (Condensed)

Dexter is a TS agent that:
- extracts intent/entities (structured output via zod),
- plans a small task DAG (taskType + dependsOn),
- executes tasks with dependency-aware parallelization,
- selects tools for “use_tools” tasks using a small model (`gpt-5-mini`) with bound tools,
- captures tool outputs in a disk-backed context store,
- carries minimal provenance (`sourceUrls`) from tools → contexts → answer prompt “Sources”.

## 2) The Part That Matters for llm-common: End-to-End Provenance Plumbing

Dexter’s reusable insight is not its finance tools or UI, but:
- the invariant “tool results can carry provenance”
- provenance survives storage and shows up at synthesis time

`llm-common` already has a stronger version of this idea:
- `Evidence` / `EvidenceEnvelope` + `validate_citations` in `llm_common/agents/provenance.py`

The big-bang rewrite should converge both products to the llm-common model and avoid URL-only “sources”.

## 3) Additional Dexter Pattern Worth Productizing: Cheap Conversation Memory

Dexter’s `MessageHistory` design is a good shared primitive:
- per-turn short summary
- structured selection of relevant prior turns
- injection into planning/understanding only

This is a strong “solo dev” pattern because it avoids embeddings and keeps behavior explicit.

## 4) Dexter Gaps to Learn From (Don’t Copy Blindly)

1. Context selection exists (`selectRelevantContexts`) but is unused in this snapshot.
2. Tool-output summarization prompts exist but are unused.
3. Sources are prompt-only and URL-only; no programmatic evidence binding.
4. The final answer contract is coupled to streaming UI (callback stream).

## 5) llm-common Workstream Implications (What to Build/Standardize)

1. **Evidence contract**: make `EvidenceEnvelope` the canonical cross-repo “tool result provenance” container.
2. **Citation validation**: standardize a validator that ensures citations reference evidence IDs.
3. **Optional StreamEvent**: keep streaming as optional (post-MVP), but if enabled, standardize one schema.
4. **Conversation memory helper**: implement a small library for summary + relevance selection (Dexter-style).
5. **Tool selection helper**: standardize “small-model tool selection” (default: `glm-4.5-air`) so both apps converge on the same model role + schema-grounded selection.

## 6) Tracking

This audit is intended to directly influence:
- `docs/bd-llm-common-cmm/SPEC.md`
- the canonical big-bang rewrite spec: `prime-radiant-ai/docs/bd-yn9g/SPEC.md`
