---
repo_memory: true
status: active
owner: llm-common-architecture
last_verified_commit: fb488f6d56538c71161cd120c2004a9c6f272033
last_verified_at: 2026-04-16T16:24:11Z
stale_if_paths:
  - llm_common/**
  - tests/**
  - docs/**
  - .github/workflows/**
---

# Workflows And Patterns

## Shared Library Rule

Prefer narrow, versioned interfaces. Avoid product-specific shortcuts in shared
provider, retrieval, or agent code.

## Provider Pattern

Provider clients should normalize common behavior while preserving enough
provider metadata for debugging and quality evaluation. Do not make a provider
look interchangeable when its failure modes or response semantics differ.

## Agent Pattern

Agent utilities should emit structured artifacts with provenance, not just
natural-language summaries. Product repos can decide how those artifacts become
business-specific analysis.

## Verification Pattern

Run lightweight library checks for small changes. For schema, retrieval, or
provider changes, add targeted contract tests and mention downstream consumer
impact in the PR.

## Generated Files

`AGENTS.md` is generated. Edit `fragments/repo-addendum.md` or the universal
baseline fragment, then run `make regenerate-agents-md`.
