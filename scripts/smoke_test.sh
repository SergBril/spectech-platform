#!/bin/bash
set -e

API="http://localhost:8000/api/v1"
PASS=0
FAIL=0

check() {
  local name="$1" method="$2" url="$3" data="$4" expected="$5"

  if [ "$method" = "GET" ]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$API$url")
  else
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$data" "$API$url")
  fi

  if [ "$code" = "$expected" ]; then
    echo "✅ $name ($code)"
    PASS=$((PASS + 1))
  else
    echo "❌ $name (expected $expected, got $code)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Smoke Test MVP ==="

# Health
check "Health" GET "/../health" "" 200
check "Ready" GET "/../ready" "" 200

# Auth
TOKEN=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@spectech.local","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

check "Login OK" POST "/auth/login" '{"email":"admin@spectech.local","password":"admin123"}' 200
check "Login bad" POST "/auth/login" '{"email":"admin@spectech.local","password":"wrong"}' 401

# Vehicles
check "List vehicles" GET "/vehicles" "" 200
check "Get vehicle 1" GET "/vehicles/1" "" 200
check "Vehicle 404" GET "/vehicles/99999" "" 404

# Requests
check "List requests" GET "/requests" "" 200
check "Get request 1" GET "/requests/1" "" 200

# Shifts
check "List shift tasks" GET "/shifts/tasks" "" 200
check "List shift reports" GET "/shifts/reports" "" 200

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ $FAIL -eq 0 ] && echo "🎉 ALL TESTS PASSED" || echo "⚠️ SOME TESTS FAILED"
