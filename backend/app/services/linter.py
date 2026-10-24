"""Guideline linter for ambiguous and conflicting rules."""
import itertools
import re
from typing import Optional

from sqlmodel import Session, select

from ..models import Rule
from .embeddings import cosine, embed, nearest_rules, related_threshold
from .llm import LLMError

VAGUE_WORDS = {"professional", "friendly", "appropriate", "modern", "clean", "engaging", "natural", "warm",
               "approachable", "premium", "authentic", "relevant", "suitable", "tasteful", "bold", "energetic",
               "formal", "casual", "etc", "where possible", "as needed", "when appropriate"}


def _vague_hits(text: str) -> list:
    low = text.lower()
    return sorted(w for w in VAGUE_WORDS if re.search(rf"\b{re.escape(w)}\b", low))


def _ambiguity(rule: Rule, llm, k: int, classification: str, external_confirmed: bool) -> Optional[dict]:
    probes = list(rule.examples_pass or []) + list(rule.examples_fail or [])
    interps, verdict_runs = [], []
    for i in range(k):
        try:
            out = llm.run("interpret_rule", {"rule_text": rule.text, "probes": probes, "sample_index": i},
                          classification=classification, external_confirmed=external_confirmed, temperature=0.8)
        except LLMError:
            return None
        interps.append(str(out.get("interpretation", "")))
        verdict_runs.append(list(out.get("verdicts", [])))
    text_dis = 0.0
    if len(interps) > 1 and all(interps):
        vecs = embed(interps)
        pairs = list(itertools.combinations(range(len(vecs)), 2))
        text_dis = sum(1 - cosine(vecs[a], vecs[b]) for a, b in pairs) / len(pairs)
    verdict_dis = 0.0
    if probes and all(len(v) == len(probes) for v in verdict_runs):
        verdict_dis = sum(len({run[j] for run in verdict_runs}) > 1 for j in range(len(probes))) / len(probes)
    return {"text_disagreement": round(text_dis, 3), "verdict_disagreement": round(verdict_dis, 3),
            "score": round(max(text_dis, verdict_dis), 3), "interpretations": interps}


def _term_conflicts(rules: list) -> list:
    banned, required = {}, {}
    for r in rules:
        for t in (r.pattern or {}).get("terms", []):
            if r.kind == "banned_term":
                banned.setdefault(t.lower(), []).append(r)
            elif r.kind == "required_term":
                required.setdefault(t.lower(), []).append(r)
    out = []
    for term in banned.keys() & required.keys():
        for a in banned[term]:
            for b in required[term]:
                if a.rule_key != b.rule_key:
                    out.append({"kind": "conflict", "method": "term_overlap", "rules": [a.rule_key, b.rule_key],
                                "score": 1.0, "explanation": (
                                    f'"{term}" is banned by {a.rule_key} but required by '
                                    f'{b.rule_key}; no content can satisfy both.')})
    return out


def lint_rules(session: Session, llm, *, k: int = 3, ambiguity_threshold: float = 0.3, classification: str = "Internal",
               external_confirmed: bool = False) -> list:
    rules = session.exec(select(Rule).where(Rule.status.in_(["draft", "active"]))).all()
    findings = []
    for r in rules:
        vague = _vague_hits(r.text)
        amb = _ambiguity(r, llm, k, classification, external_confirmed)
        flagged = (amb and amb["score"] >= ambiguity_threshold) or (amb is None and len(vague) >= 2)
        if flagged:
            findings.append({
                "kind": "ambiguity", "method": "repeated_interpretation" if amb else "lexical", "rules": [r.rule_key],
                "score": amb["score"] if amb else None,
                "explanation": ("Different readings of this rule disagree, so reviewers will apply it inconsistently."
                                if amb else "Rule relies on vague wording."),
                "details": {"vague_terms": vague, **(amb or {})}})
    findings += _term_conflicts(rules)
    seen, thr = set(), related_threshold() - 0.1
    by_id = {r.id: r for r in rules}
    for r in rules:
        if r.embedding is None:
            continue
        for other, sim in nearest_rules(session, r.embedding, k=3, exclude_id=r.id):
            if other.id not in by_id or other.rule_key == r.rule_key or sim < thr:
                continue
            pair = tuple(sorted((r.id, other.id)))
            if pair in seen:
                continue
            seen.add(pair)
            try:
                votes = [llm.run("judge_conflict", {"rule_a": r.text, "rule_b": other.text},
                                 classification=classification, external_confirmed=external_confirmed,
                                 temperature=0.5) for _ in range(2)]
            except LLMError:
                continue
            if all(v.get("conflict") for v in votes):  # both repeated judgements must agree
                findings.append({"kind": "conflict", "method": "semantic_neighbours+llm_judge",
                                 "rules": [r.rule_key, other.rule_key], "score": round(sim, 3),
                                 "explanation": votes[0].get("reason") or "Rules appear to contradict each other.",
                                 "details": {"similarity": round(sim, 3)}})
    return findings
