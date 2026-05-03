# DeepSeek vs Z.ai Text POC

Date: 2026-05-03

## Scope

This note packages the follow-up POC for the two direct text use cases:

- Prime Advisor agent in `prime-radiant-ai`
- Affordabot economics analysis in `affordabot`

`llm-common` is used as the reporting/harness repo only. UISmoke is excluded because DeepSeek V4 is not a vision model.

## Runtime Seams

- Prime Advisor: direct tool loop in `DirectAdvisorAgent.run(...)`, grounded in the prompt/tool contract from `backend/agents/direct_advisor.py`
- Affordabot: generation/review JSON contract in `AnalysisPipeline`, grounded in `backend/services/llm/orchestrator.py` and `backend/schemas/analysis.py`

## What We Ran

### 1. Clean Z.ai baseline reruns

- Prime Advisor baseline rerun on `glm-4.7`
- Affordabot baseline rerun on `glm-4.7`

### 2. DeepSeek flash matrix

- Prime Advisor: 3 flash cases on the native DeepSeek API
- Affordabot: 3 flash fixtures on the native DeepSeek API

### 3. Prior single-case context reused for comparison

Earlier in this thread, we also ran one smaller direct POC:

- Prime Advisor style single case:
  - `deepseek-v4-flash`: success
  - `deepseek-v4-pro`: success
  - `glm-4.7`: blocked by Z.ai package/balance
- Affordabot style single fixture:
  - `deepseek-v4-flash`: success
  - `deepseek-v4-pro`: success
  - `glm-4.7`: timeout

That earlier single-case evidence is useful for `flash` vs `pro`, while the follow-up matrix below is the best current signal for `flash` viability on our direct product tasks.

## Result Artifacts

- Prime single-case artifact: `/tmp/deepseek_zai_poc/prime/result.json`
- Affordabot single-case artifact: `/tmp/deepseek_zai_poc/affordabot/result.json`
- Prime flash matrix artifact: `/tmp/deepseek_zai_poc_v2/prime/result.json`
- Affordabot flash matrix artifact: `/tmp/deepseek_zai_poc_v2/affordabot/result_direct.json`

## Results

### Z.ai baseline reruns

Prime Advisor:

- `glm-4.7` failed immediately with HTTP `429` / code `1113`
- observed blocker: insufficient balance or no available resource package

Affordabot:

- `glm-4.7` failed at generate with HTTP `429`
- even before content validation, the baseline lane was unavailable

Conclusion:

- We still do not have a clean apples-to-apples Z.ai baseline rerun for this follow-up wave.
- This is an access/runtime blocker, not yet a model-quality conclusion.

### DeepSeek V4 Flash matrix

#### Prime Advisor

All 3 direct tool-use cases succeeded once DeepSeek thinking was explicitly disabled.

Case summary:

- case 1: success, `10332 ms`, `3249` total tokens, `5` tool calls
- case 2: success, `13106 ms`, `3442` total tokens, `9` tool calls
- case 3: success, `7306 ms`, `1823` total tokens, `3` tool calls

Behavior summary:

- The model handled the direct tool loop cleanly.
- It produced usable final answers in all three cases.
- The one important integration gotcha is that default DeepSeek thinking mode is a bad fit for this naive tool loop unless `reasoning_content` is replayed; disabling thinking removed that blocker.

#### Affordabot

All 3 direct DeepSeek flash fixtures succeeded on the native DeepSeek API using the real generate/review JSON contract.

Fixture summary:

- fixture 1: success, generate `22226 ms`, review `2996 ms`, review passed
- fixture 2: success, generate `15610 ms`, review `5511 ms`, review did not pass
- fixture 3: success, generate `11493 ms`, review `2448 ms`, review passed

Validation summary:

- first-pass JSON valid: `3/3`
- final schema valid: `3/3`
- review passed: `2/3`

Behavior summary:

- Flash stayed inside the JSON contract across all three fixtures.
- It behaved conservatively on the insufficient-evidence rebate fixture.
- The rental-inspection-fee fixture exposed a useful weakness: the review pass flagged that the analysis was too comfortable with qualitative pass-through assumptions while still treating the evidence as sufficient.

### DeepSeek V4 Pro single-case evidence

We do not yet have a full `pro` matrix, but we do have one earlier direct fixture comparison:

- Prime Advisor single case: `deepseek-v4-pro` succeeded
- Affordabot single fixture: `deepseek-v4-pro` succeeded with valid JSON/schema, but was much slower than `flash`

Notable Affordabot single-fixture timings from the earlier run:

- generate: about `138.7s`
- review: about `38.7s`

Conclusion:

- `pro` is viable.
- `pro` currently looks like a challenger for harder cases, not the default candidate for these lanes.

## Interpretation

### What is now clear

- `deepseek-v4-flash` is operationally viable for both direct text use cases.
- Prime Advisor is the strongest current fit because the flash lane completed a real tool-using matrix successfully.
- Affordabot also looks viable, but should keep its self-review or equivalent critique step because one of the three fixtures still needed stronger conservatism.

### What is still unresolved

