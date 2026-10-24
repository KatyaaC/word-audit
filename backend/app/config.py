"""Application settings loaded from environment variables."""
import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in ("1", "true", "yes", "on")


class Settings(BaseModel):
    database_url: str = "sqlite:///./brandtrust.db"
    auto_create_tables: bool = True
    # Commercial LLM provider for Public and Internal content.
    llm_provider: str = "mock"
    anthropic_api_key: Optional[str] = None
    commercial_model: str = "claude-sonnet-4-20250514"
    # Local LLM provider; always used for Restricted content.
    local_llm_provider: str = "mock"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    # Embeddings backend.
    embedding_backend: str = "auto"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    related_similarity: Optional[float] = None
    # Passport signing key.
    signing_key_hex: Optional[str] = None
    signing_key_path: str = "./signing_key.hex"
    enable_demo_endpoints: bool = False
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    rs = os.getenv("RELATED_SIMILARITY")
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./brandtrust.db"),
        auto_create_tables=_flag("AUTO_CREATE_TABLES", True),
        llm_provider=os.getenv("LLM_PROVIDER", "mock"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        commercial_model=os.getenv("COMMERCIAL_MODEL", "claude-sonnet-4-20250514"),
        local_llm_provider=os.getenv("LOCAL_LLM_PROVIDER", "mock"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        embedding_backend=os.getenv("EMBEDDING_BACKEND", "auto"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
        related_similarity=float(rs) if rs else None,
        signing_key_hex=os.getenv("SIGNING_KEY_HEX"),
        signing_key_path=os.getenv("SIGNING_KEY_PATH", "./signing_key.hex"),
        enable_demo_endpoints=_flag("ENABLE_DEMO_ENDPOINTS", False),
        cors_origins=os.getenv("CORS_ORIGINS", "*"),
    )
