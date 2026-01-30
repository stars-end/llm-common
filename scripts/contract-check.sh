#!/bin/bash
# contract-check.sh — Verifies Makefile compliance with MAKE_CONTRACT.md
set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
MAKEFILE="$REPO_ROOT/Makefile"

echo "🔍 Checking Makefile contract in $REPO_ROOT..."

if [ ! -f "$MAKEFILE" ]; then
    echo "❌ Error: Makefile not found at $MAKEFILE"
    exit 1
fi

REQUIRED_TARGETS=("verify-gate" "verify-nightly")
MISSING=0

for target in "${REQUIRED_TARGETS[@]}"; do
    if ! grep -q "^$target:" "$MAKEFILE"; then
        echo "❌ Missing mandatory target: $target"
        MISSING=1
    else
        echo "✅ Found target: $target"
    fi
done

if [ $MISSING -eq 1 ]; then
    echo "🛑 Makefile Contract Violation detected."
    exit 1
fi

echo "✨ Makefile Contract satisfied."
exit 0
