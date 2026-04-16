---
repo_memory: true
status: active
owner: llm-common-architecture
last_verified_commit: fb488f6d56538c71161cd120c2004a9c6f272033
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - llm_common/**
  - docs/**
  - contracts/**
  - tests/**
---

# Architecture Docs Index

These are the repo-owned brownfield maps for `llm-common`.

- `BROWNFIELD_MAP.md`: provider, agent, retrieval, contract, and verification
  code map.
- `DATA_AND_STORAGE.md`: provenance, schemas, retrieval, embeddings, and
  pgvector ownership.
- `WORKFLOWS_AND_PATTERNS.md`: provider/client conventions and verification
  patterns.

This repository is shared infrastructure. Preserve provider contracts and
provenance semantics before optimizing call sites in downstream apps.
