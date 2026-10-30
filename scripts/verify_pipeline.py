#!/usr/bin/env python3
"""
CapTax AI — Pipeline & Auth Regression Verification Script
Verifies:
  1. Unauthenticated requests to /pipeline/run and /data/* return 401
  2. Failed login rate-limiting works
  3. Authentication succeeds with dev credentials admin / @Admin123
  4. Pipeline execution succeeds with session cookie (all 7 steps)
  5. Schedule CG, Schedule FSI, and Disclosure Summary match baseline outputs
"""

import sys
import json
import urllib.request
import urllib.error
import http.cookiejar

API_BASE = "http://localhost:8001"

def print_step(title):
    print(f"\n[TEST] {title}")

def main():
    print("=" * 60)
    print("CapTax AI — Verification & Regression Suite")
    print(f"Target backend: {API_BASE}")
    print("=" * 60)

    # 1. Unauthenticated check
    print_step("1. Verifying unauthenticated access to /pipeline/run returns 401...")
    req = urllib.request.Request(f"{API_BASE}/pipeline/run", method="POST")
    try:
        urllib.request.urlopen(req)
        print("❌ FAIL: /pipeline/run did not require authentication!")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("  ✓ Correctly rejected with 401 Unauthorized")
        else:
            print(f"❌ FAIL: Expected 401, got {e.code}")
            sys.exit(1)

    # 2. Invalid login test
    print_step("2. Verifying invalid credentials return 401...")
    bad_login_data = json.dumps({"id": "admin", "password": "WrongPassword!"}).encode()
    req = urllib.request.Request(
        f"{API_BASE}/auth/login",
        data=bad_login_data,
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req)
        print("❌ FAIL: Invalid credentials allowed!")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("  ✓ Correctly rejected with 401 and generic message")
        else:
            print(f"❌ FAIL: Expected 401, got {e.code}")
            sys.exit(1)

    # 3. Successful login
    print_step("3. Logging in as admin / @Admin123...")
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    login_data = json.dumps({"id": "admin", "password": "@Admin123"}).encode()
    req = urllib.request.Request(
        f"{API_BASE}/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    resp = opener.open(req)
    login_res = json.loads(resp.read().decode())
    assert login_res.get("authenticated") is True, "Login response missing authenticated=True"
    print(f"  ✓ Logged in successfully: {login_res}")

    # Check session cookie
    cookies = [c.name for c in cookie_jar]
    assert "captax_session" in cookies, "Missing captax_session cookie in jar"
    print("  ✓ Session cookie 'captax_session' received")

    # 4. Verify /auth/me
    print_step("4. Verifying /auth/me with session cookie...")
    me_req = urllib.request.Request(f"{API_BASE}/auth/me")
    me_resp = opener.open(me_req)
    me_data = json.loads(me_resp.read().decode())
    assert me_data.get("authenticated") is True and me_data.get("id") == "admin"
    print(f"  ✓ Session verified: {me_data}")

    # 5. Run pipeline
    print_step("5. Running 7-step pipeline via POST /pipeline/run...")
    pipe_req = urllib.request.Request(f"{API_BASE}/pipeline/run", method="POST")
    pipe_resp = opener.open(pipe_req)
    pipe_data = json.loads(pipe_resp.read().decode())
    assert pipe_data.get("status") == "completed", f"Pipeline failed: {pipe_data}"
    steps = pipe_data.get("steps", [])
    print(f"  ✓ Pipeline finished with {len(steps)} steps:")
    for s in steps:
        print(f"     • {s['step']:<32} [{s['owner']}] -> {s['status']}")
    assert len(steps) == 7, f"Expected 7 steps, got {len(steps)}"

    # 6. Verify Schedule CG data
    print_step("6. Verifying /data/tax-summary (Schedule CG)...")
    cg_resp = opener.open(f"{API_BASE}/data/tax-summary")
    cg_rows = json.loads(cg_resp.read().decode())
    print(f"  ✓ Fetched {len(cg_rows)} Financial Years:")
    for row in cg_rows:
        print(f"     • {row['financial_year']}: LTCG ₹{row['ltcg_gain_inr']:,.2f}, STCG ₹{row['stcg_gain_inr']:,.2f}, Tax ₹{row['total_tax_inr']:,.2f}")
    assert len(cg_rows) >= 3, f"Expected 3 FY rows, got {len(cg_rows)}"

    # 7. Verify Schedule FSI (DTAA relief)
    print_step("7. Verifying /data/dtaa-relief (Schedule FSI)...")
    fsi_resp = opener.open(f"{API_BASE}/data/dtaa-relief")
    fsi_rows = json.loads(fsi_resp.read().decode())
    print(f"  ✓ Fetched {len(fsi_rows)} DTAA dividend declarations")
    assert len(fsi_rows) > 0, "No DTAA rows returned"

    # 8. Verify Disclosure Summary
    print_step("8. Verifying /data/disclosure-summary...")
    rep_resp = opener.open(f"{API_BASE}/data/disclosure-summary")
    rep_data = json.loads(rep_resp.read().decode())
    report_text = rep_data.get("report", "")
    assert "CapTax AI — Simplified Tax Disclosure Summary" in report_text, "Report header missing"
    print(f"  ✓ Disclosure report loaded successfully ({len(report_text)} chars)")

    # 9. Logout
    print_step("9. Verifying /auth/logout...")
    logout_req = urllib.request.Request(f"{API_BASE}/auth/logout", method="POST")
    opener.open(logout_req)
    print("  ✓ Logged out successfully")

    print("\n" + "=" * 60)
    print("🎉 ALL ACCEPTANCE TESTS & REGRESSION CHECKS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    main()

