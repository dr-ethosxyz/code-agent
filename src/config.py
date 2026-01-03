"""Configuration for Matter PR Reviewer Agent."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # App
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8080, env="PORT")

    # LLM - OpenRouter (multi-provider gateway)
    openrouter_api_key: Optional[str] = Field(default=None, env="OPENROUTER_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")

    # GitHub App Authentication
    github_app_id: Optional[str] = Field(default=None, env="GITHUB_APP_ID")
    github_private_key: Optional[str] = Field(default=None, env="GITHUB_PRIVATE_KEY")
    github_installation_id: Optional[str] = Field(default=None, env="GITHUB_INSTALLATION_ID")
    github_webhook_secret: Optional[str] = Field(default=None, env="GITHUB_WEBHOOK_SECRET")

    # Slack Integration
    slack_bot_token: Optional[str] = Field(default=None, env="SLACK_BOT_TOKEN")
    slack_signing_secret: Optional[str] = Field(default=None, env="SLACK_SIGNING_SECRET")
    slack_channel_id: Optional[str] = Field(default=None, env="SLACK_CHANNEL_ID")

    # Default Repository (for #123 shorthand in Slack)
    default_repo_owner: Optional[str] = Field(default=None, env="DEFAULT_REPO_OWNER")
    default_repo_name: Optional[str] = Field(default=None, env="DEFAULT_REPO_NAME")

    # Review Configuration
    review_model: str = Field(default="claude-sonnet-4", env="REVIEW_MODEL")
    max_files_per_review: int = Field(default=50, env="MAX_FILES_PER_REVIEW")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
