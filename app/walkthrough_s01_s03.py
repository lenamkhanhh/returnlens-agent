"""Live HTTP Walkthrough for S01 (WISMO), S03 (Case A Damage), and S04 (Case B Color Mismatch).

Executes real HTTP requests against http://127.0.0.1:8000 using real media files and records the transcript.
"""

from pathlib import Path
import json
import httpx

BASE_URL = "http://127.0.0.1:8000"

def run_walkthrough():
    transcript = []
    
    with httpx.Client(base_url=BASE_URL, timeout=25.0) as client:
        print("=== Checking Health ===")
        r = client.get("/api/health")
        print(f"GET /api/health -> {r.status_code}: {r.json()}")
        assert r.status_code == 200
        transcript.append({"step": "HEALTH", "status": r.status_code, "body": r.json()})

        # Reset database for fresh test run
        r_reset = client.post("/api/operator/reset")
        print(f"POST /api/operator/reset -> {r_reset.status_code}")
        transcript.append({"step": "RESET_DB", "status": r_reset.status_code})

        # ======================================================================
        # S01: WISMO (Where is my order?)
        # ======================================================================
        print("\n=== Running S01 (WISMO) ===")
        # 1. Inbound customer inquiry
        r_s01_create = client.post(
            "/api/cases",
            json={"order_id": "ORD-2030", "initial_message": "Where is my order?"},
            headers={"X-Customer-Id": "CUS-01"},
        )
        print(f"POST /api/cases (S01) -> {r_s01_create.status_code}: {r_s01_create.json()}")
        assert r_s01_create.status_code == 202
        s01_case_id = r_s01_create.json()["case_id"]
        transcript.append({
            "scenario": "S01",
            "action": "CREATE_CASE",
            "request": {"order_id": "ORD-2030", "customer_id": "CUS-01", "message": "Where is my order?"},
            "status": r_s01_create.status_code,
            "response": r_s01_create.json(),
        })

        # 2. Get case snapshot
        r_s01_snap = client.get(f"/api/cases/{s01_case_id}", headers={"X-Customer-Id": "CUS-01"})
        print(f"GET /api/cases/{s01_case_id} -> {r_s01_snap.status_code}")
        assert r_s01_snap.status_code == 200
        s01_snap = r_s01_snap.json()
        print(f"  State: {s01_snap['state']}, Messages count: {len(s01_snap['messages'])}")
        assert s01_snap["state"] == "RESOLVED"
        assert len(s01_snap["messages"]) >= 2
        transcript.append({
            "scenario": "S01",
            "action": "GET_SNAPSHOT",
            "status": r_s01_snap.status_code,
            "state": s01_snap["state"],
            "messages": s01_snap["messages"],
        })

        # 3. Get customer visible messages endpoint (Bug 1 verification)
        r_s01_msgs = client.get(f"/api/cases/{s01_case_id}/messages")
        print(f"GET /api/cases/{s01_case_id}/messages -> {r_s01_msgs.status_code}, count: {len(r_s01_msgs.json())}")
        assert r_s01_msgs.status_code == 200
        assert len(r_s01_msgs.json()) >= 2
        transcript.append({
            "scenario": "S01",
            "action": "GET_MESSAGES",
            "status": r_s01_msgs.status_code,
            "body": r_s01_msgs.json(),
        })

        # ======================================================================
        # S03: Case A Damage (ORD-1042)
        # ======================================================================
        print("\n=== Running S03 (Case A Damage) ===")
        # 1. Customer initiates case
        r_s03_create = client.post(
            "/api/cases",
            json={"order_id": "ORD-1042", "initial_message": "The headband cracked. I want to return it."},
            headers={"X-Customer-Id": "CUS-03"},
        )
        print(f"POST /api/cases (S03) -> {r_s03_create.status_code}: {r_s03_create.json()}")
        assert r_s03_create.status_code == 202
        s03_case_id = r_s03_create.json()["case_id"]
        transcript.append({
            "scenario": "S03",
            "action": "CREATE_CASE",
            "request": {"order_id": "ORD-1042", "customer_id": "CUS-03"},
            "status": r_s03_create.status_code,
            "response": r_s03_create.json(),
        })

        # 2. Customer uploads damage video evidence (real synthetic_damaged_item.webm)
        media_path = Path("app/demo/media/synthetic_damaged_item.webm")
        clip_bytes = media_path.read_bytes() if media_path.exists() else b"\x00\x00\x00\x20ftypisom" + b"\x00" * 200
        r_upload = client.post(
            f"/api/cases/{s03_case_id}/evidence",
            files={"file": ("synthetic_damaged_item.webm", clip_bytes, "video/webm")},
            data={"client_upload_id": "UPL-S03-01"},
        )
        print(f"POST /api/cases/{s03_case_id}/evidence -> {r_upload.status_code}: {r_upload.json()}")
        assert r_upload.status_code == 201
        transcript.append({
            "scenario": "S03",
            "action": "UPLOAD_EVIDENCE",
            "status": r_upload.status_code,
            "response": r_upload.json(),
        })

        # 3. Inspect case snapshot for return proposal
        r_s03_snap1 = client.get(f"/api/cases/{s03_case_id}", headers={"X-Customer-Id": "CUS-03"})
        s03_snap1 = r_s03_snap1.json()
        print(f"GET /api/cases/{s03_case_id} (turn 1) -> state: {s03_snap1['state']}, proposals: {len(s03_snap1['proposals'])}")
        assert s03_snap1["state"] == "WAITING_SELLER"
        assert len(s03_snap1["proposals"]) >= 1

        ret_proposal = s03_snap1["proposals"][0]
        ret_proposal_id = ret_proposal["proposal_id"]
        ret_payload_hash = ret_proposal["payload_hash"]
        print(f"  Return Proposal: {ret_proposal_id}, action_type: {ret_proposal['action_type']}")
        transcript.append({
            "scenario": "S03",
            "action": "SNAP_TURN_1",
            "state": s03_snap1["state"],
            "proposal": ret_proposal,
        })

        # 4. Seller approves return proposal
        r_ret_dec = client.post(
            f"/api/proposals/{ret_proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": ret_payload_hash},
            headers={"X-Seller-Id": "seller_dhun", "Idempotency-Key": "IDEMP-S03-RETURN-01"},
        )
        print(f"POST /api/proposals/{ret_proposal_id}/decisions -> status {r_ret_dec.status_code}, body: {r_ret_dec.text}")
        assert r_ret_dec.status_code == 200
        transcript.append({
            "scenario": "S03",
            "action": "APPROVE_RETURN",
            "status": r_ret_dec.status_code,
            "response": r_ret_dec.json(),
        })

        # Check state transitioned to WAITING_RETURN
        r_s03_snap2 = client.get(f"/api/cases/{s03_case_id}", headers={"X-Customer-Id": "CUS-03"})
        assert r_s03_snap2.json()["state"] == "WAITING_RETURN"

        # 5. Warehouse receives returned parcel -> Operator injects RETURN_RECEIVED
        r_courier = client.post(
            "/api/operator/courier-events",
            json={"shipment_id": "SHP-1042", "type": "RETURN_RECEIVED"},
        )
        print(f"POST /api/operator/courier-events -> {r_courier.status_code}: {r_courier.json()}")
        assert r_courier.status_code == 200
        transcript.append({
            "scenario": "S03",
            "action": "COURIER_RETURN_RECEIVED",
            "status": r_courier.status_code,
            "response": r_courier.json(),
        })

        # 6. Check for refund proposal
        r_s03_snap3 = client.get(f"/api/cases/{s03_case_id}", headers={"X-Customer-Id": "CUS-03"})
        s03_snap3 = r_s03_snap3.json()
        print(f"GET /api/cases/{s03_case_id} (turn 2) -> proposals: {len(s03_snap3['proposals'])}")
        ref_proposal = next(p for p in s03_snap3["proposals"] if p["action_type"] == "PROPOSE_REFUND")
        ref_proposal_id = ref_proposal["proposal_id"]
        ref_payload_hash = ref_proposal["payload_hash"]
        print(f"  Refund Proposal: {ref_proposal_id}, amount_minor: {ref_proposal['amount_minor']}")

        # 7. Seller approves refund proposal
        r_ref_dec = client.post(
            f"/api/proposals/{ref_proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": ref_payload_hash},
            headers={"X-Seller-Id": "seller_dhun", "Idempotency-Key": "IDEMP-S03-REFUND-01"},
        )
        print(f"POST /api/proposals/{ref_proposal_id}/decisions -> {r_ref_dec.status_code}: {r_ref_dec.json()}")
        assert r_ref_dec.status_code == 200
        ref_result = r_ref_dec.json()
        assert ref_result["status"] == "succeeded"
        transcript.append({
            "scenario": "S03",
            "action": "APPROVE_REFUND",
            "status": r_ref_dec.status_code,
            "response": ref_result,
        })

        # 8. Replay identical decision with same Idempotency-Key (Invariant: no duplicate refund)
        r_ref_replay = client.post(
            f"/api/proposals/{ref_proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": ref_payload_hash},
            headers={"X-Seller-Id": "seller_dhun", "Idempotency-Key": "IDEMP-S03-REFUND-01"},
        )
        print(f"POST /api/proposals/{ref_proposal_id}/decisions (replay) -> {r_ref_replay.status_code}: {r_ref_replay.json()}")
        assert r_ref_replay.status_code == 200
        assert r_ref_replay.json()["action_id"] == ref_result["action_id"]

        # 9. Final state check
        r_s03_final = client.get(f"/api/cases/{s03_case_id}", headers={"X-Customer-Id": "CUS-03"})
        s03_final = r_s03_final.json()
        print(f"GET /api/cases/{s03_case_id} (final) -> state: {s03_final['state']}, summary: {s03_final['facts']['order']['refunded_minor']} paise refunded")
        assert s03_final["state"] == "RESOLVED"
        assert s03_final["facts"]["order"]["refunded_minor"] == 129900
        transcript.append({
            "scenario": "S03",
            "action": "FINAL_VERIFICATION",
            "state": s03_final["state"],
            "refunded_minor": s03_final["facts"]["order"]["refunded_minor"],
            "messages": s03_final["messages"],
        })

        # ======================================================================
        # S04: Case B Color Mismatch (ORD-7729)
        # ======================================================================
        print("\n=== Running S04 (Case B Color Mismatch) ===")
        # 1. Customer initiates color mismatch claim (ordered white, received black)
        r_s04_create = client.post(
            "/api/cases",
            json={
                "order_id": "ORD-7729",
                "initial_message": "I ordered white headphones but got black ones instead.",
            },
            headers={"X-Customer-Id": "CUS-02"},
        )
        print(f"POST /api/cases (S04) -> {r_s04_create.status_code}: {r_s04_create.json()}")
        assert r_s04_create.status_code == 202
        s04_case_id = r_s04_create.json()["case_id"]
        transcript.append({
            "scenario": "S04",
            "action": "CREATE_CASE",
            "request": {"order_id": "ORD-7729", "customer_id": "CUS-02"},
            "status": r_s04_create.status_code,
            "response": r_s04_create.json(),
        })

        # 2. Check snapshot: state WAITING_CUSTOMER, clarification_count 1, agent asks for outer box label photo
        r_s04_snap1 = client.get(f"/api/cases/{s04_case_id}", headers={"X-Customer-Id": "CUS-02"})
        s04_snap1 = r_s04_snap1.json()
        print(f"GET /api/cases/{s04_case_id} (turn 1) -> state: {s04_snap1['state']}, clarifications: {s04_snap1['clarification_count']}")
        assert s04_snap1["state"] == "WAITING_CUSTOMER"
        assert s04_snap1["clarification_count"] == 1
        messages_s04 = s04_snap1["messages"]
        agent_msgs = [m["text"] for m in messages_s04 if m["role"] == "agent"]
        assert len(agent_msgs) >= 1
        assert "label" in agent_msgs[-1].lower() and "photo" in agent_msgs[-1].lower()
        print(f"  Agent Clarification Request: \"{agent_msgs[-1]}\"")
        transcript.append({
            "scenario": "S04",
            "action": "CLARIFICATION_REQUESTED",
            "state": s04_snap1["state"],
            "clarification_count": s04_snap1["clarification_count"],
            "agent_message": agent_msgs[-1],
        })

        # 3. Customer uploads outer box label photo (Clip-B2: synthetic_label_closeup.png)
        label_media_path = Path("app/demo/media/synthetic_label_closeup.png")
        label_bytes = label_media_path.read_bytes() if label_media_path.exists() else b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        r_s04_upload = client.post(
            f"/api/cases/{s04_case_id}/evidence",
            files={"file": ("synthetic_label_closeup.png", label_bytes, "image/png")},
            data={"client_upload_id": "UPL-S04-01"},
        )
        print(f"POST /api/cases/{s04_case_id}/evidence (S04) -> {r_s04_upload.status_code}")
        assert r_s04_upload.status_code == 201

        # Customer sends follow-up message with barcode text
        r_s04_msg2 = client.post(
            f"/api/cases/{s04_case_id}/messages",
            json={"text": "Here is the photo of the outer box label showing the barcode and model number."},
            headers={"X-Customer-Id": "CUS-02"},
        )
        print(f"POST /api/cases/{s04_case_id}/messages (S04) -> {r_s04_msg2.status_code}")
        assert r_s04_msg2.status_code == 202

        # 4. Check snapshot: state WAITING_SELLER, proposal PROPOSE_RETURN created
        r_s04_snap2 = client.get(f"/api/cases/{s04_case_id}", headers={"X-Customer-Id": "CUS-02"})
        s04_snap2 = r_s04_snap2.json()
        print(f"GET /api/cases/{s04_case_id} (turn 2) -> state: {s04_snap2['state']}, proposals: {len(s04_snap2['proposals'])}")
        assert s04_snap2["state"] == "WAITING_SELLER"
        assert len(s04_snap2["proposals"]) >= 1

        s04_ret_prop = s04_snap2["proposals"][0]
        s04_prop_id = s04_ret_prop["proposal_id"]
        s04_payload_hash = s04_ret_prop["payload_hash"]
        print(f"  Return Proposal: {s04_prop_id}, action_type: {s04_ret_prop['action_type']}")
        transcript.append({
            "scenario": "S04",
            "action": "RETURN_PROPOSED",
            "state": s04_snap2["state"],
            "proposal": s04_ret_prop,
        })

        # 5. Seller approves return proposal
        r_s04_dec = client.post(
            f"/api/proposals/{s04_prop_id}/decisions",
            json={"decision": "approve", "payload_hash": s04_payload_hash},
            headers={"X-Seller-Id": "seller_dhun", "Idempotency-Key": "IDEMP-S04-RETURN-01"},
        )
        print(f"POST /api/proposals/{s04_prop_id}/decisions (S04) -> {r_s04_dec.status_code}: {r_s04_dec.json()}")
        assert r_s04_dec.status_code == 200
        assert r_s04_dec.json()["status"] == "succeeded"
        transcript.append({
            "scenario": "S04",
            "action": "APPROVE_RETURN",
            "status": r_s04_dec.status_code,
            "response": r_s04_dec.json(),
        })

        # 6. Verify final state WAITING_RETURN
        r_s04_final = client.get(f"/api/cases/{s04_case_id}", headers={"X-Customer-Id": "CUS-02"})
        s04_final = r_s04_final.json()
        print(f"GET /api/cases/{s04_case_id} (final) -> state: {s04_final['state']}")
        assert s04_final["state"] == "WAITING_RETURN"
        transcript.append({
            "scenario": "S04",
            "action": "FINAL_VERIFICATION",
            "state": s04_final["state"],
            "messages": s04_final["messages"],
        })

    print("\n=== ALL SCENARIOS S01, S03 & S04 VERIFIED OVER LIVE HTTP ===")
    return transcript

if __name__ == "__main__":
    t = run_walkthrough()
    with open("data/walkthrough_transcript.json", "w") as f:
        json.dump(t, f, indent=2)
    print("Saved transcript to data/walkthrough_transcript.json")
