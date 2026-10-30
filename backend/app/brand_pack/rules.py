"""Load rule packs from JSON.

The active pack is versioned. In the full system Sudiksha's database holds the
approved rules; until then this loads the drafted Indian-context pack.
Set LAYER_A_RULE_PACK to point at another file.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from .models import RulePack

DEFAULT_PACK = Path(__file__).parent / "data" / "rule_pack_india.json"


@lru_cache(maxsize=8)
def load_rule_pack(path: str | None = None) -> RulePack:
    p = Path(path or os.getenv("LAYER_A_RULE_PACK") or DEFAULT_PACK)
    return RulePack.model_validate(json.loads(p.read_text(encoding="utf-8")))
