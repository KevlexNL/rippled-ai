#!/usr/bin/env bash
# Pre-push safety check: runs integration tests and blocks the push if they fail.
# Install: cp scripts/pre-push-check.sh .git/hooks/pre-push && chmod +x .git/hooks/pre-push

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "==> Running integration tests before push..."

if [ ! -f ".venv/bin/pytest" ]; then
    echo "ERROR: .venv not found. Run 'pip install -r requirements.txt' in a venv first."
    exit 1
fi

if .venv/bin/pytest tests/integration/ -v --tb=short; then
    echo "==> Integration tests passed. Proceeding with push."
    exit 0
else
    echo ""
    echo "==> Integration tests FAILED. Push blocked."
    echo "    Fix the failures above before pushing."
    echo "    To bypass (emergencies only): git push --no-verify"
    exit 1
fi
