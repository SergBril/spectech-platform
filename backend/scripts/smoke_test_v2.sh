#!/bin/bash
set -e

API="http://localhost:8000/api/v1"
PASS=0
FAIL=0

check() {
  local name="$1" method="$2" url="$3" data="$4" expected="$5"
  local code

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

echo "=== Smoke Test V2: Catalogs & RBAC ==="

# Auth
TOKEN=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@spectech.dev","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Contractors
check "List contractors" GET "/contractors" "" 200
check "List clients" GET "/contractors?type=client" "" 200
check "List owners" GET "/contractors?type=owner" "" 200
check "List employees" GET "/contractors?type=employee" "" 200

# RBAC
check "List roles" GET "/rbac/roles" "" 200
check "List permissions" GET "/rbac/permissions" "" 200

# Me
check "Get my roles" GET "/me/roles" "" 200
check "Get my permissions" GET "/me/permissions" "" 200

# Categories
check "List categories" GET "/categories" "" 200

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ $FAIL -eq 0 ] && echo "🎉 ALL TESTS PASSED" || echo "⚠️ SOME TESTS FAILED"
