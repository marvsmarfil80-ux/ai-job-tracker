"""Application settings.

Values are read from three separate files in the repository root:
  .env       PostgreSQL variables only
  groq.env   Groq variables only
  app.env    backend-only secrets (API key, n8n_writer password) and flags
Real environment variables, if set, take precedence over the files.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

REPO_ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "groq.env", REPO_ROOT / "app.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433

    groq_api_key: SecretStr | None = None

    api_key: SecretStr
    n8n_writer_password: SecretStr
    groq_mock: bool = False

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def database_url(self) -> URL:
        """SQLAlchemy URL object (keeps the password out of string formatting)."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


