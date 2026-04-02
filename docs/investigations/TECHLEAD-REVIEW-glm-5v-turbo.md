# Tech Lead Review: GLM-5V-Turbo

- MODE: investigation
- BEADS_EPIC: `bd-z8qp`
- BEADS_SUBTASK: `bd-z8qp.4`
- BEADS_DEPENDENCIES: `none`
- Investigation Doc: `docs/investigations/2026-04-03-glm-5v-turbo-evaluation.md`

## Recommendation

`RECOMMENDATION: experimental_only`

## Why

- Official docs confirm `glm-5v-turbo` exists and is priced as a premium multimodal model.
- It is materially more expensive than `glm-4.6v`.
- The current investigation account cannot call it on the coding endpoint due plan gating.
- Actual `glm-4.6v` usage in both repos is narrow and concentrated in screenshot verification, not broad product runtime.
- No concrete Affordabot production task here currently justifies a 4x-ish multimodal upgrade.

## Review focus

1. Confirm that `experimental_only` is the right bar given current plan access and narrow real usage.
2. Confirm that any future exposure should start in UISmoke / verification only, not substrate promotion.
3. Confirm whether a follow-up wave should buy/enable access and run a real screenshot-heavy A/B before any code exposure.
