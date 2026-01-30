# QA Contract (v1) - Runner + Artifact + Exit

This contract defines the standardized behavior for any QA runner (like `uismoke`) to ensure consistent automation and triage.

## Exit Codes
- `0`: Success (All stories passed according to policy).
- `1`: Product Regression (At least one reproducible failure classified as BAD_PRODUCT).
- `2`: Harness/Env Failure (Known infrastructure, navigation, or auth issues).
- `3`: Flaky/Unstable (Inconsistent results, likely timing issues).
- `4`: Suite Timeout / Capacity (Max suite duration reached).
- `127`: Unexpected Crash.

## run.json Schema
The `run.json` artifact MUST contain:
- `run_id`: Unique identifier (UUID).
- `timestamp`: ISO-8601 suite start time.
- `base_url`: Target URL tested.
- `environment`: (dev, staging, pr-N).
- `stats`: `{pass: int, fail: int, total: int, categories: {BAD_PRODUCT: int, ...}}`.
- `story_results`: Array of results.

## Story Result Schema
```json
{
  "story_id": "string",
  "status": "pass | fail | skip",
  "classification": "reproducible_fail | flaky_recovered | auth_failed | ...",
  "attempts": [
    {
      "attempt_n": 1,
      "status": "fail",
      "errors": [...],
      "evidence_dir": "path/to/evidence"
    }
  ]
}
```

## Artifact Layout
```
artifacts/verification/<run_id>/
├── run.json
├── run.md (Human readable summary)
├── beads_plan.json (Generated during triage)
└── stories/
    └── <story_id>/
        ├── attempts/
        │   └── 1/
        │       ├── screenshot.png
        │       ├── console.log
        │       └── dom.html
        └── forensics.json
```
