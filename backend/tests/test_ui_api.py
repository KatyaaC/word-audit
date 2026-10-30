"""The website contract (/api): login, review, workflow, Passport, impact, insights, rules."""
import io

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.db import get_session, make_engine
from app.demo_seed import seed_demo
from app.main import app
from app.seed_data import seed

STARTER = "Close your books faster\nPaisaLeaf Ledger guarantees 60% faster reconciliation for every customer. " \
          "Get a free trial today!!"


@pytest.fixture
def client():
    eng = make_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        seed(s)
        seed_demo(s)

    def override():
        with Session(eng, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(client, who):
    r = client.post("/api/auth/login", json={"email": f"{who}@wordaudit.demo", "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def submit_draft(client, h, text=STARTER):
    r = client.post("/api/content", headers=h, json={
        "title": "Launch post", "text": text, "html": None,
        "colour_pairs": [{"element": "Primary button", "foreground": "#ffffff", "background": "#16a34a",
                          "large_text": False}],
        "images": []})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_rejects_bad_password(client):
    r = client.post("/api/auth/login", json={"email": "creator@wordaudit.demo", "password": "nope"})
    assert r.status_code == 401
    assert client.get("/api/content").status_code == 401


def test_review_merges_brand_pack_and_engine(client):
    item = submit_draft(client, auth(client, "creator"))
    rules = {f["rule_id"] for f in item["findings"]}
    layers = {f["layer"] for f in item["findings"]}
    # Brand rule pack (same as the live editor): guarantee, exclamations, T&C, contrast
    assert {"BAN-001", "TONE-001", "REQ-001", "A11Y-001"} <= rules
    # Sudiksha's engine: claim drift against the pilot fact
    assert "C" in layers
    drift = next(f for f in item["findings"] if f["layer"] == "C")
    assert drift["fact_id"] == "CL-PL-001" and drift["span"]
    assert item["state"] == "draft" and item["author_id"] == "u-creator"
    claim = next(c for c in item["claims"] if c["ledger_fact_id"] == "CL-PL-001")
    scope = next(l for l in claim["ladders"] if l["name"] == "Scope")
    assert scope["draft_index"] > scope["ledger_index"]
    for f in item["findings"]:  # spans point at the real text
        if f["span"] and f["matched_text"]:
            assert STARTER[f["span"]["start"]:f["span"]["end"]] == f["matched_text"]


def test_full_workflow_passport_and_tamper(client):
    hc, hr, ha = auth(client, "creator"), auth(client, "reviewer"), auth(client, "approver")
    item = submit_draft(client, hc)
    cid = item["id"]

    r = client.post(f"/api/content/{cid}/transition", headers=hc, json={"action": "submit"})
    assert r.status_code == 409 and "respond to" in r.json()["detail"]

    for f in item["findings"]:
        r = client.post(f"/api/content/{cid}/findings/{f['id']}/response", headers=hc,
                        json={"decision": "rejected", "reason": "Fine for this demo"})
        assert r.status_code == 200, r.text
    assert client.post(f"/api/content/{cid}/comments", headers=hr, json={"body": "Looks ok"}).status_code == 200

    assert client.post(f"/api/content/{cid}/transition", headers=hc, json={"action": "submit"}).json()["state"] == "in_review"
    assert client.post(f"/api/content/{cid}/transition", headers=hc, json={"action": "forward"}).status_code == 403
    assert client.post(f"/api/content/{cid}/transition", headers=hr,
                       json={"action": "forward"}).json()["state"] == "awaiting_approval"
    done = client.post(f"/api/content/{cid}/transition", headers=ha, json={"action": "approve"}).json()
    assert done["state"] == "approved" and done["passport_id"]
    assert done["comments"][0]["body"] == "Looks ok"
    assert any(a["action"] == "approved" for a in done["audit"])

    pid = done["passport_id"]
    p = client.get(f"/api/passports/{pid}").json()  # public, no token
    assert p["current_status"] == "valid" and p["approved_by"] == "Meera Shah"
    assert any(e["fact_id"] == "CL-PL-001" for e in p["evidence"])

    ok = client.post(f"/api/passports/{pid}/verify", json={}).json()
    assert ok["signature_valid"] and ok["fingerprint_match"]
    same = client.post(f"/api/passports/{pid}/verify", json={"content": p["canonical_text"]}).json()
    assert same["fingerprint_match"]
    bad = client.post(f"/api/passports/{pid}/verify", json={"content": p["canonical_text"] + " Extra."}).json()
    assert bad["signature_valid"] and not bad["fingerprint_match"]

    # Expiring the fact flags the content and the Passport
    hm = auth(client, "manager")
    out = client.post("/api/ledger/facts/CL-PL-001/expire", headers=hm).json()
    assert cid in out["flagged_content"] and pid in out["flagged_passports"]
    assert client.get(f"/api/content/{cid}", headers=hc).json()["state"] == "needs_rereview"
    assert client.get(f"/api/passports/{pid}").json()["current_status"] == "needs_rereview"

    ins = client.get("/api/insights", headers=hm).json()
    ids = {n["id"] for n in ins["impact"]["nodes"]}
    assert {"CL-PL-001", cid, pid} <= ids
    assert ins["repeated_mistakes"] and ins["findings_per_week"]


def test_strict_mode_and_new_version(client):
    hc = auth(client, "creator")
    item = submit_draft(client, hc, "Our new app is simple to use.")
    cid = item["id"]
    r = client.post(f"/api/content/{cid}/versions", headers=hc, json={
        "title": "Launch post", "text": "Our new app is simple to use. It is a miracle cure!!",
        "colour_pairs": [], "images": []})
    v2 = r.json()
    assert len(v2["versions"]) == 2 and v2["state"] == "draft"
    assert v2["findings"] and all(f["response"] is None for f in v2["findings"])
    # Only the author can add versions
    assert client.post(f"/api/content/{cid}/versions", headers=auth(client, "reviewer"),
                       json={"text": "x", "colour_pairs": [], "images": []}).status_code == 403


def test_constitution_upload_and_approve(client):
    hm = auth(client, "manager")
    before = client.get("/api/constitution", headers=hm).json()
    guide = b'Voice guide\n\nNever use "world-class" in any copy.\n\nAlways include "Terms apply" on offers.'
    doc = client.post("/api/constitution/upload", headers=hm, data={"classification": "internal"},
                      files={"file": ("voice.txt", io.BytesIO(guide), "text/plain")}).json()
    assert doc["filename"] == "voice.txt" and len(doc["rules"]) == 2
    assert all(r["status"] == "draft" and r["drafted_by"] == "software" for r in doc["rules"])
    after = client.post(f"/api/constitution/rules/{doc['rules'][0]['id']}/decision", headers=hm,
                        json={"decision": "approve", "reason": ""}).json()
    assert after["version"] != before["version"]
    assert client.post(f"/api/constitution/rules/{doc['rules'][1]['id']}/decision", headers=auth(client, "creator"),
                       json={"decision": "approve", "reason": ""}).status_code == 403
    assert any(d["id"] == "pack" for d in after["documents"])
