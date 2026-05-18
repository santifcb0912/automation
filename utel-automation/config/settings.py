# ============================================================
# config/settings.py
# Carga y valida todas las variables del archivo .env
# Equivalente a application.properties en Spring Boot
# ============================================================

import os                          # Para leer variables del sistema operativo
from dotenv import load_dotenv     # Para cargar el archivo .env
from loguru import logger          # Para mostrar mensajes en consola con formato

# Carga el archivo .env y convierte cada línea en variable de entorno
# Equivalente a @PropertySource en Spring Boot
load_dotenv()


class Settings:
    """
    Clase que contiene toda la configuración del sistema.
    Equivalente a una clase @Configuration en Spring Boot.
    Se instancia una sola vez al inicio del programa.
    """

    def __init__(self):
        # --- Credenciales de InConcert ---
        # Leemos el usuario desde el .env — nunca hardcodeado en el código
        self.inconcert_user: str = self._get("INCONCERT_USER")

        # Leemos la contraseña desde el .env
        self.inconcert_password: str = self._get("INCONCERT_PASSWORD")

        # --- Configuración de Google ---
        # ID del Google Sheets del mes actual
        self.google_sheet_id: str = self._get("GOOGLE_SHEET_ID")

        # Ruta al archivo JSON de credenciales de Google
        self.google_credentials_path: str = self._get(
            "GOOGLE_CREDENTIALS_PATH",
            default="./config/google_credentials.json"
        )

        # Modo de autenticacion de Google:
        # - service_account: usa config/google_credentials.json
        # - oauth: usa el navegador y guarda un token de usuario local
        self.google_auth_mode: str = self._get(
            "GOOGLE_AUTH_MODE",
            default="service_account"
        )

        # JSON de cliente OAuth tipo "Desktop app", descargado desde Google Cloud
        self.google_oauth_client_secret_path: str = self._get(
            "GOOGLE_OAUTH_CLIENT_SECRET_PATH",
            default="./config/google_oauth_client_secret.json"
        )

        # Token local generado tras autorizar tu usuario en el navegador
        self.google_oauth_token_path: str = self._get(
            "GOOGLE_OAUTH_TOKEN_PATH",
            default="./config/google_oauth_token.json"
        )

        # Nombre de la carpeta en Drive donde se guardan las capturas
        self.google_drive_folder_name: str = self._get(
            "GOOGLE_DRIVE_FOLDER_NAME",
            default="Capturas UTEL"
        )

        # --- Configuración del scraping ---
        # Tiempo máximo en segundos para esperar el lead (5 minutos = 300s)
        self.lead_timeout_seconds: int = int(
            self._get("LEAD_TIMEOUT_SECONDS", default="300")
        )

        # Tiempo en segundos entre cada reintento de búsqueda
        self.lead_retry_interval_seconds: int = int(
            self._get("LEAD_RETRY_INTERVAL_SECONDS", default="30")
        )

        # Número máximo de leads procesándose al mismo tiempo
        self.max_workers: int = int(
            self._get("MAX_WORKERS", default="3")
        )

        # Puerto donde corre la interfaz web
        self.port: int = int(self._get("PORT", default="8000"))

        # Carpeta donde se guardan temporalmente las capturas de pantalla
        self.screenshots_dir: str = "./screenshots"

        # Muestra en consola que la configuración se cargó correctamente
        logger.info("✅ Configuración cargada correctamente desde .env")

    def _get(self, key: str, default: str = None) -> str:
        """
        Lee una variable de entorno. Si no existe y no tiene valor por defecto,
        lanza un error claro indicando qué variable falta.
        Equivalente a @Value con validación en Spring Boot.
        """
        # Buscamos la variable en el sistema operativo
        value = os.getenv(key, default)

        # Si no existe y no hay valor por defecto, el sistema no puede continuar
        if value is None:
            logger.error(f"❌ Variable de entorno faltante: {key}")
            logger.error(f"   Agrégala al archivo .env: {key}=tu_valor_aqui")
            raise ValueError(f"Variable de entorno requerida no encontrada: {key}")

        return value


# Creamos una instancia única de Settings que se comparte en todo el proyecto
# Equivalente al Singleton pattern o @Bean con scope singleton en Spring
settings = Settings()
