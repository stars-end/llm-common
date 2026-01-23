# Agent Handoff: UISmoke Fixes Review

You are taking over the UISmoke Agent fixes work. A previous agent has completed code changes and documented everything. Your role is to review, validate, and complete remaining work.

## Context

**Problem**: UISmoke Agent harness was completely broken, blocking all automated QA for Prime Radiant.

**Root Causes** (7 issues fixed):
1. `extra_body` parameter conflict in ZaiClient
2. Missing `close()` method on GLMVisionClient
3. JSON serialization failure for Pydantic models
4. String steps rejected by AgentStory validation
5. Legacy `goals` format not supported
6. `load_story` function not exported
7. Missing `get_content()` method on browser adapter

**Commits Delivered**:
- `llm-common@f7f415e` - Fixed extra_body conflict, added close(), normalized story loading
- `llm-common@1c74d95` - Added comprehensive review documentation
- `prime-radiant-ai@c8c27a7` - Added get_content() to browser adapter (awaiting PR)

**Documentation**: Full technical review at `docs/UISMOKE_FIXES_REVIEW.md`

---

## Your Tasks

### Priority 0: Verify Fixes Work

1. **Read the full review document**:
   ```bash
   cat ~/llm-common/docs/UISMOKE_FIXES_REVIEW.md
   ```

2. **Run smoke test validation**:
   ```bash
   cd ~/prime-radiant-ai
   export ZAI_API_KEY="<your-key>"
   export PRIME_SMOKE_BASE_URL="https://frontend-dev-f8a3.up.railway.app"
   python scripts/e2e_agent/run_prime_smoke.py --story docs/TESTING/STORIES/dashboard_smoke.yml
   ```

3. **Verify no errors occur**:
   - No `extra_body` conflict
   - No `close()` attribute error
   - No JSON serialization failure
   - No validation errors for string steps

4. **Close epic if successful**:
   ```bash
   cd ~/llm-common
   bd close llm-common-grd
   ```

### Priority 1: Complete Follow-Up Work

**Epic**: `llm-common-1pf` - Story format inconsistency

Decision needed: Should we standardize on Pydantic schemas (schemas.py) and deprecate dataclass models (models.py)?

If yes:
1. Update `prime-radiant-ai/scripts/e2e_agent/run_prime_smoke.py`:
   - Change `from llm_common.agents.models import` → `from llm_common.agents.schemas import`
   - Replace `dataclass_to_dict(report)` → `report.to_json_dict()`
2. Add `# DEPRECATED` comments to `llm_common/agents/models.py`
3. Test smoke runner again

**Epic**: `bd-xe6` (prime-radiant-ai) - Migrate stories from goals to steps

Convert stories from legacy format:
```yaml
# BEFORE
goals:
  - "Navigate to page"

# AFTER
steps:
  - id: step-1
    description: "Navigate to page"
    validation_criteria: ["expected-text"]
```

Stories to convert:
- advisor_qa.yml
- advisor_rag.yml
- dashboard_smoke.yml
- (11 more - see full list in review doc)

---

## Quick Reference

| Repo | Key Files | Beads Epic |
|------|-----------|------------|
| llm-common | `providers/zai_client.py`, `agents/schemas.py`, `agents/utils.py` | `llm-common-grd` (P0), `llm-common-1pf` (P1) |
| prime-radiant-ai | `scripts/e2e_agent/run_prime_smoke.py`, `docs/TESTING/STORIES/*.yml` | `bd-xe6` (P1) |

---

## Status

- [x] Code changes committed and pushed
- [x] Documentation written and pushed
- [ ] Smoke test validation **(YOUR JOB)**
- [ ] Epic llm-common-grd closure
- [ ] Epic llm-common-1pf completion
- [ ] Epic bd-xe6 completion

---

## If You Find Issues

1. Log new issue: `bd create --type bug --priority P0 --title "Describe issue"`
2. Revert if critical: `git revert f7f415e`
3. Contact previous agent with details from `docs/UISMOKE_FIXES_REVIEW.md`

---

**Start here**: Read `~/llm-common/docs/UISMOKE_FIXES_REVIEW.md` completely, then run the smoke test validation command above.
