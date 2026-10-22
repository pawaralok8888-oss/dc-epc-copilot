#!/usr/bin/env bash
# Day 6 "Done when" check: a fresh git clone follows the README and runs
# from cached results, with NO .env file and NO API key.
#
# Usage (from anywhere):
#   bash tests/clean_clone_check.sh git@github.com:YOUR-USERNAME/dc-epc-copilot.git
#   bash tests/clean_clone_check.sh git@github.com:YOUR-USERNAME/dc-epc-copilot.git feature/graph
#
# Tip: push your branch first, because this clones from GitHub, not your folder.

set -euo pipefail

REPO_URL="${1:?Usage: clean_clone_check.sh <repo-url> [branch]}"
BRANCH="${2:-main}"
WORKDIR="$(mktemp -d)"
PORT=8599
pass() { echo "  PASS  $1"; }
fail() { echo "  FAIL  $1"; exit 1; }

echo "Working in $WORKDIR"
cd "$WORKDIR"

echo "[1/5] Fresh clone ($BRANCH)"
git clone --quiet --branch "$BRANCH" "$REPO_URL" repo || fail "git clone"
cd repo
pass "cloned"

echo "[2/5] Required files exist"
for f in README.md requirements.txt app.py .env.example docs/schema.md \
         data/cache/requirements.json data/cache/tests.json; do
  [ -e "$f" ] && pass "$f" || fail "$f is missing (is data/cache committed?)"
done
[ -e .env ] && fail ".env is in the repo (a key may have leaked!)" || pass "no .env committed"

echo "[3/5] Install exactly as the README says"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet -r requirements.txt || fail "pip install"
pass "pip install"

echo "[4/5] pytest, with the API key removed"
unset ANTHROPIC_API_KEY
python -m pytest -q || fail "pytest"
pass "pytest"

echo "[5/5] Streamlit starts and answers"
streamlit run app.py --server.headless true --server.port "$PORT" >streamlit.log 2>&1 &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null || true' EXIT
ok=0
for _ in $(seq 1 30); do
  if curl -sf "http://localhost:$PORT/_stcore/health" >/dev/null; then ok=1; break; fi
  sleep 1
done
[ "$ok" = 1 ] && pass "app is healthy on port $PORT" || { cat streamlit.log; fail "app did not start"; }

echo
echo "ALL CHECKS PASSED: a fresh clone runs from cached results."
echo "Now open the app once by hand and click through the demo flow."
