#!/usr/bin/env bash
# Convenience wrapper: apply SQL migrations idempotently.
# Uses the project-root check_and_apply_migrations.py script.
#
# Usage:
#   ./scripts/apply_migrations.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
exec python3 check_and_apply_migrations.py "$@"
