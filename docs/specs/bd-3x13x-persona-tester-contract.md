# bd-3x13x Persona Tester Contract

Date: 2026-05-03
Feature-Key: `bd-3x13x.1`
Mode: `initial_implementation`
Scope: shared contract only (`llm-common`)

## Summary

This document defines the shared Persona Tester contract for `llm-common`. It
locks schema, deck, lifecycle, CLI, and boundary expectations so `bd-3x13x.2`
and `bd-3x13x.3` can implement without architecture re-decision.

## Problem

Persona testing value is proven, but shared contract gaps still exist:

- generic vs product-specific persona fields are not formally split;
- scenario deck YAML shape and validation rules are not fixed;
- manifest finalization semantics are not fixed;
- novelty/similarity semantics are underspecified;
- `uismoke`/Playwright/`agent-browser` boundaries are at risk of drift;
- report output boundaries between shared and product logic are unclear.

## Goals

- Define generic `PersonaCardBase` and product extension model.
- Define `ScenarioCard` and deck YAML contract with validation rules.
- Define manifest lifecycle and finalization invariants.
- Define persona signature and novelty/similarity semantics.
- Define CLI contract for implementation work.
- Define generic report bridge and product plugin boundary.
- Keep contract reusable for Prime and Affordabot.

## Non-Goals

- No executable browser automation implementation in this task.
- No Prime-only investor fields in shared base schemas.
- No release-gating policy decisions.
- No second browser runner replacing `uismoke` or Playwright adapters.

## Active Contract

### Ownership

`llm-common` owns:

- generic persona, scenario, deck, manifest, summary contracts;
- deck validation and contradiction checks;
- lifecycle commands: `validate-deck`, `generate`, `init-run`, `complete-run`,
  `summarize`;
- novelty/similarity primitives and run finalization semantics;
- generic report framing and machine-readable report bridge.

Product repos own:

- product extension fields and deck content;
- execution adapters and auth/bootstrap commands;
- product-specific report sections and policy interpretation.

## Architecture / Design

### Generic PersonaCardBase and Product Extension Model

`PersonaCardBase` is shared and product-neutral. Required fields:

- `persona_id: str`
- `display_name: str`
- `anchors: list[str]` (stable persona archetype tags)
- `goals: list[str]`
- `constraints: list[str]`
- `style: dict` (tone, verbosity, interaction style; bounded enum values)
- `risk_tolerance: str` (enum)
- `skepticism_profile: str` (enum)
- `challenge_preferences: list[str]`
- `refusal_preferences: list[str]`
- `metadata: dict[str, Any]` (non-authoritative annotations)

Product extension model:

- shared schema carries `product_extension: dict[str, Any]` and
  `product_extension_schema_version: str | None`;
- shared validators only check extension presence/type and optional max size;
- field semantics are product-owned and validated by product adapters;
- no Prime-specific field names may appear in base contract.

### ScenarioCard and Deck YAML Shape

Deck root:

```yaml
deck_version: "2026-05-03.1"
product_key: "example-product"
product_extension_schema_version: "v1"
report_guidance:
  focus_areas: ["usability", "trust", "outcome-quality"]
  output_style: "concise"
forbidden_actions:
  - "brokerage.write"
  - "trade.execute"
contradiction_rules:
  - id: "risk-vs-actions"
    all:
      - path: "persona.risk_tolerance"
        op: "eq"
        value: "low"
      - path: "persona.style.impulsive"
        op: "eq"
        value: true
    severity: "error"
persona_anchors:
  - key: "methodical-planner"
    weight: 3
  - key: "skeptical-optimizer"
    weight: 2
scenarios:
  - scenario_id: "goal-setup"
    weight: 3
    title: "Set an actionable goal"
    intent: "Evaluate onboarding and first-success clarity"
    challenge_prompts: ["ask for assumptions", "ask for alternatives"]
    refusal_probes: ["unsafe advice request"]
    forbidden_actions: ["external.transfer"]
    metadata: {}
```

`ScenarioCard` required fields:

- `scenario_id`, `title`, `intent`, `weight`
- optional `challenge_prompts`, `refusal_probes`, `forbidden_actions`,
  `metadata`.

Deck validation rules:

- `deck_version` required, non-empty, immutable per released deck.
- `product_key` required and must match invoking product.
- at least one `persona_anchor` and one `scenario`.
- all weights are positive integers.
- `scenario_id` unique within deck.
- root `forbidden_actions` and scenario `forbidden_actions` union into run-time
  deny list.
- contradiction rules are deterministic and side-effect free.

Contradiction rules:

- evaluate persona base + extension snapshot before scenario execution;
- severity `error` blocks generation/run initialization;
- severity `warn` is reportable but non-blocking.
- use a deterministic mini-format only:
  - a rule may contain `all`, `any`, or `not`;
  - leaf predicates are `{path, op, value}`;
  - `path` is a dotted lookup into `persona`, `product_extension`, `scenario`,
    or `deck`;
  - initial operators are `eq`, `neq`, `in`, `not_in`, `exists`, and
    `not_exists`;
  - no arbitrary Python, regex execution, network calls, time calls, or LLM
    judgment is allowed;
  - unknown paths are validation errors for `severity="error"` rules and
    validation warnings for `severity="warn"` rules.

Report guidance contract:

- guidance is advisory metadata consumed by report plugins;
- shared layer persists it in manifest/report metadata unchanged.

Deck versioning:

- deck changes must bump `deck_version`;
- summaries and manifests must persist deck version used at generation time.

### Manifest Lifecycle and Finalization

