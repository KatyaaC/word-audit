"""ISO date helpers with safe parsing."""
from datetime import date
from typing import Optional


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None