- We do not yet have a fair fresh baseline comparison against Z.ai because the Z.ai lane was blocked by account/package/rate-limit conditions during this wave.
- Because of that, we can say:
  - DeepSeek flash works
  - DeepSeek pro works
  - but not yet that either one definitively beats the current Z.ai baseline head-to-head

## Recommendation

### Current recommendation

`RECOMMENDATION: proceed_to_phase_1_with_mandatory_phase_1_5_gate`

### Why

- `deepseek-v4-flash` has now succeeded on:
  - one Prime-style single case
  - one Affordabot-style single fixture
  - three Prime matrix cases
  - three Affordabot matrix fixtures
- The remaining uncertainty is no longer basic viability. It is traffic-like stability, JSON/tool-call behavior under real product loops, and production policy.
- Z.ai baseline access remains blocked, so this report should not claim a clean head-to-head win. It does provide enough evidence to start the lowest-risk shared text-lane cutover.

### Migration policy

The migration should proceed in phases:

1. Phase 1: cut over the main proven config-driven/OpenRouter-backed text lanes to `deepseek-v4-flash` with minimal behavior change.
2. Phase 1.5: mandatory validation gate on traffic-like Prime Advisor and Affordabot text behaviors before touching harder Z.ai-shaped runtime paths.
3. Phase 2: migrate remaining direct/Z.ai-shaped text runtime surfaces that require adaptation.
4. Phase 3: cleanup runtime env names, stale docs, active defaults, and operator health checks.

Z.ai should remain available for vision and for any explicitly retained fallback path until the product migration proves otherwise. It should not remain the default production text lane once Phase 1 and Phase 1.5 pass.

## Ownership Boundary

Split the migration by ownership boundary, not by provider:

- `llm-common` owns shared DeepSeek text provider/client behavior, default model-selection contracts, JSON/tool-loop expectations, cost/error/env handling, and the shared "text = DeepSeek Flash, vision = Z.ai" boundary.
- `prime-radiant-ai` owns Prime Advisor product integration, advisor loop validation, portfolio/advisor runtime behavior, and Prime admin/diagnostic behavior.
- `affordabot` owns economics-analysis integration, JSON/review fixtures, product-specific fallback decisions, Windmill bridge/product runtime paths, and Affordabot health behavior.

Do not split a single runtime path across multiple agents in the same phase. Shared abstractions should land in `llm-common` first; product repos should consume them rather than inventing local provider abstractions.

## Next Step

The next highest-signal implementation sequence is:

### Phase 1

Objective: cut over the main proven text lane to DeepSeek Flash with minimal behavior change.

Initial scope:

- `llm-common`: shared text-default/model-selection surfaces such as orchestrator, understanding, reflection, and tool-selection lanes.
- `prime-radiant-ai`: config-driven/OpenRouter-backed text paths such as LLM config and portfolio analyzer surfaces.
- `affordabot`: model-default wiring in the application entry/runtime config, without touching search, direct bridge, or vision paths.

Validation:

- structured JSON still validates
- fallback behavior still works
- metrics/cost tracking records DeepSeek Flash correctly
- core text smoke tests run without requiring Z.ai text access

Exit:

- in-scope text defaults point to `deepseek-v4-flash`
- no vision/search/direct-bridge behavior is changed

### Phase 1.5

Objective: validate DeepSeek Flash on traffic-like text behavior before touching harder runtime paths.

This gate is mandatory.

Validation:

- rerun real-ish Prime Advisor tool loops
- rerun real-ish Affordabot JSON/review loops
- verify tool-call stability
- verify JSON first-pass and final-pass rates
- verify latency is acceptable for small orchestration calls
- verify review/critique behavior remains conservative enough
- verify fallback behavior and cost/metrics tracking

Exit:

- Phase 2 may start only if the traffic-like loops pass or produce bounded, understood fixes in `llm-common`.

### Phase 2

Objective: migrate remaining Z.ai-shaped text runtime surfaces that need adaptation.

Initial scope:

- Prime direct advisor and related agent paths, including direct advisor, portfolio advisor, PydanticAI runtime, and admin/diagnostic LLM endpoints.
- Affordabot core pipeline/provider wiring, direct bridge/discovery text paths, and Windmill bridge integration where text provider assumptions are still Z.ai-shaped.

Out of scope:

- vision paths
- broad search-provider changes
- cleanup-only docs churn

Validation:

- text runtime paths work without `ZAI_API_KEY`
- retries/failure taxonomy remain accurate
- health/diagnostic endpoints reflect the new text-provider truth

Exit:

- no direct production text runtime depends on Z.ai transport
- Z.ai remains only for vision or explicitly retained non-text fallback behavior

### Phase 3

Objective: cleanup and convergence after runtime cutover works.

Scope:

- env/runtime config naming cleanup
- stale active runtime references to Z.ai text defaults
- operator docs and health-check alignment
- dead legacy branches in active runtime code

Validation:

- docs and runtime env match reality
- no stale active default-text references remain
- operator health checks state: text defaults use DeepSeek Flash; vision remains Z.ai

Exit:

- one coherent runtime contract across `llm-common`, `prime-radiant-ai`, and `affordabot`
