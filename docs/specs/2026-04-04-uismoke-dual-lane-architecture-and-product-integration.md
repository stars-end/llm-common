# UISmoke Dual-Lane Architecture And Product Integration

Date: 2026-04-04

Feature-Key: bd-go96e

Mode: initial_implementation

Cross-repo coordination input:
- affordabot PR #393 spec: `docs/specs/2026-04-04-expanded-new-family-wave-with-substrate-story-pack.md`

## Summary

`uismoke` should remain the shared execution engine, but it should stop behaving like a single GLM-centric runner with a deterministic flag bolted on. The approved target is a dual-lane architecture:

1. deterministic lane
2. exploratory lane

The deterministic lane is the shared deterministic execution lane. It stays Playwright-backed and provider-free, and is suitable for repo-local wrappers that need reproducible checks.

The exploratory lane stays inside the shared `uismoke` engine and is explicitly advisory by default. It uses the same Playwright session model plus an exploratory planner/LLM interface for non-deterministic steps, richer forensics, and nightly or operator-invoked runs.

Stories remain repo-local. Product repos own story packs, Make targets, validation scripts, drift guards, and release semantics. `llm-common` owns the engine, lane orchestration, Playwright runtime, artifact schema, and generic triage primitives.
`llm-common` does not own founder or merge-gate authority; callers decide whether results are blocking.

`agent-browser` should not become the first in-core `uismoke` backend. It should remain a manual or dogfood sidecar for founder UX review, exploratory QA, screenshots, and human-in-the-loop inspection.

## Grounded Repo Findings

### Shared Engine (`llm-common`)

