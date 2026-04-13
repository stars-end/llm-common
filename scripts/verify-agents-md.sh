#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ ! -f AGENTS.md ]]; then
  echo "ERROR: AGENTS.md not found at repo root."
  exit 1
fi

tmp_original="$(mktemp)"
trap 'rm -f "$tmp_original"' EXIT
cp AGENTS.md "$tmp_original"

./scripts/agents-md-compile.zsh

if [[ -n "$(tail -c1 AGENTS.md 2>/dev/null)" ]]; then
  echo "ERROR: AGENTS.md must end with a trailing newline."
  echo "Fix command:"
  echo "  make regenerate-agents-md"
  exit 1
fi

if cmp -s AGENTS.md "$tmp_original"; then
  echo "OK: AGENTS.md is up to date"
  exit 0
fi

echo "ERROR: AGENTS.md is stale or was edited directly."
echo "Fix command:"
echo "  make regenerate-agents-md"
echo
echo "Diff:"
diff -u "$tmp_original" AGENTS.md || true
exit 1
