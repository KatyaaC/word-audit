from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from bt_auth import UserOut, require_roles, router

app = FastAPI()
app.include_router(router)


@app.get("/approver-only")
def approver_only(user: UserOut = Depends(require_roles("approver"))):
    return {"ok": user.id}


client = TestClient(app)


def token(email: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_login_and_me():
    t = token("creator@wordaudit.demo")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {t}"})
    assert r.json()["role"] == "creator"


def test_wrong_password():
    r = client.post("/auth/login", json={"email": "creator@wordaudit.demo", "password": "nope"})
    assert r.status_code == 401


def test_role_gate():
    ok = client.get("/approver-only", headers={"Authorization": f"Bearer {token('approver@wordaudit.demo')}"})
    no = client.get("/approver-only", headers={"Authorization": f"Bearer {token('creator@wordaudit.demo')}"})
    assert ok.status_code == 200 and no.status_code == 403


def test_missing_token():
    assert client.get("/auth/me").status_code == 401
