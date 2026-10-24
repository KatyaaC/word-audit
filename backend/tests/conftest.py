import os

os.environ["EMBEDDING_BACKEND"] = "hash"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SIGNING_KEY_HEX"] = "11" * 32
os.environ["ENABLE_DEMO_ENDPOINTS"] = "1"

import pytest  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import make_engine  # noqa: E402
from app.seed_data import seed  # noqa: E402
from app.services.llm import LLMRouter, MockClient  # noqa: E402


@pytest.fixture
def engine():
    e = make_engine("sqlite://")
    SQLModel.metadata.create_all(e)
    return e


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        seed(s)
        yield s


@pytest.fixture
def llm():
    return LLMRouter(MockClient())
