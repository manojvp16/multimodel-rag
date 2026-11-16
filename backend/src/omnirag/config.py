from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    GEMINI_API_KEY: str = ""

    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"

    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_DIMENSIONS: int = 768
    QDRANT_LOCAL: bool = True

    QDRANT_URL: str = "http://localhost:6333"

    QDRANT_COLLECTION: str = "omnirag_collection"

    APP_NAME: str = "OmniRAG"

    DEBUG: bool = True
    STORAGE_DIR: Path | None = None
    AUTH_USERNAME: str = ""
    AUTH_PASSWORD: str = ""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
