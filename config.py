# config.py
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load env early so APP_ENV and CHROMA_*_DEV / _QA / _PROD are available
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env")
_APP_ENV_RAW = (os.getenv("APP_ENV") or "dev").strip().lower()
_APP_ENV = _APP_ENV_RAW if _APP_ENV_RAW in ("dev", "qa", "prod") else "dev"
load_dotenv(_PROJECT_ROOT / f".env.{_APP_ENV}")


def _chroma_env(key: str) -> str | None:
    """CHROMA_API_KEY or CHROMA_API_KEY_DEV / _QA / _PROD for current env."""
    return os.getenv(f"CHROMA_{key}") or os.getenv(f"CHROMA_{key}_{_APP_ENV.upper()}")


class Settings(BaseSettings):
    """
    Single source of truth:
    - In dev: loads .env (optional)
    - In qa/prod: env vars injected by CI/infra (no .env needed)
    """
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Environment ----
    app_env: str = Field(default="dev", alias="APP_ENV")  # dev | qa | prod
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---- MCP ----
    mcp_name: str = Field(default="mcp-rag-query-v1", alias="MCP_NAME")

    # ---- LLM / RAG ----
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    retrieval_k: int = Field(default=4, alias="RETRIEVAL_K")

    # ---- Vector DB / Chroma ----
    chroma_mode: str = Field(default="local", alias="CHROMA_MODE")  # local|cloud
    chroma_host: str | None = Field(default=None, alias="CHROMA_HOST")
    chroma_port: int | None = Field(default=None, alias="CHROMA_PORT")
    chroma_api_key: str | None = Field(default=None, alias="CHROMA_API_KEY")
    chroma_tenant: str | None = Field(default=None, alias="CHROMA_TENANT")
    chroma_database: str | None = Field(default=None, alias="CHROMA_DATABASE")

    # Collection name (used as-is; set CHROMA_COLLECTION to override)
    chroma_collection: str = Field(default="tb_all", alias="CHROMA_COLLECTION")
    # If False, append _dev/_qa/_prod to collection name. Default True = use name as-is.
    chroma_collection_exact: bool = Field(default=True, alias="CHROMA_COLLECTION_EXACT")

    # ---- Safety toggles ----
    allow_write_tools: bool = Field(default=False, alias="ALLOW_WRITE_TOOLS")

    def resolved_collection(self) -> str:
        if self.chroma_collection_exact:
            return self.chroma_collection
        return f"{self.chroma_collection}_{self.app_env}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# convenient module-level exports for existing imports
settings = get_settings()
APP_ENV = settings.app_env

# RAG / query.py (Chroma from CHROMA_* or CHROMA_*_DEV/_QA/_PROD)
_chroma_api_key = _chroma_env("API_KEY")
_chroma_tenant = _chroma_env("TENANT")
_chroma_database = _chroma_env("DATABASE")
CHROMA_SETTINGS = {
    "api_key": _chroma_api_key,
    "tenant": _chroma_tenant,
    "database": _chroma_database,
    "collection_name": settings.resolved_collection(),
    "sparse_embedding_key": os.getenv("CHROMA_SPARSE_KEY", "sparse_embedding"),
}

CHAT_MODEL = settings.openai_model
RETRIEVAL_K = settings.retrieval_k
EMBEDDING_MODEL = settings.embedding_model


def get_chroma_client():
    """Return Chroma Cloud client. Uses CHROMA_* or CHROMA_*_DEV/_QA/_PROD for current APP_ENV."""
    if not (_chroma_api_key and _chroma_tenant and _chroma_database):
        raise RuntimeError(
            "Missing CHROMA_API_KEY / CHROMA_TENANT / CHROMA_DATABASE "
            f"(or CHROMA_*_{_APP_ENV.upper()}). Check .env and .env.{_APP_ENV} (APP_ENV={settings.app_env})."
        )
    import chromadb
    return chromadb.CloudClient(
        api_key=_chroma_api_key,
        tenant=_chroma_tenant,
        database=_chroma_database,
    )
