"""Configuracion del sistema basada en variables de entorno.

Mapa mental si vienes de Spring Boot: esto equivale a application.properties mas un bean @ConfigurationProperties.
Los valores obligatorios vienen de .env; los opcionales definen autenticacion de Google, timeouts, workers y puerto.
"""

import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class Settings:
    """
    Clase que contiene toda la configuración del sistema.
    Equivalente a una clase @Configuration en Spring Boot.
    Se instancia una sola vez al inicio del programa.
    """

    def __init__(self):
        self.inconcert_user: str = self._get("INCONCERT_USER")

        self.inconcert_password: str = self._get("INCONCERT_PASSWORD")

        self.google_sheet_id: str = self._get("GOOGLE_SHEET_ID")

        self.google_credentials_path: str = self._get(
            "GOOGLE_CREDENTIALS_PATH",
            default="./config/google_credentials.json"
        )

        self.google_auth_mode: str = self._get(
            "GOOGLE_AUTH_MODE",
            default="service_account"
        )

        self.google_oauth_client_secret_path: str = self._get(
            "GOOGLE_OAUTH_CLIENT_SECRET_PATH",
            default="./config/google_oauth_client_secret.json"
        )

        self.google_oauth_token_path: str = self._get(
            "GOOGLE_OAUTH_TOKEN_PATH",
            default="./config/google_oauth_token.json"
        )

        self.google_drive_folder_name: str = self._get(
            "GOOGLE_DRIVE_FOLDER_NAME",
            default="Capturas UTEL"
        )

        self.lead_timeout_seconds: int = int(
            self._get("LEAD_TIMEOUT_SECONDS", default="120")
        )

        self.lead_retry_interval_seconds: int = int(
            self._get("LEAD_RETRY_INTERVAL_SECONDS", default="30")
        )

        self.max_workers: int = int(
            self._get("MAX_WORKERS", default="3")
        )

        self.port: int = int(self._get("PORT", default="8000"))

        self.screenshots_dir: str = "./screenshots"

        logger.info("✅ Configuración cargada correctamente desde .env")

    def _get(self, key: str, default: str = None) -> str:
        """
        Lee una variable de entorno. Si no existe y no tiene valor por defecto,
        lanza un error claro indicando qué variable falta.
        Equivalente a @Value con validación en Spring Boot.
        """
        value = os.getenv(key, default)

        if value is None:
            logger.error(f"❌ Variable de entorno faltante: {key}")
            logger.error(f"   Agrégala al archivo .env: {key}=tu_valor_aqui")
            raise ValueError(f"Variable de entorno requerida no encontrada: {key}")

        return value


settings = Settings()
