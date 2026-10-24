"""Embedding backends: sentence-transformers when available, deterministic hashing otherwise."""
import math
import re
import zlib
from functools import lru_cache

from sqlmodel import Session, select, text

from ..config import get_settings
from ..db import EMBED_DIM
from ..engine.textutil import content_tokens
from ..models import LedgerClaim, Rule


@lru_cache
def active_backend() -> str:
    mode = get_settings().embedding_backend
    if mode == "hash":
        return "hash"
    try:
        import sentence_transformers  # noqa: F401

        return "bge"
    except Exception:
        if mode == "bge":
            raise
        return "hash"


@lru_cache
def _bge_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def _hash_embed(t: str) -> list:
    v = [0.0] * EMBED_DIM
    for w in content_tokens(t):
        feats = [(w, 1.0)]
        if len(w) >= 4:
            feats += [("#" + w[i:i + 3], 0.35) for i in range(len(w) - 2)]
        for f, wt in feats:
            h = zlib.crc32(f.encode())
            v[h % EMBED_DIM] += wt if (h >> 16) & 1 else -wt
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts: list) -> list:
    if not texts:
        return []
    if active_backend() == "bge":
        return _bge_model().encode(texts, normalize_embeddings=True).tolist()
    return [_hash_embed(t) for t in texts]


def cosine(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))  # vectors are L2-normalised


def related_threshold() -> float:
    s = get_settings()
    if s.related_similarity is not None:
        return s.related_similarity
    return 0.78 if active_backend() == "bge" else 0.55


def _vec_literal(vec: list) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def nearest_ledger(session: Session, vec: list, k: int = 4) -> list:
    """Return the top-k ledger facts by cosine similarity."""
    if session.bind.dialect.name == "postgresql":
        rows = session.execute(
            text("SELECT id, 1 - (embedding <=> CAST(:v AS vector)) AS sim FROM ledger_claim "
                 "WHERE status <> 'superseded' AND embedding IS NOT NULL "
                 "ORDER BY embedding <=> CAST(:v AS vector) LIMIT :k"),
            {"v": _vec_literal(vec), "k": k},
        ).all()
        out = []
        for rid, sim in rows:
            out.append((session.get(LedgerClaim, rid), float(sim)))
        return out
    items = session.exec(select(LedgerClaim).where(LedgerClaim.status != "superseded")).all()
    scored = [(i, cosine(vec, i.embedding)) for i in items if i.embedding]
    return sorted(scored, key=lambda p: p[1], reverse=True)[:k]


def nearest_rules(session: Session, vec: list, k: int = 3, exclude_id=None) -> list:
    if session.bind.dialect.name == "postgresql":
        rows = session.execute(
            text("SELECT id, 1 - (embedding <=> CAST(:v AS vector)) AS sim FROM rule "
                 "WHERE status <> 'retired' AND embedding IS NOT NULL AND id <> COALESCE(:ex, -1) "
                 "ORDER BY embedding <=> CAST(:v AS vector) LIMIT :k"),
            {"v": _vec_literal(vec), "k": k, "ex": exclude_id},
        ).all()
        return [(session.get(Rule, rid), float(sim)) for rid, sim in rows]
    items = session.exec(select(Rule).where(Rule.status != "retired")).all()
    scored = [(i, cosine(vec, i.embedding)) for i in items if i.embedding and i.id != exclude_id]
    return sorted(scored, key=lambda p: p[1], reverse=True)[:k]
