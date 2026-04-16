## llm-common — Repo-Specific Context

### Repo-Memory Brownfield Maps

Before changing provider clients, agent primitives, retrieval, embeddings,
schemas, provenance, or shared verification helpers, read the maintained
repo-memory maps:

- `docs/architecture/README.md`
- `docs/architecture/BROWNFIELD_MAP.md`
- `docs/architecture/DATA_AND_STORAGE.md`
- `docs/architecture/WORKFLOWS_AND_PATTERNS.md`

These maps are the repo-owned source of truth for brownfield orientation.
Beads memory is a pointer/decision log, not proof.

### Shared Library Boundary

`llm-common` owns reusable contracts and primitives. Product-specific business
logic belongs in downstream repos unless there is an explicit promotion
decision.

### Tool Routing

For work in this repo:
- read repo-memory maps first for brownfield orientation when touching mapped areas
- use `llm-tldr` first for semantic discovery, exact trace work, call paths, slices, impact, and structural debugging
- use `serena` first for known-symbol refactors and insertions

If one of these is skipped on a qualifying task, the final response or handoff
must include `Tool routing exception: <reason>`.
