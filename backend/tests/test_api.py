import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

import app.api as api_mod
from app.db import make_engine, get_session
from app.main import app
from app.seed_data import seed

H = lambda user, role: {"X-User": user, "X-Role": role}
DRAFT = "Our platform guarantees 60% faster support resolution time for every customer. Results may vary."


@pytest.fixture
def client():
    eng = make_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        seed(s)

    def override():
        with Session(eng, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_end_to_end(client):
    r = client.post("/content", json={"title": "Launch", "text": DRAFT}, headers=H("katya", "creator"))
    cid = r.json()["id"]
    rev = client.post(f"/content/{cid}/review", json={}, headers=H("katya", "creator")).json()
    assert rev["findings"] and any(f["layer"] == "C" for f in rev["findings"])
    assert all(f["suggested_fix"] is None or f["fix_verified"] for f in rev["findings"])
    assert client.get(f"/content/{cid}/claims").json()[0]["details"]["draft"]["qualifier_rank"] == 4

    assert client.post(f"/content/{cid}/approve", json={}, headers=H("p", "approver")).status_code == 409  # pending
    for f in rev["findings"]:
        bad = client.post(f"/findings/{f['id']}/decision", json={"decision": "rejected", "reason": ""},
                          headers=H("katya", "creator"))
        assert bad.status_code == 422  # reason is mandatory
        ok = client.post(f"/findings/{f['id']}/decision", json={"decision": "accepted", "reason": "will fix"},
                         headers=H("katya", "creator"))
        assert ok.status_code == 200
    assert client.post(f"/content/{cid}/approve", json={}, headers=H("katya", "approver")).status_code == 403
    pid = client.post(f"/content/{cid}/approve", json={}, headers=H("dr-pandey", "approver")).json()["passport_id"]
    assert client.get(f"/passport/{pid}/verify").json()["valid"] is True

    led = client.get("/ledger").json()[0]
    assert client.patch(f"/ledger/{led['id']}", json={"value": 40}, headers=H("m", "creator")).status_code == 403
    imp = client.patch(f"/ledger/{led['id']}", json={"value": 40}, headers=H("m", "brand_manager")).json()
    assert pid in imp["impact"]["passport_ids"]
    assert client.get(f"/passport/{pid}").json()["current_status"] == "flagged"

    cv = client.get(f"/content/{cid}").json()["content_version_id"]
    client.post(f"/demo/tamper/{cv}")
    assert client.get(f"/passport/{pid}/verify").json()["valid"] is False
    assert client.get("/audit/verify").json()["ok"] is True


def test_redaction_preview_and_linter(client):
    r = client.post("/redaction/preview", json={"text": "Mail me at a@b.com"}).json()
    assert "a@b.com" not in r["redacted_text"] and r["destination"] == "local model only"
    assert client.post("/linter/run", json={}, headers=H("m", "brand_manager")).status_code == 200
    assert client.post("/linter/run", json={}, headers=H("x", "creator")).status_code == 403
