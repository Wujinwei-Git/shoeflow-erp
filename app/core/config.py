from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ShoeFlow ERP"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        default=(
            "mysql+pymysql://shoeflow:change_me@"
            "127.0.0.1:3306/shoeflow?charset=utf8mb4"
        ),
        description="SQLAlchemy database connection URL",
    )
    db_echo: bool = False

    deepseek_api_key: SecretStr | None = Field(
        default=None,
        description="DeepSeek API key",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        min_length=1,
    )
    deepseek_model: str = Field(
        default="deepseek-v4-flash",
        min_length=1,
    )
    deepseek_timeout_seconds: float = Field(
        default=30,
        ge=5,
        le=120,
    )
    agent_action_expire_minutes: int = Field(
        default=15,
        ge=1,
        le=120,
    )
    rag_knowledge_dir: str = Field(
        default="knowledge/erp_manual",
        min_length=1,
        description="ERP 操作手册 Markdown 目录",
    )
    rag_default_top_k: int = Field(
        default=3,
        ge=1,
        le=5,
    )
    rag_min_score: float = Field(
        default=0.08,
        ge=0,
        le=1,
    )
    rag_max_chunk_chars: int = Field(
        default=1400,
        ge=300,
        le=4000,
    )

    jwt_secret_key: str = Field(
        min_length=64,
        description="JWT signing secret",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(
        default=480,
        ge=15,
        le=10080,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
