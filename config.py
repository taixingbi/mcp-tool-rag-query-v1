# config.py
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent

_APP_ENV = (os.getenv("APP_ENV") or "dev").strip().lower()
if _APP_ENV not in ("dev", "qa", "prod"):
    _APP_ENV = "dev"

load_dotenv(_ROOT / ".env", override=True)
load_dotenv(_ROOT / f".env.{_APP_ENV}", override=True)

print("APP_ENV", _APP_ENV) 
print("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
print("CHROMA_API_KEY", os.getenv("CHROMA_API_KEY"))
print("CHROMA_TENANT", os.getenv("CHROMA_TENANT"))
print("CHROMA_DATABASE", os.getenv("CHROMA_DATABASE"))

def _chroma_env(key: str) -> str | None:
    """CHROMA_{key} or CHROMA_{key}_DEV/_QA/_PROD."""
    return os.getenv(f"CHROMA_{key}") or os.getenv(f"CHROMA_{key}_{_APP_ENV.upper()}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="dev", alias="APP_ENV")
    mcp_name: str = Field(default="mcp-rag-query-v1", alias="MCP_NAME")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    retrieval_k: int = Field(default=4, alias="RETRIEVAL_K")
    chroma_collection: str = Field(default="tb_all", alias="CHROMA_COLLECTION")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Chroma (from CHROMA_* or CHROMA_*_DEV/_QA/_PROD)
_chroma_api_key = _chroma_env("API_KEY")
_chroma_tenant = _chroma_env("TENANT")
_chroma_database = _chroma_env("DATABASE")

CHROMA_SETTINGS = {
    "api_key": _chroma_api_key,
    "tenant": _chroma_tenant,
    "database": _chroma_database,
    "collection_name": settings.chroma_collection,
}

CHAT_MODEL = settings.openai_model
RETRIEVAL_K = settings.retrieval_k
EMBEDDING_MODEL = settings.embedding_model


def get_chroma_client():
    if not (_chroma_api_key and _chroma_tenant and _chroma_database):
        raise RuntimeError(
            "Missing CHROMA_API_KEY / CHROMA_TENANT / CHROMA_DATABASE "
            f"(or CHROMA_*_{_APP_ENV.upper()}). Check .env and .env.{_APP_ENV}."
        )
    import chromadb
    return chromadb.CloudClient(
        api_key=_chroma_api_key,
        tenant=_chroma_tenant,
        database=_chroma_database,
    )
