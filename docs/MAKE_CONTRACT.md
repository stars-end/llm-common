# Makefile Contract v1

This contract defines the mandatory `make` targets for application repositories using the `uismoke` runner. Adherence ensures consistent CI/CD behavior and DX across the ecosystem.

## Required Targets

| Target | Description | Expected Flags |
| :--- | :--- | :--- |
| `verify-gate` | P0 Quality Gate. Must be fast and deterministic. | `--deterministic-only` |
| `verify-nightly` | Full regression suite. Allows LLM vision flakiness. | None (full suite) |

## Implementation Guidance

### verify-gate
This target should target a stable subset of stories.
- **Prime**: Uses `--only-stories` to pin precisely 3 critical flows.
- **Affordabot**: Uses `--exclude-stories` to skip environment-specific blockers (e.g. real Clerk).

### verify-nightly
This target runs the complete set of stories found in `docs/TESTING/STORIES/`.

## Enforcement
The `contract-check` script in `llm-common` verifies that these targets exist in the `Makefile` and are documented in `make help`.
