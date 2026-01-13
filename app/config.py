"""Application configuration from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://localhost/telegram_mcp"

    # Telegram API (shared credentials for all users)
    telegram_api_id: int
    telegram_api_hash: str

    # Security
    encryption_key: str  # Fernet key for session encryption
    jwt_secret: str  # Secret for signing JWT tokens
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Server
    base_url: str = "http://localhost:8000"
    allowed_redirect_uris: str = "https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback"

    # Rate limiting
    rate_limit_per_minute: int = 100

    @property
    def redirect_uris_list(self) -> list[str]:
        """Parse allowed redirect URIs into a list."""
        return [uri.strip() for uri in self.allowed_redirect_uris.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
