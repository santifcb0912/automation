from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    inconcert_user: str = Field(validation_alias="INCONCERT_USER")
    inconcert_password: str = Field(validation_alias="INCONCERT_PASSWORD")

    google_sheet_id: str = Field(validation_alias="GOOGLE_SHEET_ID")

    google_credentials_path: str = Field(
        default="./config/google_credentials.json",
        validation_alias="GOOGLE_CREDENTIALS_PATH",
    )

    google_auth_mode: Literal["service_account", "oauth", "user", "usuario"] = Field(
        default="service_account",
        validation_alias="GOOGLE_AUTH_MODE",
    )

    google_oauth_client_secret_path: str = Field(
        default="./config/google_oauth_client_secret.json",
        validation_alias="GOOGLE_OAUTH_CLIENT_SECRET_PATH",
    )

    google_oauth_token_path: str = Field(
        default="./config/google_oauth_token.json",
        validation_alias="GOOGLE_OAUTH_TOKEN_PATH",
    )

    google_drive_folder_name: str = Field(
        default="Capturas UTEL",
        validation_alias="GOOGLE_DRIVE_FOLDER_NAME",
    )

    lead_timeout_seconds: int = Field(
        default=120,
        ge=10,
        le=600,
        validation_alias="LEAD_TIMEOUT_SECONDS",
    )

    lead_retry_interval_seconds: int = Field(
        default=30,
        ge=5,
        le=120,
        validation_alias="LEAD_RETRY_INTERVAL_SECONDS",
    )

    max_workers: int = Field(
        default=3,
        ge=1,
        le=10,
        validation_alias="MAX_WORKERS",
    )

    port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        validation_alias="PORT",
    )

    screenshots_dir: str = "./screenshots"

    @field_validator("google_credentials_path", "google_oauth_client_secret_path", "google_oauth_token_path")
    @classmethod
    def resolve_relative_paths(cls, v: str) -> str:
        return str(Path(v).resolve()) if v.startswith(".") else v


settings = Settings()
