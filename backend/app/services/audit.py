"""Hash-chained audit log."""
import hashlib
import json
import threading
from typing import Optional

from sqlmodel import Session, select

from ..models import AuditLog, now_iso

_lock = threading.Lock()
GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(seq, ts, actor, action, entity, entity_id, data, prev_hash) -> str:
    body = canonical(
        {"seq": seq, "ts": ts, "actor": actor, "action": action, "entity": entity,
         "entity_id": entity_id, "data": data, "prev_hash": prev_hash}
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def log(session: Session, actor: str, action: str, entity: str, entity_id, data: Optional[dict] = None) -> AuditLog:
    data = json.loads(canonical(data or {}))  # normalise so the stored JSON hashes identically later
    with _lock:
        last = session.exec(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)).first()
        seq = (last.seq + 1) if last else 1
        prev = last.entry_hash if last else GENESIS
        ts = now_iso()
        entry = AuditLog(
            seq=seq, ts=ts, actor=actor, action=action, entity=entity, entity_id=str(entity_id),
            data=data, prev_hash=prev,
            entry_hash=_hash(seq, ts, actor, action, entity, str(entity_id), data, prev),
        )
        session.add(entry)
        session.flush()
    return entry


def verify_chain(session: Session) -> dict:
    prev = GENESIS
    expected_seq = 1
    count = 0
    for e in session.exec(select(AuditLog).order_by(AuditLog.seq)).all():
        recomputed = _hash(e.seq, e.ts, e.actor, e.action, e.entity, e.entity_id, e.data, e.prev_hash)
        if e.seq != expected_seq or e.prev_hash != prev or e.entry_hash != recomputed:
            return {"ok": False, "entries": count, "first_bad_seq": e.seq}
        prev = e.entry_hash
        expected_seq += 1
        count += 1
    return {"ok": True, "entries": count, "first_bad_seq": None}
