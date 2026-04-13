#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if ! command -v actionlint >/dev/null 2>&1; then
  cat <<'MSG'
ERROR: actionlint is required to validate .github/workflows YAML.

Install one of:
  brew install actionlint
  go install github.com/rhysd/actionlint/cmd/actionlint@latest

Then rerun:
  ./scripts/check-workflow-syntax.sh
MSG
  exit 2
fi

echo "Validating workflow syntax with actionlint..."
# This guard is for workflow syntax/load errors. Keep shellcheck style
# findings out of this gate to avoid blocking unrelated legacy scripts.
actionlint -color -ignore 'shellcheck reported issue'
echo "OK: workflow syntax validation passed"
