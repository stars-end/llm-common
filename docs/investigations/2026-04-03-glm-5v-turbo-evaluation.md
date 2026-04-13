# GLM-5V-Turbo Evaluation

- Date: 2026-04-03
- Repo: `stars-end/llm-common`
- Inspected SHA: `ce0f732a360758e9775c73dcbf24c1b369b00ddd`
- Affordabot context PR: `stars-end/affordabot#358`
- Primary question: should `glm-5v-turbo` be added or exposed as a premium multimodal lane in `llm-common`?

## Verdict

`RECOMMENDATION: experimental_only`

Current evidence does not justify default adoption or even a user-facing premium lane yet.

Why:
- `glm-5v-turbo` is officially documented and priced, but the documentation surface is inconsistent enough that adoption should stay cautious.
- The current account used for this investigation cannot call `glm-5v-turbo` on the coding endpoint at all (`1311`, HTTP 429: subscription plan does not include access).
- Actual `glm-4.6v` usage in `llm-common` and Affordabot is narrow. There is not yet a concrete production task here that clearly needs more multimodal reasoning than the current lane.
- The single bounded live POC did not produce a usable apples-to-apples quality comparison because `glm-5v-turbo` was access-gated before inference.

## Official Z.ai status

Primary sources:
- Pricing: [docs.z.ai/guides/overview/pricing](https://docs.z.ai/guides/overview/pricing)
- Chat completion API: [docs.z.ai/api-reference/llm/chat-completion](https://docs.z.ai/api-reference/llm/chat-completion)
- Model page: [docs.z.ai/guides/vlm/glm-5v-turbo](https://docs.z.ai/guides/vlm/glm-5v-turbo)
- GLM Coding Plan overview: [docs.z.ai/devpack/overview](https://docs.z.ai/devpack/overview)
- Baseline comparison model page: [docs.z.ai/guides/vlm/glm-4.6v](https://docs.z.ai/guides/vlm/glm-4.6v)

Confirmed:
- `glm-5v-turbo` has an official model page.
- Official pricing lists it at `$1.2 / 1M input tokens` and `$4.0 / 1M output tokens`.
- Official pricing lists `glm-4.6v` at `$0.3 / 1M input tokens` and `$0.9 / 1M output tokens`.
- Official model docs position `glm-5v-turbo` as a higher-end multimodal model with image, video, text, and file input, plus `200K` context and `128K` max output.
- The `glm-5v-turbo` quick-start examples use the general chat endpoint: `https://api.z.ai/api/paas/v4/chat/completions`.
- The general chat-completion reference page includes a vision-model section, but its visible model enum omits `glm-5v-turbo`. That is a documentation inconsistency, not clean API surfacing.

Important plan/access nuance:
- The GLM Coding Plan overview says all plans support vision understanding, but its supported-model list explicitly names text models and does not explicitly include `glm-5v-turbo`.
- The same page says API calls are billed separately and do not use Coding Plan quota.
- Inference from the docs plus the live call: `glm-5v-turbo` appears to be an API-billed premium multimodal model, not a generally available Coding Plan default.

## Price and latency tradeoff

### Pricing

Per official pricing:

| Model | Input / 1M | Output / 1M | Relative vs `glm-4.6v` |
|---|---:|---:|---:|
| `glm-4.6v` | $0.30 | $0.90 | 1.0x |
| `glm-5v-turbo` | $1.20 | $4.00 | 4.0x input, 4.4x output |

If token usage were similar, `glm-5v-turbo` is roughly a 4x cost lane.

### Latency

Official docs do not publish request latency targets for either model.

Live evidence from this investigation:
- `glm-4.6v` completed a coding-endpoint request in `9377 ms`.
- `glm-5v-turbo` returned a plan-gating error in `810 ms`, so no real inference latency could be measured.

Conclusion:
- Cost premium is real and documented.
- Actual latency premium remains unverified in this environment because the account cannot execute `glm-5v-turbo`.

## `llm-common` current `glm-4.6v` usage map

### Runtime paths

1. `llm_common/agents/ui_smoke_agent.py`
- Main multimodal lane.
- Hard-codes `model="glm-4.6v"` for the agentic screenshot + tool-calling loop.
- Falls back to `glm-4.5v` on some safety/provider errors.
- Uses `glm-4.5v` for final screenshot text extraction in `_verify_completion`.

2. `llm_common/verification/framework.py`
- Browser screenshot validation path.
- `_validate_with_glm()` hard-codes `model="glm-4.6v"` for screenshot checks.
- This is a real runtime use when a verification story has `requires_llm=True` and a screenshot is captured.

3. `llm_common/qa/agentic_verifier.py`
- Exported library surface with default model `openai/glm-4.6v`.
- I found no in-repo runtime caller. It is a callable surface, but not an actively exercised path inside this SHA.

### Runtime-adjacent but effectively config-only or legacy

1. `llm_common/providers/glm_models.py`
- `GLMConfig.default_model = "glm-4.6v"`.
- The active UISmoke path imports `GLMConfig` from `providers.zai_client`, not from this file.
- This looks like older standalone GLM client support rather than the main current runtime lane.

2. `llm_common/agents/glm_client.py`
- Older standalone vision client with default `glm-4.6v`.
- I found no active runtime import path using this file. Current runner imports `GLMVisionClient` from `llm_common.providers.zai_client`.

3. `llm_common/verification/stories/user_stories.py`
4. `llm_common/verification/stories/rag_stories.py`
- These contain several `llm_model="glm-4.6v"` declarations.
- In the current framework, `story.llm_model` is not threaded into `_validate_with_glm()`, which hard-codes `glm-4.6v`.
- These entries are intent/config metadata, not effective per-story routing.

### Docs / examples / tests only

- `docs/GLM_CLIENT.md`
- `examples/glm_browser_agent.py`
- `tests/test_glm_client.py`
- `docs/UI_SMOKE_AGENT.md`
- `docs/AGENT_CAPABILITIES.md`

### Net assessment for `llm-common`

Actual live-value `glm-4.6v` usage is concentrated in:
- UISmoke/browser screenshot reasoning
- verification-framework screenshot validation

It is not a broad default across the library.

## Affordabot current `glm-4.6v` usage map

### Narrow runtime / product-adjacent usage

1. `backend/services/substrate_promotion.py`
- Defines `GLM46VPromotionBoundary`.
- Intended only for ambiguous substrate-promotion cases after rules return `unclear`.
- Boundary defaults to `enabled=False`.
- Boundary also requires an injected transport. No production transport wiring was found in this PR context.

2. `backend/scripts/substrate/evaluate_promotion_candidates.py`
- Offline/backfill-style CLI path that instantiates `GLM46VPromotionBoundary`.
- LLM use is gated behind `--enable-llm` or `SUBSTRATE_PROMOTION_ENABLE_LLM=1`.
- This is not broad production rollout; it is a selective evaluation surface.

### Verification / manual QA usage

1. `backend/scripts/verification/capture_visual_proof.py`
- Uses `GLMVisionClient(GLMConfig(model="glm-4.6v"))`.

2. `backend/scripts/verification/admin_pipeline_agent.py`
- Uses `ZaiClient` with `default_model="glm-4.6v"` and feeds that into `UISmokeAgent`.

### Docs/spec-only usage

- `docs/specs/2026-04-03-data-substrate-framework-v1.md`
- `docs/specs/2026-04-02-glm-ocr-hard-doc-poc.md`

These docs are explicit that:
- the substrate framework is locked,
- `glm-4.6v` is only for ambiguous cases,
- `glm-ocr` remains the hard-document OCR fallback,
- no broad model swap is desired.

### Net assessment for Affordabot

There is no evidence here for broad `glm-4.6v` dependence across product runtime.

The real use is narrow:
- optional ambiguous-case substrate classification
- visual/admin verification tooling

That is exactly the kind of surface where a future premium multimodal experiment could live, but it does not justify defaulting a more expensive model today.

## What actually seems to need stronger multimodal reasoning?

The strongest candidates are:

1. UI-smoke or admin-dashboard screenshot reasoning
- Complex, dense screenshots with multiple panels, tables, charts, and subtle broken-state cues.
- This is the cleanest fit for a premium multimodal lane in `llm-common`.

2. Rich document-page understanding
- Not OCR replacement.
- Potentially useful for page-level understanding when a screenshot or rendered page combines tables, charts, and mixed layout semantics.
- Affordabot’s current locked substrate framework already chose `glm-ocr` for hard-doc extraction and `glm-4.6v` only for ambiguous classification, so this is not currently a substrate-framework reason to adopt `glm-5v-turbo`.

Tasks that do not currently justify `glm-5v-turbo` here:
- generic substrate promotion fallback
- OCR replacement
- broad default browser automation
- general llm-common defaults

## Quick POC

### Task

Single bounded UI-smoke-style comparison on one Affordabot admin screenshot:
- image: `artifacts-download/verification-report-20508988845/verify-20251225-190748/screenshots/rag_11_admin.png`
- prompt: classify whether the admin dashboard appears render-complete and summarize visible sections in JSON
- endpoint used: `https://api.z.ai/api/coding/paas/v4/chat/completions`

### Result

| Model | Result | Latency | Usage / Cost | Notes |
|---|---|---:|---|---|
| `glm-4.6v` | Request succeeded | `9377 ms` | `1415` prompt + `180` completion = `1595` total tokens. Estimated cost: about `$0.00059` using official pricing. | Returned `finish_reason="length"` and empty final content because the response budget was consumed by reasoning tokens. |
| `glm-5v-turbo` | Request rejected | `810 ms` | No inference cost observed | HTTP `429`, code `1311`: current subscription plan does not include access to `GLM-5V-Turbo`. |

### Product interpretation

- This was enough to verify that `glm-5v-turbo` is not currently usable in this environment for the existing coding-endpoint integration style.
- It did **not** produce a quality comparison, so there is no evidence here that the new model materially improves Affordabot’s current screenshot-verification tasks.
- The live blocker is operational and commercial, not theoretical: access is not available on the current plan.

## Adoption recommendation

### Recommended policy

Keep `glm-5v-turbo` out of defaults.

If exposed at all, expose it only as a hidden experiment for premium multimodal QA work:
- not for substrate framework rollout,
- not for global `GLMModels.VISION`,
- not for broad automatic use in UISmoke,
- not for OCR.

### Why not `premium_lane` yet

I am not recommending `premium_lane` yet because at least one of these must be true first:
- the target account can actually invoke the model,
- we have a successful side-by-side quality win on a real task,
- there is a specific product owner willing to pay the 4x-ish token premium for that task.

None of those are demonstrated here.

### Explicit Affordabot relevance

For Affordabot specifically:
- `glm-5v-turbo` is **not** justified for the locked substrate framework.
- `glm-5v-turbo` is **not** justified as a replacement for `glm-ocr`.
- The only plausible near-term use is manual or opt-in premium visual QA on complex admin screenshots if access is enabled later.

## Lowest-regret integration points if access improves later

If a future wave wants to expose this safely, the lowest-regret sequence is:

1. Add a named constant only
- Add `GLMModels` constant for `glm-5v-turbo`.
- Update `ZaiClient.PRICING` with official pricing.

2. Thread an explicit opt-in vision-model override through the real multimodal surfaces
- `llm_common/agents/ui_smoke_agent.py`
- `llm_common/verification/framework.py`

3. Keep the default on `glm-4.6v`
- Only allow `glm-5v-turbo` via an explicit override or experimental flag.

4. Do not start with these surfaces
- `llm_common/agents/glm_client.py` legacy standalone client
- `llm_common/qa/agentic_verifier.py` until it has a real caller
- Affordabot substrate promotion boundary

## Final answer

`glm-5v-turbo` is worth tracking, but not worth exposing broadly in `llm-common` today.

Best current position:
- document it internally as a future experiment,
- keep `glm-4.6v` as the active multimodal lane,
- revisit only after account access exists and one real screenshot-heavy QA task shows a clear win.
