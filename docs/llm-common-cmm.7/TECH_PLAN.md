# llm-common-cmm.7 — Publish JSON Schema artifacts

## Goal
Make shared contracts consumable by multiple repos by publishing versioned JSON Schema artifacts (and optionally generated types).

## Acceptance Criteria
- Schemas are emitted to a predictable path (and/or attached to releases).
- Downstream repos can pin to a version/tag and validate outputs in CI.

