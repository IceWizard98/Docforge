#!/bin/bash
set -euo pipefail

echo "Running all tests..."
echo ""

echo "--- Backend Tests ---"
cd "$(dirname "$0")/../backend"
if [ -d "venv" ]; then
  source venv/bin/activate
fi
python -m pytest tests/ -v --cov=core --cov-report=term
BACKEND_EXIT=$?
if [ -d "venv" ]; then
  deactivate 2>/dev/null || true
fi

echo ""
echo "--- Frontend Tests ---"
cd "$(dirname "$0")/../frontend"
npm test
FRONTEND_EXIT=$?

echo ""
if [ $BACKEND_EXIT -eq 0 ] && [ $FRONTEND_EXIT -eq 0 ]; then
  echo "All tests passed! ✅"
  exit 0
else
  echo "Some tests failed! ❌"
  echo "  Backend exit code: $BACKEND_EXIT"
  echo "  Frontend exit code: $FRONTEND_EXIT"
  exit 1
fi
