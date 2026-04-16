---
repo_memory: true
status: active
owner: llm-common-architecture
last_verified_commit: fb488f6d56538c71161cd120c2004a9c6f272033
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - llm_common/**
  - docs/contracts/**
  - tests/**
---

# Brownfield Map

`llm-common` is the shared LLM/provider/retrieval/agent library used by product
repos. Changes here can alter behavior in multiple apps, so keep contracts
explicit.

## Core Areas

- `llm_common/core/`: client abstractions, model definitions, and shared
  exceptions.
- `llm_common/providers/`: provider clients for GLM/Z.ai/OpenRouter and related
  adapter behavior.
- `llm_common/agents/`: agentic executor, planner, research agent, provenance,
  and UI smoke agent code.
- `llm_common/contracts/`: schema registry and JSON schemas for cross-layer
  artifacts.
- `llm_common/retrieval/`: retrieval abstractions and backends, including the
  pgvector backend.
- `llm_common/embeddings/`: embedding adapters and shared embedding utilities.
- `llm_common/web_search/`: shared web-search client abstractions.
- `llm_common/verification/` and `llm_common/qa/`: validation and QA helpers.

## Product Boundary

This repo should expose reusable primitives and contracts. Product-specific
business logic belongs in the product repo unless it is deliberately promoted
into a shared contract.

## Before Changing This Area

Inspect:
- `docs/contracts/PROVENANCE_CONTRACT.md`
- `docs/contracts/stream_event.md`
- `docs/LLM_COMMON_PG_BACKEND_MIGRATION.md`
- `docs/UI_SMOKE_AGENT.md`
- `llm_common/contracts/schemas/`
