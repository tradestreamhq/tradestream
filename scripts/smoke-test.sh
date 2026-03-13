#!/usr/bin/env bash
# Smoke test for TradeStream Docker Compose stack.
# Usage: ./scripts/smoke-test.sh
# Exits 0 on success, 1 on failure.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
FAILURES=0

pass() { echo -e "${GREEN}PASS${NC}: $1"; }
fail() { echo -e "${RED}FAIL${NC}: $1"; FAILURES=$((FAILURES + 1)); }

echo "=== TradeStream Smoke Test ==="
echo ""

# 1. Check all containers are running
echo "--- Container Health ---"
for svc in tradestream-app tradestream-postgres tradestream-redis; do
  if docker inspect --format='{{.State.Running}}' "$svc" 2>/dev/null | grep -q true; then
    pass "$svc is running"
  else
    fail "$svc is not running"
  fi
done

# 2. PostgreSQL accepts connections
echo ""
echo "--- PostgreSQL ---"
if docker exec tradestream-postgres pg_isready -U "${POSTGRES_USER:-tradestream}" -d "${POSTGRES_DB:-tradestream}" >/dev/null 2>&1; then
  pass "PostgreSQL is accepting connections"
else
  fail "PostgreSQL is not accepting connections"
fi

# 3. Redis responds to PING
echo ""
echo "--- Redis ---"
if docker exec tradestream-redis redis-cli -a "${REDIS_PASSWORD:-changeme}" ping 2>/dev/null | grep -q PONG; then
  pass "Redis responds to PING"
else
  fail "Redis does not respond to PING"
fi

# 4. App health endpoint
echo ""
echo "--- Application ---"
APP_PORT="${APP_HTTP_PORT:-8080}"
if curl -sf "http://localhost:${APP_PORT}/health" >/dev/null 2>&1; then
  pass "App /health endpoint returns 200"
else
  # App might not be fully ready yet — warn instead of hard fail
  echo -e "${RED}WARN${NC}: App /health endpoint not reachable on port ${APP_PORT} (may still be starting)"
  FAILURES=$((FAILURES + 1))
fi

# 5. gRPC port is open
if timeout 2 bash -c "echo > /dev/tcp/localhost/${APP_GRPC_PORT:-50051}" 2>/dev/null; then
  pass "gRPC port ${APP_GRPC_PORT:-50051} is open"
else
  echo -e "${RED}WARN${NC}: gRPC port ${APP_GRPC_PORT:-50051} not reachable (may still be starting)"
  FAILURES=$((FAILURES + 1))
fi

echo ""
echo "=== Results: $((5 - FAILURES))/5 checks passed ==="

if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
exit 0
