#!/usr/bin/env bash
# Validate GitHub Actions workflow files for syntax and structural correctness.
set -euo pipefail

WORKFLOWS_DIR=".github/workflows"
ERRORS=0

if [ ! -d "$WORKFLOWS_DIR" ]; then
  echo "ERROR: $WORKFLOWS_DIR directory not found"
  exit 1
fi

echo "Validating GitHub Actions workflows in $WORKFLOWS_DIR..."

for file in "$WORKFLOWS_DIR"/*.yml "$WORKFLOWS_DIR"/*.yaml; do
  [ -f "$file" ] || continue
  name=$(basename "$file")

  # Check YAML syntax
  if ! python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
    echo "FAIL: $name — invalid YAML syntax"
    ERRORS=$((ERRORS + 1))
    continue
  fi

  # Check required top-level keys
  has_on=$(python3 -c "
import yaml, sys
with open('$file') as f:
    d = yaml.safe_load(f)
if not isinstance(d, dict):
    sys.exit(1)
if 'on' not in d and True not in d:
    sys.exit(1)
" 2>/dev/null && echo "yes" || echo "no")

  has_jobs=$(python3 -c "
import yaml, sys
with open('$file') as f:
    d = yaml.safe_load(f)
if not isinstance(d, dict) or 'jobs' not in d:
    sys.exit(1)
" 2>/dev/null && echo "yes" || echo "no")

  if [ "$has_on" = "no" ]; then
    echo "FAIL: $name — missing 'on' trigger"
    ERRORS=$((ERRORS + 1))
  fi

  if [ "$has_jobs" = "no" ]; then
    echo "FAIL: $name — missing 'jobs' section"
    ERRORS=$((ERRORS + 1))
  fi

  if [ "$has_on" = "yes" ] && [ "$has_jobs" = "yes" ]; then
    echo "OK:   $name"
  fi
done

echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "$ERRORS workflow(s) have errors."
  exit 1
else
  echo "All workflows are valid."
fi
