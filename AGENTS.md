# AGENTS.md — LLM Common V3 DX

**Start Here**
1. **Initialize**: `source ~/.bashrc && dx-check || curl -fsSL https://raw.githubusercontent.com/stars-end/agent-skills/master/scripts/dx-hydrate.sh | bash`
2. **Check Environment**: `dx-check` checks git, Beads, and Skills.

**Core Tools**:
- **Beads**: Issue tracking. Use `bd` CLI.
- **Skills**: Automated workflows (`start-feature`, `sync-feature`, `finish-feature`).

**Daily Workflow**:
1. `start-feature bd-xxx` - Start work.
2. Code...
3. `sync-feature "message"` - Save work (runs ci-lite).
4. `finish-feature` - Verify & PR.

---

**Repo Context: Shared Library**
- **Purpose**: Core LLM abstractions and providers for Affordabot and Prime Radiant.
- **Rules**:
  - NO business logic. Only generic AI tools.
  - `make ci-lite` enforces strict typing (mypy) and linting (ruff).
  - Changes here affect downstream apps. Test carefully.


## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
