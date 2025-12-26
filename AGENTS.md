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

