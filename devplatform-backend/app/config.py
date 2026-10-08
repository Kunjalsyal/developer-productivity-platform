from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/devplatform"
    auto_create_schema: bool = True
    api_key: str | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    github_token: str | None = None
    notion_token: str | None = None

    embedding_backend: str = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    llm_provider: str = "fake"
    llm_model: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    llm_max_tokens: int = 1024

    top_k: int = 8
    max_context_chunks: int = 6
    min_similarity: float = 0.30
    min_supporting_chunks: int = 1

    max_file_bytes: int = 300_000
    max_chunk_chars: int = 6_000
    doc_chunk_chars: int = 1_200


@lru_cache
def get_settings() -> Settings:
    return Settings()
