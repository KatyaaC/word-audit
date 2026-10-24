"""Evaluation scoreboard: precision/recall of planted errors on the synthetic set (offline, mock LLM, hash embeddings
unless sentence-transformers is installed). Usage: python scripts/evaluate.py [data/synthetic_testset.json]"""
import json
import os
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlmodel import Session, SQLModel, select  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import make_engine  # noqa: E402
from app.engine.pipeline import run_engine  # noqa: E402
from app.models import Rule  # noqa: E402
from app.seed_data import seed  # noqa: E402
from app.services.llm import LLMRouter, MockClient  # noqa: E402


def label(f):
    if f.kind == "claim":
        return f"claim:{f.claim_status}"
    return f.kind


def main(path):
    items = json.load(open(path))
    eng = make_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    tp, fp, fn = defaultdict(int), defaultdict(int), defaultdict(int)
    with Session(eng) as s:
        seed(s)
        rules = s.exec(select(Rule).where(Rule.status == "active")).all()
        for it in items:
            out = run_engine(s, it["text"], rules, LLMRouter(MockClient()), today=date(2026, 10, 24), explain=False)
            pred, exp = {label(f) for f in out.findings}, set(it["expected"])
            for l in pred & exp:
                tp[l] += 1
            for l in pred - exp:
                fp[l] += 1
                print(f"  false alarm {it['id']}: {l}")
            for l in exp - pred:
                fn[l] += 1
                print(f"  missed      {it['id']}: {l}")
    print(f"\n{'label':24}{'TP':>4}{'FP':>4}{'FN':>4}{'precision':>11}{'recall':>8}")
    for l in sorted(set(tp) | set(fp) | set(fn)):
        p = tp[l] / (tp[l] + fp[l]) if tp[l] + fp[l] else float("nan")
        r = tp[l] / (tp[l] + fn[l]) if tp[l] + fn[l] else float("nan")
        print(f"{l:24}{tp[l]:>4}{fp[l]:>4}{fn[l]:>4}{p:>11.2f}{r:>8.2f}")
    T, P, N = sum(tp.values()), sum(fp.values()), sum(fn.values())
    print(f"\nOVERALL  n={len(items)} items  precision={T/(T+P) if T+P else 0:.2f}  recall={T/(T+N) if T+N else 0:.2f}")
    print("Synthetic data only: this does not prove real-world performance.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "data",
                                                            "synthetic_testset.json"))
