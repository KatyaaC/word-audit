"""Precision and recall of Layer A on the synthetic test items.

Usage:  python eval_layer_a.py [path/to/items.json]

Each item lists the rule IDs we expect to fire. Matching is by rule ID as a
multiset, so two expected BAN-007 hits need two BAN-007 findings.
Results on synthetic data do not prove real-world performance.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from layer_a import CheckRequest, load_rule_pack, run_layer_a

DEFAULT_ITEMS = Path(__file__).parent / "layer_a" / "data" / "synthetic_rule_tone_a11y.json"


def main(path: str | None = None) -> int:
    items = json.loads(Path(path or DEFAULT_ITEMS).read_text(encoding="utf-8"))["items"]
    pack = load_rule_pack()
    totals = Counter()
    by_cat: dict[str, Counter] = defaultdict(Counter)
    clean_items = clean_with_alarm = 0
    rows = []

    for it in items:
        req = CheckRequest(
            text=it.get("text", ""),
            html=it.get("html"),
            colour_pairs=it.get("colour_pairs", []),
            images=it.get("images", []),
        )
        got = Counter(f.rule_id for f in run_layer_a(req, pack))
        exp = Counter(it["expected"])
        tp = sum((got & exp).values())
        fp = sum((got - exp).values())
        fn = sum((exp - got).values())
        for c in (totals, by_cat[it["category"]]):
            c["tp"] += tp
            c["fp"] += fp
            c["fn"] += fn
        if not exp:
            clean_items += 1
            clean_with_alarm += int(fp > 0)
        status = "ok" if fp == 0 and fn == 0 else "MISS"
        rows.append((it["id"], status, sorted(exp.elements()), sorted(got.elements())))

    def pr(c: Counter) -> tuple[float, float]:
        p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 1.0
        r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 1.0
        return p, r

    print(f"Layer A evaluation on {len(items)} synthetic items (rule pack {pack.version})\n")
    for rid, status, exp, got in rows:
        print(f"  {rid:4} {status:4} expected={exp} got={got}")
    print()
    for cat, c in sorted(by_cat.items()):
        p, r = pr(c)
        print(f"  {cat:14} precision={p:.2f} recall={r:.2f}  (tp={c['tp']} fp={c['fp']} fn={c['fn']})")
    p, r = pr(totals)
    print(f"\n  OVERALL        precision={p:.2f} recall={r:.2f}  (tp={totals['tp']} fp={totals['fp']} fn={totals['fn']})")
    print(f"  Clean items with a false alarm: {clean_with_alarm} of {clean_items}")
    return 0 if totals["fp"] == 0 and totals["fn"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
