"""FastAPI router for Layer A.

Sudiksha can mount this in the main API with:

    from layer_a.router import router as layer_a_router
    app.include_router(layer_a_router)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from .engine import count_by_severity, run_layer_a
from .models import CheckRequest, CheckResponse, RulePack
from .rules import load_rule_pack

router = APIRouter(prefix="/layer-a", tags=["Layer A"])


@router.get("/rule-pack", response_model=RulePack)
def get_rule_pack() -> RulePack:
    return load_rule_pack()


@router.post("/check", response_model=CheckResponse)
def check(req: CheckRequest) -> CheckResponse:
    pack = load_rule_pack()
    findings = run_layer_a(req, pack)
    return CheckResponse(
        rule_pack_version=pack.version,
        checked_at=datetime.now(timezone.utc),
        findings=findings,
        counts=count_by_severity(findings),
    )
