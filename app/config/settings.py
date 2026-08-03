from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Literal
from loguru import logger


class Settings(BaseSettings):
    
    # Lee variables de entorno desde .env con Pydantic v2.
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # --- InConcert ---
    # Credenciales de login compartidas para todas las ligas de InConcert.
    inconcert_user: str = Field(validation_alias="INCONCERT_USER")
    inconcert_password: str = Field(validation_alias="INCONCERT_PASSWORD")

    # --- Google Sheets ---
    # ID del documento de Google Sheets del mes en curso (sin .env no arranca).
    google_sheet_id: str = Field(validation_alias="GOOGLE_SHEET_ID")

    # --- Google Auth ---
    # Ruta al JSON de Service Account (modo service_account) o al cliente OAuth (modo oauth).
    google_credentials_path: str = Field(
        default="./config/data/google_credentials.json",
        validation_alias="GOOGLE_CREDENTIALS_PATH",
    )

    # service_account comparte una cuenta fija; oauth autentica al usuario dueño del Sheets.
    google_auth_mode: Literal["service_account", "oauth"] = Field(
        default="service_account",
        validation_alias="GOOGLE_AUTH_MODE",
    )

    # JSON de cliente OAuth (solo para modo oauth) — se descarga de Google Cloud Console.
    google_oauth_client_secret_path: str = Field(
        default="./config/data/google_oauth_client_secret.json",
        validation_alias="GOOGLE_OAUTH_CLIENT_SECRET_PATH",
    )

    # Token OAuth generado tras la primera autorización — se recarga automáticamente.
    google_oauth_token_path: str = Field(
        default="./config/data/google_oauth_token.json",
        validation_alias="GOOGLE_OAUTH_TOKEN_PATH",
    )

    # --- Pipeline ---
    # Tiempo máximo (s) esperando que un lead llegue a InConcert tras llenar el formulario.
    lead_timeout_seconds: int = Field(
        default=120,
        ge=10,     # mínimo 10s
        le=600,    # máximo 600s (10 min)
        validation_alias="LEAD_TIMEOUT_SECONDS",
    )

    # Máximo de leads procesándose en paralelo — 1 evita saturación local.
    max_workers: int = Field(
        default=3,
        ge=1,     # mínimo 1 (procesamiento secuencial)
        le=10,    # máximo 10 (evita saturar Chrome/APIs)
        validation_alias="MAX_WORKERS",
    )

    # --- Servidor ---
    # Puerto local donde corre la interfaz web (FastAPI + uvicorn).
    port: int = Field(
        default=8000,
        ge=1024,   # mínimo 1024 (puertos no privilegiados)
        le=65535,  # máximo 65535 (rango TCP/IP)
        validation_alias="PORT",
    )

    # Convierte rutas relativas (./config/...) a absolutas para que pathlib funcione desde cualquier CWD.
    @field_validator("google_credentials_path", "google_oauth_client_secret_path", "google_oauth_token_path")
    @classmethod
    def resolve_relative_paths(cls, v: str) -> str:
        return str(Path(v).resolve()) if v.startswith(".") else v

    # Advierte al arranque si falta el archivo de credenciales según el modo de auth elegido.
    @model_validator(mode="after")
    def validate_auth_files(self) -> "Settings":
        if self.google_auth_mode == "service_account":
            path = Path(self.google_credentials_path)
            if not path.exists():
                logger.warning(f"Service Account no encontrada en: {path}")
        elif self.google_auth_mode == "oauth":
            path = Path(self.google_oauth_client_secret_path)
            if not path.exists():
                logger.warning(f"Cliente OAuth no encontrado en: {path}")
        return self


# Singleton importable desde cualquier módulo: from config.settings import settings
settings = Settings()
