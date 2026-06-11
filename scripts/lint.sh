#!/bin/bash
set -euo pipefail

echo "Linting all code..."
echo ""

HAD_ERRORS=0

echo "--- Backend Ruff ---"
cd "$(dirname "$0")/../backend"
if command -v ruff &> /dev/null; then
  ruff check . || HAD_ERRORS=1
else
  echo "ruff not found. Install with: pip install ruff"
  HAD_ERRORS=1
fi

echo ""
echo "--- Backend MyPy ---"
if command -v mypy &> /dev/null; then
  mypy core/ --ignore-missing-imports || HAD_ERRORS=1
else
  echo "mypy not found. Skipping."
fi

echo ""
echo "--- Frontend Lint ---"
cd "$(dirname "$0")/../frontend"
npm run lint || HAD_ERRORS=1

echo ""
echo "--- Frontend Type Check ---"
npm run typecheck || HAD_ERRORS=1

echo ""
if [ $HAD_ERRORS -eq 0 ]; then
  echo "All lint checks passed! ✅"
  exit 0
else
  echo "Some lint checks failed! ❌"
  exit 1
fi
