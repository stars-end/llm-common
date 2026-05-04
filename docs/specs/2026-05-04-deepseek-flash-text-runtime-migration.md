# DeepSeek Flash Text Runtime Migration

Date: 2026-05-04
Feature-Key: bd-t76k5
Source evidence: bd-2r5f2, llm-common PR #102

## Summary

Migrate the shared and product text runtime lanes from Z.ai-shaped/default text behavior to a DeepSeek Flash text lane, while keeping Z.ai scoped to vision and explicitly retained fallback surfaces.

The migration is intentionally phased, but the Phase 1.5 validation gate is mandatory. Phase 2 must not start until real-ish Prime Advisor tool loops and Affordabot economics JSON/review loops pass or receive explicit HITL override.

## Problem

The POC in bd-2r5f2 showed that DeepSeek Flash is viable for the two important direct text use cases:

- Prime Advisor tool loops
- Affordabot economics generation/review JSON contracts

It also showed that the current Z.ai text baseline could not be cleanly rerun because the lane was blocked by account/package/rate-limit failures. The next risk is no longer basic DeepSeek viability. The next risk is migrating too much runtime surface before the shared text lane has proven traffic-like stability.

## Goals

- Make DeepSeek Flash the default text lane for in-scope shared/product text paths.
- Keep Z.ai available for vision and explicitly retained non-text fallback behavior.
- Preserve product-specific policy ownership in `prime-radiant-ai` and `affordabot`.
- Use `llm-common` for reusable provider/client/model-selection/cost/error/env contracts.
- Require traffic-like validation before migrating direct Z.ai-shaped runtime paths.
- Keep broad search provider changes, vision changes, and cleanup-only churn out of early phases.

## Non-Goals

- Do not migrate vision paths to DeepSeek Flash.
- Do not change broad web/search provider policy in this migration.
- Do not remove every historical Z.ai reference in Phase 1.
- Do not split one runtime path across multiple agents in the same phase.
- Do not let product repos invent shared provider abstractions that belong in `llm-common`.

## Active Contract

Runtime truth after the migration:

- Text default: DeepSeek Flash through the verified shared provider/model-selection contract.
- Vision default: Z.ai, unless a separate future vision migration explicitly changes it.
- Product ownership: Prime and Affordabot own their runtime policy and validation fixtures.
- Shared ownership: `llm-common` owns reusable client/provider/default/cost/error/env behavior.

The exact provider slug, transport parameters, and cost metadata must be verified at Phase 1a kickoff against the active provider surface. Do not freeze stale model ids or pricing from planning text.

## Ownership Boundaries

### llm-common

Owns reusable platform behavior:

- DeepSeek text provider/client surface
- shared text-default/model-selection behavior
- JSON-mode and tool-loop expectations
- thinking-off/default reasoning settings for tool loops when required
- cost, metrics, error taxonomy, and env naming
- shared contract that Z.ai is vision-only unless explicitly retained as text fallback

### prime-radiant-ai

Owns Prime product integration:

- advisor and portfolio runtime policy
- Prime config-driven/OpenRouter-backed text paths
- Prime advisor traffic-like tool-loop validation
- admin and diagnostic LLM endpoint behavior

### affordabot

Owns Affordabot product integration:

- economics-analysis generation/review fixtures
- Affordabot model-default wiring and product fallback behavior
- direct bridge/discovery text paths
- Windmill bridge/product runtime text assumptions

## Execution Phases

### Phase 0: Control Spec

Bead: bd-t76k5.1

Write and merge this migration control spec. This phase creates the shared execution contract, Beads graph, acceptance criteria, and dependency gates.

Exit criteria:

- Spec names goals, non-goals, boundaries, phases, validation, and first implementation task.
- Beads child tasks exist with hard dependencies.
- Phase 1.5 blocks Phase 2.

### Phase 1a: llm-common Shared Text Lane

Bead: bd-t76k5.2

Cut the shared text lane to DeepSeek Flash with minimal behavior change.

In scope:

- shared text-default and model-selection surfaces such as orchestrator, understanding, reflection, and tool-selection lanes
- provider/client behavior needed by product repos
- cost/metrics/error/env handling
- Z.ai vision-only boundary

Out of scope:

- product-specific runtime policy
- direct Z.ai transport migrations in product repos
- broad docs cleanup
- vision/search changes

Validation:

- structured JSON still validates
- fallback behavior still works
- metrics/cost tracking records the verified DeepSeek Flash model id
- text smoke tests work without Z.ai text access

Exit:

- shared in-scope text defaults point to DeepSeek Flash
- product repos can consume the shared text lane without local provider invention

### Phase 1b: Prime Text Lane Cutover

Bead: bd-t76k5.3

Cut Prime config-driven/OpenRouter-backed text paths onto the shared DeepSeek Flash lane.

Likely touch points:

- `llm_config.py`
- `llm_portfolio_analyzer.py`
- related config-driven text-default surfaces

Validation:

- Prime advisor/config smoke flows work without relying on `ZAI_API_KEY` for text
- fallback behavior still works
- cost/metrics remain correct
- vision/search behavior is unchanged

### Phase 1c: Affordabot Economics Text Lane Cutover

