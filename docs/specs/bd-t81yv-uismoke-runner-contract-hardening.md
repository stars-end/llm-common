# bd-t81yv uismoke Runner Contract Hardening

Date: 2026-04-07
Feature-Key: `bd-t81yv`

## Summary

This epic hardens `uismoke` as a shared runner contract without importing product-level
concepts from Prime into `llm-common`.

The failure to avoid is now clear:

- the earlier Prime-side QA rationalization was correct to avoid cross-repo work at the time
- later founder-live verification needed a deterministic browser runner again
- because `uismoke` role and inputs were not cleanly modeled, Prime ended up with a fuzzy
  boundary between repo-local lane semantics and shared runner mechanics

This epic fixes the shared side of that boundary.

## Problem

`uismoke` is being asked to support multiple real jobs:

- deterministic browser verification
- LLM-assisted semantic/evidence verification
- auth/bootstrap/session setup
- repo-local wrappers in application repos

Today those jobs are not cleanly separated enough. The main shared-code risks are:

1. **Product concepts leaking into the shared engine**
   - Prime has repo-local concepts like `founder_real_auth`
   - shared code should not adopt product naming for those concepts

2. **Execution mode ambiguity**
   - deterministic browser checks and LLM-backed semantic checks are both "uismoke"
   - their authority levels differ materially

3. **Browser substrate ambiguity**
   - Playwright is the right executable substrate
   - `agent-browser` is useful manually
   - the boundary between them is not explicit enough

4. **Repo integration friction**
   - wrappers need stable generic CLI inputs and machine-readable JSON results
   - without that, app repos grow bespoke harness glue

## Goals

- Define generic `uismoke` auth/bootstrap/session inputs.
- Split deterministic and LLM execution modes explicitly.
- Make Playwright the authoritative substrate for executable `uismoke` lanes.
- Publish a stable CLI and result schema for repo-local wrappers.
- Document `agent-browser` as a manual sidecar, not the authoritative gate substrate.

## Non-Goals

- Do not add product-specific lanes such as `founder_real_auth` to shared code.
- Do not move Prime story ownership into `llm-common`.
- Do not turn `agent-browser` into the executable gate runner.
- Do not decide which Prime prompts are gating from inside `llm-common`.

## Active Contract

`llm-common` will own only generic runner concepts:

- `mode`
  - `deterministic`
  - `llm`
- `auth_mode`
  - examples: `cookie_bypass`, `real_jwt`, `anon`
- `bootstrap`
  - session/bootstrap contract names, not product semantics
- browser substrate behavior
- CLI inputs
- machine-readable result schema

Prime and other consuming repos will map their repo-local lane names onto those generic
inputs.

## Architecture / Design

### 1. Generic lane contract, not product lane contract

The shared runner should support generic inputs like:

- `--mode deterministic`
- `--mode llm`
- `--auth-mode cookie_bypass`
- `--auth-mode real_jwt`
- `--bootstrap <name>`

It should **not** support product concepts like:

- `--lane founder_real_auth`

That mapping belongs in the consuming repo.

### 2. Deterministic vs LLM are first-class modes

These must be explicit, not implied.

Deterministic mode:
- structural checks
- stable selectors
- route/auth/bootstrap preconditions
- artifact shell and known labels
- suitable for authoritative gating when the consuming repo chooses to do so

LLM mode:
- semantic grading
- narrative quality
- fuzzy content assessment
- suitable for evidence/nightly support, not merge truth by default

### 3. Playwright is the shared substrate

Shared executable automation should be Playwright-first.

Why:
- deterministic assertions
- traces/screenshots
- stable navigation and auth helpers
- CI-friendly behavior

`agent-browser` remains useful, but as:
- manual reproduction
- exploratory debugging
- HITL support

It should not become the authoritative execution substrate for `uismoke`.

### 4. Stable JSON out

The result schema should clearly express:

- mode
- auth/bootstrap inputs used
- story identity
- pass/fail classification
- deterministic assertion failures vs LLM judgment failures
- artifacts/traces/screenshots produced

This lets consuming repos:
- wrap the runner cleanly
- build drift guards and gating logic locally
- avoid parsing ad hoc console output

## Execution Phases

### Phase 1: Generic config contract

- define generic auth/bootstrap/session model
- separate repo-local naming from shared inputs

### Phase 2: Explicit mode split

- make deterministic and LLM execution modes explicit in config, code path, and outputs

### Phase 3: Playwright substrate hardening

- unify reusable auth/bootstrap/session helpers
- make executable paths clearly Playwright-backed

### Phase 4: Stable CLI and result schema

- finalize CLI shape
- finalize JSON result contract
- document supported calling patterns

### Phase 5: Interop boundary docs

- document how consuming repos should use:
  - `uismoke deterministic`
  - `uismoke llm`
  - `agent-browser`

## Beads Structure

- Epic: `bd-t81yv` uismoke runner contract hardening and Playwright lane model
- Children:
  - `bd-520c4` Define generic uismoke auth, bootstrap, and lane config contract
  - `bd-m3jwi` Split uismoke deterministic and LLM execution modes
  - `bd-6c6mk` Harden Playwright-first uismoke substrate and shared bootstrap helpers
  - `bd-l2mex` Stabilize uismoke CLI inputs and machine-readable result schema
  - `bd-7jgbc` Document uismoke and agent-browser interoperability boundaries

Blocking edges:

- `bd-m3jwi <- bd-520c4`
- `bd-6c6mk <- bd-520c4`
- `bd-l2mex <- bd-m3jwi`
- `bd-l2mex <- bd-6c6mk`
- `bd-7jgbc <- bd-l2mex`

## Validation

Completion proof for `llm-common`:

- runner accepts generic auth/bootstrap inputs without repo-specific semantics
- deterministic and LLM modes are explicit and testable
- Playwright-backed execution path is the documented executable substrate
- result JSON is stable and consumable by app repos
- Prime integration can be wired without bespoke shared-code hacks

Likely validation surfaces:

- `uismoke --help`
- targeted unit tests for config parsing and result serialization
- deterministic sample story run
- LLM sample story run
- fixture-based JSON contract tests

## Risks / Rollback

Main risk:
- changing CLI/result shape in a way that breaks consuming repo wrappers

Mitigation:
- version and document the contract before broad integration
- keep repo-local labels out of shared code
- validate against Prime as the first real consumer

Rollback:
- preserve compatibility shim behavior temporarily at the CLI layer if the new contract
  breaks an existing consumer unexpectedly

## Recommended First Task

Start with `bd-520c4`.

Why first:
- the generic config/auth/bootstrap model is the foundation for mode split, Playwright
  hardening, and stable CLI design
- if this stays fuzzy, the rest of the epic will just encode product-specific drift
