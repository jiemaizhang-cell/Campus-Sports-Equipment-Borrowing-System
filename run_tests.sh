#!/usr/bin/env bash
set -euo pipefail

mkdir -p evidence
stamp="$(date -u +%Y-%m-%d_%H-%M-%S)"
log="evidence/pytest_${stamp}.txt"
xml="evidence/pytest_${stamp}.xml"

PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi

{
  echo "Execution date (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Python version: $("$PYTHON_BIN" --version 2>&1)"
  echo "Git branch: $(git rev-parse --abbrev-ref HEAD 2>&1 || true)"
  echo "Git commit: $(git rev-parse HEAD 2>&1 || true)"
  echo "Running tests:"
} | tee "$log"

set +e
"$PYTHON_BIN" -m pytest -v "--junitxml=$xml" 2>&1 | tee -a "$log"
exit_code=${PIPESTATUS[0]}
set -e

echo "pytest exit code: $exit_code" | tee -a "$log"
echo "Evidence log: $log"
exit "$exit_code"