Bead: bd-t76k5.4

Cut Affordabot core model-default economics text wiring onto the shared DeepSeek Flash lane.

Likely touch points:

- `main.py`
- core analysis pipeline model-default wiring
- product-specific fallback configuration

Validation:

- economics JSON fixtures validate
- review fixtures validate conservative behavior
- core text flows smoke-test without `ZAI_API_KEY`
- Windmill, search, bridge, and vision surfaces are unchanged in this phase

### Phase 1.5: Mandatory Traffic-Like Validation Gate

Bead: bd-t76k5.5

This is a hard blocker before Phase 2.

Run:

- real-ish Prime Advisor tool loops
- real-ish Affordabot JSON/review loops

Verify:

- tool-call stability
- JSON first-pass and final-pass rates
- latency remains acceptable for small orchestration calls
- review/critique behavior remains conservative enough
- fallback behavior still works
- metrics/cost tracking stays accurate

Exit:

- Phase 2 may start only if validation passes, or if HITL explicitly overrides the gate with known bounded failures.

### Phase 2: Z.ai-Shaped Text Runtime Migration

Bead: bd-t76k5.6

Migrate harder runtime paths that are coupled to Z.ai transport, error semantics, strict JSON assumptions, or diagnostics.

Prime in scope:

- `direct_advisor.py`
- `portfolio_advisor.py`
- `pydanticai_runtime.py`
- admin/diagnostic LLM endpoints such as `admin.py`

Affordabot in scope:

- core pipeline/provider wiring such as `orchestrator.py`
- direct bridge/discovery text paths such as `bridge.py` and `auto_discovery_service.py`
- Windmill bridge integration where text provider assumptions are still Z.ai-shaped

Out of scope:

- vision paths
- broad search-provider changes
- cleanup-only docs churn

Validation:

- text runtime paths work without `ZAI_API_KEY`
- retries and failure taxonomy remain accurate
- health and diagnostic endpoints reflect the new provider truth
- Z.ai remains only for vision or explicitly retained non-text fallback behavior

Exit:

- no direct production text runtime depends on Z.ai transport

### Phase 3: Cleanup And Convergence

Bead: bd-t76k5.7

Clean stale runtime references after the behavior migration works.

Likely touch points:

- `glm_models.py`
- `llm_config.py`
- `main.py`
- runtime-adjacent docs in all three repos

Validation:

- env/runtime docs match active behavior
- no stale active default-text references remain
- health checks state: text = DeepSeek Flash, vision = Z.ai
- cleanup does not introduce behavior changes

## Beads Structure

- Epic: bd-t76k5, DeepSeek Flash text runtime migration
- bd-t76k5.1: Phase 0 control spec
- bd-t76k5.2: Phase 1a llm-common shared text lane
- bd-t76k5.3: Phase 1b Prime text lane cutover
- bd-t76k5.4: Phase 1c Affordabot economics text lane cutover
- bd-t76k5.5: Phase 1.5 mandatory traffic-like validation gate
- bd-t76k5.6: Phase 2 Z.ai-shaped text runtime migration
- bd-t76k5.7: Phase 3 cleanup and convergence

Blocking edges:

- bd-t76k5.1 blocks bd-t76k5.2
- bd-t76k5.2 blocks bd-t76k5.3 and bd-t76k5.4
- bd-t76k5.3 and bd-t76k5.4 block bd-t76k5.5
- bd-t76k5.5 blocks bd-t76k5.6
- bd-t76k5.6 blocks bd-t76k5.7

## Agent Strategy

Use at most two implementation agents at a time. Default implementation model is `gpt-5.3-codex` unless the orchestrator records a deliberate override. Batch by outcome:

- Agent A: `llm-common` shared provider/default work.
- Agent B: product integration in either `prime-radiant-ai` or `affordabot`, only after shared surfaces land.

Do not assign the same runtime path to two agents in the same phase. Product agents consume shared contracts; they do not create parallel provider abstractions.

## Validation Gates

Every implementation PR must include:

- exact provider/model id used at runtime
- whether text paths require `ZAI_API_KEY`
- JSON/schema validation evidence where applicable
- fallback/error-path evidence
- cost/metrics evidence
- explicit statement that vision/search behavior was not changed unless the Bead scope says otherwise

Phase 1.5 evidence must include:

- Prime advisor loop cases and outcomes
- Affordabot JSON/review fixture cases and outcomes
- first-pass/final-pass JSON rates
- latency summary
- conservative-review assessment
- remaining blockers, if any

## Risks

- JSON-mode drift: require schema validation before and after provider cutover.
- Tool-loop instability: keep Phase 1.5 mandatory before direct runtime migrations.
- Cost/metrics drift: verify recorded model ids and prices at kickoff and in smoke evidence.
- Product-policy leakage: keep reusable behavior in `llm-common`, product decisions in product repos.
- Scope creep: keep search and vision out unless separately approved.

## Recommended First Task

Start bd-t76k5.2 after this spec merges.

The first implementation task should verify the current DeepSeek Flash provider slug, transport requirements, and cost metadata, then cut the shared text-default/model-selection lane in `llm-common` with tests/smokes that product repos can trust.
