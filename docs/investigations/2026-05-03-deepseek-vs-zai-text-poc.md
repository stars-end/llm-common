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

`RECOMMENDATION: experimental_only`

### Why

- `deepseek-v4-flash` has now succeeded on:
  - one Prime-style single case
  - one Affordabot-style single fixture
  - three Prime matrix cases
  - three Affordabot matrix fixtures
- The remaining uncertainty is not basic viability. It is baseline comparison quality and production policy.

### Suggested policy

- Prime Advisor:
  - add `deepseek-v4-flash` as an experimental text lane candidate
  - keep `deepseek-v4-pro` reserved for harder cases or later evaluation
- Affordabot:
  - add `deepseek-v4-flash` as an experimental analysis lane candidate behind an explicit flag
  - keep critique/review turned on
- Z.ai:
  - do not remove current Z.ai wiring until we complete one clean fresh baseline rerun with working access

## Next Step

The next highest-signal step is one clean baseline wave:

1. restore a usable Z.ai package/account state
2. rerun the same Prime and Affordabot fixtures unchanged
3. compare `glm-4.7` vs `deepseek-v4-flash` directly on:
   - latency
   - token use
   - tool-loop stability
   - first-pass JSON validity
   - final schema validity
   - review pass rate

If Z.ai remains unavailable, the practical decision can still move forward as:

- keep current Z.ai production wiring unchanged
- expose `deepseek-v4-flash` as an opt-in experimental lane for text-only use cases