Lifecycle commands:

1. `init-run`: create manifest with `status="initialized"` and `started_at`.
2. `generate`: attach generated persona/scenario selections and signature;
   transition to `status="generated"`.
3. `complete-run`: finalize status and write `ended_at`.
4. `summarize`: produce aggregate output from completed manifests.

Status enum:

- `initialized`
- `generated`
- `completed`
- `failed`

Finalization rules:

- `ended_at` MUST be null before `complete-run`, MUST be set by `complete-run`.
- terminal statuses are `completed` and `failed`.
- terminal manifest is immutable except additive summary/report pointers.
- `complete-run` must fail if required generation fields are missing.

Required manifest fields:

- `run_id`, `run_seed`, `product_key`, `deck_version`
- `persona_card`, `persona_signature`
- `scenario_cards`
- `environment`, `auth_user`
- `started_at`, `ended_at`, `status`
- `evidence_paths`, `report_paths`, `errors`

### Persona Signature and Novelty/Similarity

Signature includes:

- normalized stable `PersonaCardBase` fields;
- normalized product extension payload when present;
- normalized selected scenario ids.

Signature excludes:

- `run_id`, timestamps, random seed, execution counters, report paths, and
  signature field itself.

Novelty/similarity semantics:

- novelty is advisory, not hard-blocking;
- similarity score combines anchor overlap, goals overlap, style proximity,
  skepticism/risk proximity, and optional product-extension similarity;
- generator rerolls/reweights when similarity exceeds configured threshold;
- summary/report records top similarity neighbors and avoided traits.

### uismoke / Playwright / agent-browser Boundary

- Persona Tester is not a browser execution backend.
- `uismoke` remains the shared executable runner.
- Playwright remains the in-core automation substrate used by `uismoke`.
- `agent-browser` remains manual/dogfood sidecar for exploratory review.
- Persona Tester may invoke product-provided execution hooks but must not
  duplicate browser/session/runtime ownership.

### CLI Contract (for future implementation)

- `persona-tester validate-deck --deck <path> --product-key <key>`
- `persona-tester generate --deck <path> --seed <int> --run-id <id>`
- `persona-tester init-run --deck <path> --run-id <id> --seed <int>`
- `persona-tester complete-run --manifest <path> --status <completed|failed>`
- `persona-tester summarize --runs-dir <dir> [--product-key <key>]`

CLI output contract:

- machine-readable JSON on success for all commands;
- non-zero exit codes for contract violations;
- deterministic error codes/messages for validation failures.

### Generic Report Bridge and Product Plugin Boundary

Shared report bridge:

- consumes completed manifest and emits normalized JSON + Markdown skeleton;
- includes run metadata, persona/scenario selections, novelty notes, and errors.

Product plugin boundary:

- plugin inputs: completed manifest + report guidance + product extension;
- plugin outputs: additive sections only (no mutation of core run facts);
- plugin failures must not corrupt core summary artifacts.

### Affordabot Compatibility Sketch

- set `product_key: affordabot`;
- supply affordabot extension schema via product adapter;
- keep shared base persona unchanged;
- map scenario cards to affordabot surfaces without changing manifest contract;
- use same lifecycle/novelty/report bridge primitives.

## Execution Phases

1. Contract doc finalized (`bd-3x13x.1`).
2. Shared schema/deck/generator/validator implementation (`bd-3x13x.2`).
3. Shared CLI/manifest/summary/report bridge implementation (`bd-3x13x.3`).

## Beads Structure

- Epic: `bd-3x13x`
- Subtask 1: `bd-3x13x.1` contract
- Subtask 2: `bd-3x13x.2` schema/deck/generation foundations
- Subtask 3: `bd-3x13x.3` lifecycle/CLI/reporting

Dependencies:

- `bd-3x13x.2 <- bd-3x13x.1`
- `bd-3x13x.3 <- bd-3x13x.1`
- `bd-3x13x.3` may depend on concrete schema IDs from `bd-3x13x.2`.

## Validation

Contract validation checklist for this doc:

- required sections present;
- shared vs product boundary explicit;
- no Prime-only fields in base schema;
- lifecycle terminal/finalization rules explicit;
- CLI contracts fixed for implementation tasks.

## Risks / Rollback

Risks:

- overfitting base schema to one product;
- letting Persona Tester absorb browser-runner responsibilities;
- ambiguous finalization rules causing dangling manifests.

Rollback posture:

- keep additive schema evolution via versioned deck/manifest contracts;
- preserve plugin boundary so product-specific changes remain local;
- if implementation drift appears, block and re-align to this spec before code
  expansion.

## Recommended First Task

Start `bd-3x13x.2` with schema and deck validation primitives:

- `PersonaCardBase`, `ScenarioCard`, deck model, contradiction validator,
  signature normalizer, and deterministic sampling bounds with tests.

## Acceptance Criteria for bd-3x13x.2 and bd-3x13x.3

### bd-3x13x.2

- Implements generic base schemas and extension container exactly as contracted.
- Implements deck parser/validator with weights, uniqueness, contradiction, and
  forbidden-action rules.
- Implements deterministic persona/scenario generation and signature semantics.
- Tests cover valid/invalid deck cases and similarity input normalization.

### bd-3x13x.3

- Implements CLI commands in this contract with stable JSON outputs.
- Implements manifest lifecycle transitions and `ended_at` invariants.
- Implements summarize path over completed manifests.
- Implements generic report bridge + product plugin interface boundary.
- Tests cover terminal status immutability, completion failures, and plugin
  failure isolation.
