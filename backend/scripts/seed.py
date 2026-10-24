"""Seed the configured database with the demo ledger, rules and a released constitution v1."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sqlmodel import Session  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.seed_data import seed  # noqa: E402

if __name__ == "__main__":
    init_db()
    with Session(engine) as s:
        seed(s)
    print("seeded")
