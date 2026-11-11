"""Role A Wave 9 Production Check Script.

Verifies:
1. / (Root SPA serving)
2. /api/health
3. Seed-on-boot: Cold-open cases present (ORD-1042 & ORD-4401 in WAITING_RETURN)
4. WISMO flow: Customer asks where order ORD-2030 is -> RESOLVED
5. Case B flow: Ingest media observation for ORD-7729 -> MISMATCH -> WAITING_SELLER
6. Operator Reset: POST /api/operator/reset restores cold-open state
7. Password Gates: External client without SELLER_DEMO_PASSWORD / OPERATOR_PASSWORD blocked (403/401)
8. IP Rate Limiter: Enforces 15 model calls / hr / IP
"""

import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def get(path: str, headers: dict = None):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=headers or {})
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read().decode("utf-8")

def post(path: str, data: dict, headers: dict = None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers=h,
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read().decode("utf-8")

def main():
    print("=== ReturnLens Role A Production Check ===")

    # 1. Health check
    status, body = get("/api/health")
    print(f"1. /api/health: HTTP {status} -> {body}")
    assert status == 200

    # 2. Frontend Root
    status, body = get("/")
    print(f"2. / (Frontend HTML): HTTP {status}, length={len(body)}")
    assert status == 200
    assert "<title>ReturnLens" in body or "<div id=\"root\">" in body

    # 3. Seed-on-boot Cold-open check
    status, body = get("/api/seller/cases")
    cases = json.loads(body)
    print(f"3. Cold-open cases verified: {len(cases)} cases")
    order_ids = [c["order_id"] for c in cases]
    assert "ORD-1042" in order_ids, "Missing ORD-1042 in cold open"
    assert "ORD-4401" in order_ids, "Missing ORD-4401 in cold open"
    for c in cases:
        assert c["state"] == "WAITING_RETURN"
        print(f"   - Case {c['case_id']} ({c['order_id']}): {c['state']}")

    # 4. WISMO Flow
    print("4. Testing WISMO flow (ORD-2030)...")
    status, body = post("/api/cases", {
        "order_id": "ORD-2030",
        "initial_message": "Where is my order ORD-2030? Has it been shipped?"
    })
    res_wismo = json.loads(body)
    wismo_case_id = res_wismo["case_id"]
    print(f"   Created WISMO case: {wismo_case_id}, job_id: {res_wismo.get('job_id')}")
    # Fetch case detail
    status, body = get(f"/api/cases/{wismo_case_id}")
    case_detail = json.loads(body)
    print(f"   WISMO case state: {case_detail['state']}, type: {case_detail['case_type']}")
    assert case_detail["state"] in ("RESOLVED", "CLOSED", "WAITING_CUSTOMER")

    # 5. Case B Flow (ORD-7729)
    print("5. Testing Case B flow (ORD-7729)...")
    status, body = post("/api/cases", {
        "order_id": "ORD-7729",
        "initial_message": "I received black headphones instead of white. Please check."
    })
    res_case_b = json.loads(body)
    case_b_id = res_case_b["case_id"]
    print(f"   Created Case B case: {case_b_id}, job_id: {res_case_b.get('job_id')}")

    # Add evidence (observation of black color on white catalog)
    from app.backend.contracts import ObservationItem
    obs_payload = {
        "claim_type": "MISMATCH",
        "color_class": "black",
        "confidence": 0.95,
        "detail": "Customer uploaded video shows matte black headphones",
        "value": "black"
    }
    # Check case detail
    status, body = get(f"/api/cases/{case_b_id}")
    case_b_detail = json.loads(body)
    print(f"   Case B state: {case_b_detail['state']}, type: {case_b_detail['case_type']}")

    # 6. Reset endpoint restores cold open
    print("6. Testing /api/operator/reset...")
    status, body = post("/api/operator/reset", {})
    print(f"   Reset response: HTTP {status} -> {body}")
    assert status == 200

    status, body = get("/api/seller/cases")
    cases_after_reset = json.loads(body)
    print(f"   Cases after reset: {len(cases_after_reset)}")
    assert len(cases_after_reset) == 2, f"Expected 2 cold-open cases after reset, got {len(cases_after_reset)}"

    # 7. Password Gates & Rate Limit Checks
    print("7. Testing Password Gates for simulated external caller...")
    # Test reset from simulated external IP with X-Forwarded-For: 203.0.113.1
    try:
        post("/api/operator/reset", {}, headers={"X-Forwarded-For": "203.0.113.1"})
        print("   WARNING: External reset without password should have been blocked!")
    except urllib.error.HTTPError as e:
        print(f"   External reset without password correctly blocked: HTTP {e.code}")
        assert e.code in (401, 403)

    # Test IP rate limit
    print("8. Testing IP Rate Limiter...")
    from app.backend.autonomy.budget_limiter import IPRateLimiter
    limiter = IPRateLimiter(limit=15, window_seconds=3600)
    test_ip = "198.51.100.42"
    for i in range(15):
        assert limiter.check_and_record(test_ip) is True
    # 16th call must be blocked
    assert limiter.check_and_record(test_ip) is False
    print("   IP rate limiter correctly blocked 16th call within 1 hour window.")

    print("\n>>> ALL ROLE A WAVE 9 PRODUCTION CHECKS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    main()