- The current runner exposes `deterministic_only`, but still unconditionally requires `ZAI_API_KEY` and initializes `GLMVisionClient` before any story runs, including deterministic-only runs. See [`uismoke_runner.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/uismoke_runner.py#L44), [`uismoke_runner.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/uismoke_runner.py#L115), and [`uismoke_runner.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/uismoke_runner.py#L121).
- The same runner already treats deterministic-only success differently from full runs, which shows the lane split is conceptually present but not structurally isolated yet. See [`uismoke_runner.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/uismoke_runner.py#L227).
- `UISmokeAgent` already has a real deterministic executor path for structured actions and a separate LLM loop for the rest, but both live in one class. See deterministic execution in [`ui_smoke_agent.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/ui_smoke_agent.py#L168) and exploratory execution in [`ui_smoke_agent.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/ui_smoke_agent.py#L520).
- The exploratory path is tightly coupled to GLM model names and retry behavior (`glm-4.6v` then `glm-4.5v`). See [`ui_smoke_agent.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/ui_smoke_agent.py#L668).
- Playwright is already the canonical in-core runtime backend via `create_playwright_context()` and `PlaywrightAdapter`. See [`playwright_adapter.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/runtime/playwright_adapter.py#L17) and [`playwright_adapter.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/runtime/playwright_adapter.py#L339).
- Shared triage exists today and converts run artifacts into product, story-stability, and harness/environment buckets. See [`uismoke_triage.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/uismoke_triage.py#L19).
- Existing `llm-common` docs already describe the intended ownership split as shared core abstractions in `llm-common` and story/workflow ownership in application repos. See [`UI_SMOKE_AGENT.md`](/tmp/agents/bd-go96e/llm-common/docs/UI_SMOKE_AGENT.md#L39).

### Affordabot

- The current story index is a single top-level admin-console pack and does not yet promote the substrate viewer as the canonical executable surface. See [`README.md`](/Users/fengning/affordabot/docs/TESTING/STORIES/README.md#L1).
- Repo-local Make targets already invoke `uismoke` directly against repo-local stories, which is the right ownership pattern. See [`Makefile`](/Users/fengning/affordabot/Makefile#L269).
- Affordabot already has the product substrate viewer surface needed for a canonical story pack:
  - recent runs
  - failure buckets
  - raw row list
  - raw row detail
  See [`SubstrateExplorer.tsx`](/Users/fengning/affordabot/frontend/src/components/admin/SubstrateExplorer.tsx#L45).
- The frontend service layer already exposes substrate run, failure bucket, raw rows, and raw detail endpoints. See [`adminService.ts`](/Users/fengning/affordabot/frontend/src/services/adminService.ts#L211).
- The backend already supports run list, summary, failure bucket, raw-row list, and raw-row detail APIs. See [`admin.py`](/Users/fengning/affordabot/backend/routers/admin.py#L371), [`admin.py`](/Users/fengning/affordabot/backend/routers/admin.py#L465), [`admin.py`](/Users/fengning/affordabot/backend/routers/admin.py#L507), [`admin.py`](/Users/fengning/affordabot/backend/routers/admin.py#L538), and [`admin.py`](/Users/fengning/affordabot/backend/routers/admin.py#L618).
- The coordination spec in affordabot PR #393 explicitly says the new substrate viewer story pack should stay repo-local and be wired into existing affordabot verification surfaces, while the `uismoke` engine refactor stays in a separate `llm-common` lane.

### Prime Radiant AI

- Prime already distinguishes executable story ownership from governance/history by keeping `production_v2/` executable and `production-v2/` non-executable. See [`README.md`](/Users/fengning/prime-radiant-ai/docs/TESTING/STORIES/README.md#L11) and [`README.md`](/Users/fengning/prime-radiant-ai/docs/TESTING/STORIES/README.md#L57).
- Prime already states the most important contract discipline clearly: UISmoke stories are executable but non-authoritative, and Playwright contract tests remain the release gate. See [`production_v2/README.md`](/Users/fengning/prime-radiant-ai/docs/TESTING/STORIES/production_v2/README.md#L3) and [`Makefile`](/Users/fengning/prime-radiant-ai/Makefile#L486).
- Prime keeps repo-local validators and drift guards that enforce story directory, selector, and contract discipline. See [`validate-story-contracts.py`](/Users/fengning/prime-radiant-ai/scripts/verification/validate-story-contracts.py#L34) and [`v2_story_drift_guard.py`](/Users/fengning/prime-radiant-ai/scripts/verification/v2_story_drift_guard.py#L27).
- Prime’s Makefile already expresses a clean release split:
  - authoritative deterministic contract gate with Playwright
  - non-authoritative `uismoke` regression/nightly surfaces
  See [`Makefile`](/Users/fengning/prime-radiant-ai/Makefile#L486), [`Makefile`](/Users/fengning/prime-radiant-ai/Makefile#L524), and [`Makefile`](/Users/fengning/prime-radiant-ai/Makefile#L620).
- Prime’s overnight script already operationalizes the desired flow: deterministic gate first, exploratory run second, triage after. See [`uismoke-overnight.sh`](/Users/fengning/prime-radiant-ai/scripts/verification/uismoke-overnight.sh#L9).

## Target Architecture

### Decision

Adopt a three-surface model:

1. `uismoke` deterministic lane
2. `uismoke` exploratory lane
3. `agent-browser` manual sidecar

Only the first two are part of the shared engine. The third is intentionally outside the engine core.

### Lane Contract

| Surface | Purpose | Backend | Failure Semantics | Default Use |
|---|---|---|---|---|
| Deterministic lane | Stable executable story verification | Playwright only | Deterministic pass/fail output; wrappers may treat as blocking | fast repro, CI wrappers, deterministic evidence |
| Exploratory lane | Ambiguous-step completion, richer nightly evidence, advisory product surfacing | Playwright + exploratory planner/LLM | Advisory by default; may fail nightly jobs if repo opts in | nightly, debugging, single-story investigation |
| Manual sidecar | Operator QA, dogfood, screenshots, discovery, bug-hunting | `agent-browser` | Never a shared-engine authority surface | ad hoc human or agent-driven review |

### Required Engine Split

The shared engine should be reorganized around explicit lane selection instead of implicit GLM coupling:

- `uismoke_runner.py`
  - becomes lane-neutral orchestration plus CLI
  - selects deterministic, exploratory, or mixed execution
- deterministic executor
  - executes structured steps and validations only
  - never initializes an LLM client
- exploratory executor
  - invoked only for non-deterministic steps or explicit exploratory runs
  - owns model/provider selection and retry policy
- Playwright runtime
  - shared by both lanes
  - remains the canonical automation backend
- artifact writer
  - records lane metadata consistently for both paths

### Exact First Refactor To Remove Unnecessary GLM Coupling

The first refactor should target the current unconditional provider startup path:

1. Move GLM client initialization out of `UISmokeRunner.run()` and behind a lane gate.
   - Current coupling lives in [`uismoke_runner.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/uismoke_runner.py#L115).
2. Extract the exploratory LLM step loop out of `UISmokeAgent` into a provider-backed planner/executor interface.
   - Current hardcoding lives in [`ui_smoke_agent.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/ui_smoke_agent.py#L668).
3. Keep deterministic step execution as a provider-free path and ensure deterministic runs work without `ZAI_API_KEY`.
   - Current deterministic executor already exists in [`ui_smoke_agent.py`](/tmp/agents/bd-go96e/llm-common/llm_common/agents/ui_smoke_agent.py#L168).

Recommended new shared modules:

- `llm_common/agents/uismoke/lane_runner.py`
- `llm_common/agents/uismoke/deterministic_executor.py`
- `llm_common/agents/uismoke/exploratory_executor.py`
- `llm_common/agents/uismoke/exploration_provider.py`

The immediate goal is not a perfect class hierarchy. The immediate goal is to make deterministic runs provider-free and make exploratory behavior explicit.

## Deterministic vs Exploratory Lane Contract

### Deterministic Lane

Rules:

- Uses Playwright only.
- Runs only deterministic steps.
- Requires no LLM API key.
- May run with `--max-tool-iterations 1` or no exploratory loop at all.
- Produces deterministic artifacts suitable for evidence and repo-local policy evaluation.
- Fails fast on harness, auth, navigation, selector, and deterministic assertion failures.

Expected product-level usage:

- affordabot deterministic substrate verification subset
- affordabot stable admin deterministic subset
- prime-radiant-ai contract-adjacent or regression-support deterministic subsets

### Exploratory Lane

Rules:

- Uses the same Playwright runtime, not a different browser backend.
- Invokes an exploratory planner only when a story step is explicitly non-deterministic or when the run is configured as exploratory/mixed.
- Defaults to advisory classification semantics for ambiguous or LLM-only failures.
- Produces richer evidence: debug screenshots, HTML, step traces, model/provider metadata.

Exploratory lane should be allowed to:

- complete steps with vision/tool reasoning
- gather more forensics
- exercise nightly or operator scenarios

Exploratory lane should not be allowed to:

- redefine product repo release policy
- replace Playwright contract gates
- silently become required for deterministic CI

### Mixed Runs

Mixed runs are acceptable for nightly or investigation usage:

- deterministic steps execute first as usual
- exploratory executor is invoked only when a step requires it
- artifacts record which lane actually executed each step

This keeps one story format while making execution semantics explicit.

## Playwright vs `agent-browser`

### Playwright Stays In-Core

Playwright belongs in the shared engine because it is:

- scriptable
- reproducible
- suitable for CI
- already implemented as the canonical adapter in `llm-common`

No architecture change should move primary execution away from Playwright.

### `agent-browser` Stays A Sidecar

`agent-browser` belongs outside the core `uismoke` engine for:

- founder UX dogfooding
- manual review capture
- exploratory navigation not expressed as executable stories
- screenshot and session walkthrough collection

Recommended placement:

- repo-local scripts or skills
- docs-driven QA workflows
- optional follow-up after a `uismoke` failure or before promoting a story

Not recommended:

- replacing `PlaywrightAdapter`
- making `agent-browser` the default backend for CI or `uismoke run`
- forcing product repos to express manual QA inside the engine core

## Story Ownership Contract

### Shared Engine Owns

- story loading/parsing primitives
- lane selection and orchestration
- Playwright runtime/backend
- shared artifact schema
- shared failure taxonomy and generic triage helpers
- CLI flags and generic JSON artifact layout

### Product Repos Own

- story YAML files
- story-pack READMEs and product rationale
- Make targets and invocation policies
- validation scripts and drift guards
- release authority semantics
- route/auth matrices
- product-specific selector and data-contract validation

### Explicit Boundary

Do not centralize story packs into `llm-common`.

The engine can define:

- story schema
- artifact schema
- lane schema

The engine should not own:

- affordabot substrate stories
- prime-radiant-ai `production_v2` stories
- repo release gates

This is consistent with the historical `llm-common` documentation split in [`UI_SMOKE_AGENT.md`](/tmp/agents/bd-go96e/llm-common/docs/UI_SMOKE_AGENT.md#L39) and with prime-radiant-ai’s existing repo-local contract discipline.

## Artifact And Triage Contract

Shared artifacts should gain lane-aware metadata without taking story ownership away from product repos.

Add to `run.json` metadata:

- `lane`: `deterministic`, `exploratory`, or `mixed`
- `backend`: `playwright`
- `llm_provider`: provider id or `null`
- `llm_model`: model id or `null`
- `story_repo`: repo name
- `story_pack`: repo-local story pack id
- `deterministic_steps`
- `exploratory_steps`

Add to each story summary:

- `lane_used`
- `step_lane_breakdown`
- `advisory_only`

Triage implications:

- deterministic lane failures should remain triage-worthy by default
- exploratory-only failures should default to advisory triage unless the repo explicitly opts into blocking behavior for that pack
- harness failures discovered during deterministic-only runs should stay high-priority

## Affordabot Integration Recommendation

### Recommendation

Rebase Batch 2 onto the already-published repo-local affordabot substrate viewer story pack and wire that pack into the canonical repo-local Make targets. Do not put these stories in `llm-common`, and do not introduce a second parallel pack layout from `llm-common`.

### Why

Affordabot already has the right product surface and APIs, but its current top-level story pack still describes the older admin-console truth instead of substrate viewer truth. The coordination spec for PR #393 explicitly calls this out.

### Story Pack Constraint

Batch 2 must assume the substrate pack already exists in affordabot’s repo-local testing surface, even if the current local snapshot used for this memo does not yet show it.

That means Batch 2 should:

- discover and reuse the published affordabot substrate pack location and story IDs
- update the affordabot story index to point at that pack if needed
- adjust Make targets to call that pack directly

Batch 2 should not:

- invent a second subtree
- duplicate the published substrate stories under a new layout
- move the pack into `llm-common`

### Recommended Affordabot Make Surface

Add or update repo-local targets such as:

- `verify-substrate-gate`
  - deterministic lane
  - canonical gating subset for runs list, failure buckets, raw row detail
- `verify-substrate-qa`
  - mixed or exploratory lane
  - advisory by default
- `verify-substrate-nightly`
  - repro-friendly exploratory lane
- `verify-substrate-triage`
  - shared triage against latest substrate artifact set

Do not immediately replace all existing affordabot story targets. Promote the already-published substrate surface into the first-class verification path, prove it, then decide whether broader story-pack reorganization is worthwhile.

### Affordabot Gate Design

The first deterministic substrate gate should verify:

1. runs list renders
2. selecting a run loads summary and failure buckets
3. raw rows list loads for a run
4. selecting a raw row loads row detail

This aligns directly with the current frontend and backend shape in:

- [`SubstrateExplorer.tsx`](/Users/fengning/affordabot/frontend/src/components/admin/SubstrateExplorer.tsx#L75)
- [`adminService.ts`](/Users/fengning/affordabot/frontend/src/services/adminService.ts#L211)
- [`admin.py`](/Users/fengning/affordabot/backend/routers/admin.py#L371)

## Prime Radiant AI Integration Recommendation

### Recommendation

Prime should keep its current repo-local contract discipline and adopt the new shared engine only as an execution improvement, not as a testing-governance reset.

### Preserve What Already Works

Keep these repo-local choices:

- `production_v2/` is the executable story directory
- `production-v2/` stays governance/history only
- Playwright `verify-v2-contract` remains authoritative
- `uismoke` regression/nightly remains non-authoritative support
- selector and drift guard scripts remain repo-local

The current evidence strongly supports that this is the better ownership pattern. See:

- [`README.md`](/Users/fengning/prime-radiant-ai/docs/TESTING/STORIES/README.md#L11)
- [`production_v2/README.md`](/Users/fengning/prime-radiant-ai/docs/TESTING/STORIES/production_v2/README.md#L17)
- [`validate-story-contracts.py`](/Users/fengning/prime-radiant-ai/scripts/verification/validate-story-contracts.py#L34)
- [`v2_story_drift_guard.py`](/Users/fengning/prime-radiant-ai/scripts/verification/v2_story_drift_guard.py#L27)

### Alignment Work

Prime should align by:

- consuming the shared deterministic/exploratory lane split from `llm-common`
- keeping repo-local `verify-v2*` targets
- preserving Playwright authority
- adding lane metadata to regression/nightly artifacts
- optionally renaming internal docs or scripts to use the new lane vocabulary

Prime should not be forced into affordabot’s product semantics, and affordabot should not inherit prime’s release authority model.

## Validation Gates

### Shared Engine Gate

- deterministic lane must run without `ZAI_API_KEY`
- exploratory lane must initialize provider only when used
- Playwright remains the only in-core backend
- artifact schema records lane/backend/provider metadata

### Affordabot Gate

- canonical substrate viewer stories remain repo-local
- deterministic substrate gate covers runs, failure buckets, raw row detail
- Make targets call repo-local story pack, not `llm-common` story assets

### Prime Gate

- `verify-v2-contract` remains Playwright-authoritative
- executable story directory remains `production_v2/`
- repo-local validators remain the source of truth for selector and drift checks

## Do Not Do This

- Do not centralize affordabot or prime-radiant-ai stories into `llm-common`.
- Do not make `agent-browser` the first in-core `uismoke` backend.
- Do not collapse deterministic and exploratory semantics back into one opaque QA mode.
- Do not make exploratory/LLM results a mandatory pre-merge gate by default.
- Do not replace prime-radiant-ai’s Playwright product-contract gate with `uismoke`.
- Do not treat affordabot’s new substrate viewer story pack as a sidecar experiment; it must be wired into repo-local verification once added.
- Do not broaden this task into UI rewrites or cross-repo implementation churn.

## First Implementation Batches

### Batch 1: `llm-common` Engine Decoupling

Goal:

- make deterministic runs provider-free
- make exploratory execution explicit

Scope:

- refactor `uismoke_runner.py`
- extract exploratory executor/provider interface from `ui_smoke_agent.py`
- keep Playwright adapter untouched except for metadata plumbing
- add tests proving deterministic runs work without `ZAI_API_KEY`

Acceptance:

- `uismoke run --lane deterministic` works with no LLM credentials
- exploratory lane still works with existing GLM provider
- artifact metadata includes lane/backend/provider fields

### Batch 2: Affordabot Substrate Story Pack

Goal:

- make the substrate viewer the canonical executable truth for this product surface

Scope:

- reuse the already-published repo-local substrate story pack
- update repo-local substrate Make targets around that existing pack
- wire deterministic substrate gate and exploratory/nightly substrate surfaces
- keep stories in affordabot

Acceptance:

- deterministic substrate gate covers run list, failure buckets, and raw row detail
- the published substrate pack is reachable from affordabot’s story index
- no story assets are added to `llm-common`

### Batch 3: Prime Alignment Without Governance Regression

Goal:

- align Prime to the shared lane architecture without weakening its current contracts

Scope:

- adopt shared lane flags or metadata
- keep Playwright release gate authoritative
- keep repo-local validator and drift-guard ownership
- update overnight or regression wrappers only where terminology or metadata needs alignment

Acceptance:

- `verify-v2-contract` unchanged as release authority
- `verify-v2-regression` and `verify-v2-nightly` use the new lane model cleanly
- repo-local validators still pass unchanged or with minimal targeted updates

## Recommended First Implementation Batch

Start with Batch 1 in `llm-common`.

Reason:

- it removes the current unconditional GLM coupling
- it defines the contract both product repos will integrate against
- it avoids affordabot or prime-radiant-ai making repo-local workflow changes against a still-ambiguous engine

If Batch 1 is approved, the next product-facing move should be Batch 2 for affordabot, because the coordination spec already says the substrate viewer story pack is the missing executable product truth in that repo.
