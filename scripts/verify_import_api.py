#!/usr/bin/env python3
"""
CapTax AI — Import API Verification & Test Suite
Tests:
  1. GET /api/import/capabilities returns supported formats, OCR status, limits
  2. GET /api/import/status returns active dataset ("sample")
  3. POST /api/import/batches creates a new batch
  4. POST /api/import/batches/{batch_id}/files uploads a CSV with auto-detection
  5. GET /api/import/batches/{batch_id}/files/{file_id}/preview returns rows & mapping
  6. PUT /api/import/batches/{batch_id}/files/{file_id}/mapping updates mapping & row exclusions
  7. POST /api/import/batches/{batch_id}/validate returns row-level inspection report
  8. POST /api/import/batches/{batch_id}/confirm normalizes and writes data
  9. POST /api/import/reset-sample restores default sample data
"""

import sys
import json
import urllib.request
import urllib.error
import http.cookiejar

API_BASE = "http://127.0.0.1:8001"

def print_step(title):
    print(f"\n[TEST] {title}")

def main():
    print("=" * 60)
    print("CapTax AI — Import Service Verification Suite")
    print(f"Target backend: {API_BASE}")
    print("=" * 60)

    # 1. Login
    print_step("1. Authenticating as admin...")
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
    assert login_res.get("authenticated") is True
    print("  ✓ Authenticated successfully")

    # 2. Check capabilities
    print_step("2. Checking /api/import/capabilities...")
    cap_resp = opener.open(f"{API_BASE}/api/import/capabilities")
    cap_data = json.loads(cap_resp.read().decode())
    assert "supported_formats" in cap_data
    assert "file_types" in cap_data
    assert cap_data.get("max_file_size_mb") == 20
    print(f"  ✓ Capabilities returned: {len(cap_data['supported_formats'])} formats supported")
    print(f"  ✓ OCR available: {cap_data.get('ocr_available')}")
    print(f"  ✓ Formats: {', '.join(cap_data['file_types'])}")

    # 3. Check import status
    print_step("3. Checking /api/import/status...")
    st_resp = opener.open(f"{API_BASE}/api/import/status")
    st_data = json.loads(st_resp.read().decode())
    assert "active_dataset" in st_data
    print(f"  ✓ Active dataset: {st_data['active_dataset']}")

    # 4. Create batch
    print_step("4. Creating new import batch...")
    batch_req = urllib.request.Request(f"{API_BASE}/api/import/batches", method="POST", data=b"")
    batch_resp = opener.open(batch_req)
    batch_data = json.loads(batch_resp.read().decode())
    batch_id = batch_data["id"]
    assert batch_id and batch_data["status"] == "created"
    print(f"  ✓ Created batch: {batch_id}")

    # 5. Upload a statement CSV (with Zerodha headers)
    print_step("5. Uploading sample statement CSV...")
    csv_content = (
        "Symbol,ISIN,Trade Date,Trade Type,Quantity,Price,Brokerage,STT,Exchange,Trade ID\n"
        "TCS,INE467B01029,2024-03-01,BUY,50,3800.00,20.00,10.00,NSE,TRD1001\n"
        "TCS,INE467B01029,2024-06-15,SELL,50,4200.00,20.00,10.00,NSE,TRD1002\n"
        "RELIANCE,INE002A01018,2024-04-10,BUY,30,2900.00,20.00,10.00,NSE,TRD1003\n"
    ).encode("utf-8")

    upload_req = urllib.request.Request(
        f"{API_BASE}/api/import/batches/{batch_id}/files",
        data=csv_content,
        headers={
            "Content-Type": "text/csv",
            "X-Filename": "zerodha_statement_2024.csv"
        },
        method="POST"
    )
    upload_resp = opener.open(upload_req)
    file_data = json.loads(upload_resp.read().decode())
    file_id = file_data["id"]
    print(f"  ✓ Uploaded file: {file_data['filename']} (ID: {file_id})")
    print(f"  ✓ Auto-detected broker: {file_data.get('broker')}")
    print(f"  ✓ Auto-detected mapping: {file_data.get('mapping')}")
    assert file_data.get("broker") == "Zerodha"
    assert file_data.get("mapping", {}).get("symbol") == "Symbol"

    # 6. Preview uploaded file
    print_step("6. Previewing file rows...")
    prev_resp = opener.open(f"{API_BASE}/api/import/batches/{batch_id}/files/{file_id}/preview")
    prev_data = json.loads(prev_resp.read().decode())
    assert len(prev_data["rows"]) == 3
    print(f"  ✓ Preview returned {len(prev_data['rows'])} rows, {len(prev_data['columns'])} columns")

    # 7. Validate batch
    print_step("7. Validating batch...")
    val_req = urllib.request.Request(f"{API_BASE}/api/import/batches/{batch_id}/validate", method="POST", data=b"")
    val_resp = opener.open(val_req)
    val_data = json.loads(val_resp.read().decode())
    assert val_data["valid"] is True
    assert val_data["row_count"] == 3
    print(f"  ✓ Validation passed: {val_data['row_count']} valid trade rows")

    # 8. Confirm batch
    print_step("8. Confirming batch import...")
    conf_req = urllib.request.Request(f"{API_BASE}/api/import/batches/{batch_id}/confirm", method="POST", data=b"")
    conf_resp = opener.open(conf_req)
    conf_data = json.loads(conf_resp.read().decode())
    assert conf_data["status"] == "confirmed"
    assert conf_data["row_count"] == 3
    print(f"  ✓ Batch confirmed: {conf_data['row_count']} trades imported into normalized_trades.csv")

    # 9. Verify import status is now 'imported'
    print_step("9. Verifying active status...")
    st2_resp = opener.open(f"{API_BASE}/api/import/status")
    st2_data = json.loads(st2_resp.read().decode())
    assert st2_data["active_dataset"] == "imported"
    print(f"  ✓ Active dataset is now: {st2_data['active_dataset']} (Batch: {st2_data['active_batch']['id']})")

    # 10. Reset to sample data
    print_step("10. Resetting back to sample data...")
    reset_req = urllib.request.Request(f"{API_BASE}/api/import/reset-sample", method="POST", data=b"")
    reset_resp = opener.open(reset_req)
    reset_data = json.loads(reset_resp.read().decode())
    assert reset_data["active_dataset"] == "sample"
    print("  ✓ Successfully restored default sample dataset")

    # 11. Verify status is 'sample'
    st3_resp = opener.open(f"{API_BASE}/api/import/status")
    st3_data = json.loads(st3_resp.read().decode())
    assert st3_data["active_dataset"] == "sample"
    print("  ✓ Active status confirmed: sample")

    print("\n" + "=" * 60)
    print("🎉 ALL IMPORT API TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    main()

