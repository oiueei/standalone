#!/usr/bin/env bash
# Scoped mutation testing: mutate ONLY the Python files changed since a base
# ref, so the run finishes in minutes and actually gets used. Surviving
# mutants = assertions too permissive (smells #7/#8 in checklist.md).
#
# Usage (from the repo root):
#   .claude/skills/solid-testing/scripts/mutation_test.sh              # since @{push}/origin
#   .claude/skills/solid-testing/scripts/mutation_test.sh v0.10.0      # since a ref
#
# JS note: for the frontend the equivalent is Stryker (npx stryker run) with
# `mutate` scoped the same way in stryker.config.json — heavier to set up, so
# start with the backend; the cheap manual variant for BOTH stacks is:
# re-introduce the bug / flip the condition and watch the test fail.
set -euo pipefail

BASE="${1:-}"
if [ -z "$BASE" ]; then
  BASE=$(git rev-parse --abbrev-ref --symbolic-full-name '@{push}' 2>/dev/null) \
    || BASE="origin/$(git rev-parse --abbrev-ref HEAD)"
fi

if ! command -v mutmut >/dev/null 2>&1; then
  echo "mutmut is not installed. It is a dev-only tool — install it ad hoc:"
  echo "    pip install mutmut"
  exit 1
fi

CHANGED=$(git diff --name-only "$BASE"...HEAD -- 'core/*.py' \
  | grep -v -e '/tests/' -e '/migrations/' || true)

if [ -z "$CHANGED" ]; then
  echo "No changed backend source files since $BASE — nothing to mutate."
  exit 0
fi

echo "Mutating files changed since $BASE:"
echo "$CHANGED" | sed 's/^/  - /'

PATHS=$(echo "$CHANGED" | paste -sd, -)

# mutmut caches in .mutmut-cache; a fresh run per scope keeps results honest.
rm -rf .mutmut-cache
mutmut run --paths-to-mutate "$PATHS" --tests-dir core/tests \
  --runner "python -m pytest -x -q core/tests" || true

echo
echo "== Surviving mutants (each one is a test that lied) =="
mutmut results
echo
echo "Inspect one with: mutmut show <id>   — then strengthen the assertion"
echo "that should have killed it, and re-run this script."
