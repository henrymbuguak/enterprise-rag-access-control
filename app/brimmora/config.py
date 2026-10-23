"""All settings come from environment variables (.env via docker compose)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    pg_admin_dsn: str = "postgresql://brimmora:brimmora@localhost:5432/brimmora"
    pg_app_dsn: str = "postgresql://app_user:app_user@localhost:5432/brimmora"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "brimmora"
    minio_secret_key: str = "brimmora-secret"
    bucket: str = "corpus"

    opensearch_url: str = "http://localhost:9200"
    index_alias: str = "brimmora-chunks"
    kafka_brokers: str = "localhost:19092"
    events_topic: str = "minio-events"

    ollama_url: str = "http://localhost:11434"
    llm_model: str = "llama3.1:8b"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_version: str = "v1"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    chunk_words: int = 180
    chunk_overlap: int = 30
    min_relevance: float = 0.0

    region: str = "eu-west"
    tenant_id: str = "manufacturing"
    group_cache_ttl_seconds: int = 600
    jwt_secret: str = "dev-only-jwt-secret-change-me-in-production"
    dev_mode: bool = False
    prompt_version: str = "answer-v1"
    api_url: str = "http://localhost:8000"


settings = Settings()
