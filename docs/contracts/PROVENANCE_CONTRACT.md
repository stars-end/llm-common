# Provenance Contract (v1)

Canonical JSON Schema artifacts live in:
- `llm_common/contracts/schemas/evidence.v1.json`
- `llm_common/contracts/schemas/evidence_envelope.v1.json`
- `llm_common/contracts/schemas/tool_result.v1.json`

## Goals
- Standardize how tools attach provenance so downstream synthesis + UIs can render sources consistently.
- Keep evolution safe for a solo developer: **additive-only within a major** (new optional fields only).

## Models

### `Evidence` (`evidence.v1`)
Represents a single piece of provenance (URL or internal).
Common fields:
- `id`: unique identifier (string)
- `kind`: `"url" | "internal" | "legislation" | "derived"`
- `label`: human-readable label
- `url`: optional URL (empty string allowed)
- `excerpt`: optional short excerpt
- `metadata`: free-form object for tool-specific details
- `derived_from`: evidence IDs this item was derived from

### `EvidenceEnvelope` (`evidence_envelope.v1`)
Container that groups evidence produced by one tool call:
- `source_tool`: tool name
- `source_query`: optional tool input/query
- `evidence[]`: list of `Evidence`

### `ToolResult` (`tool_result.v1`)
Standard tool execution result:
- `success`: boolean
- `data`: arbitrary JSON payload
- `error`: optional error string
- `source_urls[]`: legacy URL-only provenance (kept for compatibility)
- `evidence[]`: list of `EvidenceEnvelope` (preferred)

## Usage

- Tools should return `ToolResult(..., evidence=[EvidenceEnvelope(...)])` when possible.
- Synthesis layers can collect:
  - `source_urls` for a simple “Sources” list
  - or `evidence[]` for stronger evidence binding + citation validation (`validate_citations`).

## Versioning Policy
- Contract files are versioned by name (`*.v1.json`).
- **Breaking changes require a new major** (e.g., `v2`) and migration notes.
- Within `v1`, changes must be additive and backwards compatible.

