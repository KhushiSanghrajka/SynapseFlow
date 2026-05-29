from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Synapse Flow Orchestrator"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./orchestration.db"
    inference_base_url: str = Field(default="https://models.inference.ai.azure.com", alias="INFERENCE_BASE_URL")
    github_models_endpoint: str = "https://models.github.ai/inference"
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    default_model: str = "gpt-4o"
    cors_origins: list[str] = ["http://localhost:5173"]
    mock_llm: bool = False
    telegram_bot_token: str | None = None
    telegram_agent_id: str | None = None
    demo_auto_seed: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
