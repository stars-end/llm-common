---
repo_memory: true
status: active
owner: llm-common-architecture
last_verified_commit: fb488f6d56538c71161cd120c2004a9c6f272033
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - llm_common/contracts/**
  - llm_common/retrieval/**
  - llm_common/embeddings/**
  - llm_common/agents/provenance*
  - docs/contracts/**
  - docs/LLM_COMMON_PG_BACKEND_MIGRATION.md
---

# Data And Storage

`llm-common` should not own product data. It owns reusable data contracts,
retrieval interfaces, provenance shapes, and provider-neutral storage helpers.

## Storage-Adjacent Surfaces

- Contract schemas define portable artifact shapes.
- Retrieval backends define how downstream apps can query indexed evidence.
- Embedding utilities define derived-vector behavior.
- Provenance utilities define how claims stay tied to source material.
- pgvector support is an adapter layer, not an app-specific corpus owner.

## Invariants

- Keep provenance explicit when transforming model output.
- Do not hide provider-specific fields inside generic contracts without a
  versioning decision.
- Retrieval adapters should not assume a product repo's table names unless the
  adapter is intentionally scoped.
- Schema changes need tests and downstream migration notes.

## Downstream Impact

Before changing retrieval, provenance, or schemas, check known consumers in
Affordabot and Prime Radiant. A library-local test pass is not enough if a
public contract changed.
