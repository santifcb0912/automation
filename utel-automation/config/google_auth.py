"""Fabrica de credenciales de Google para Sheets y Drive.

Soporta dos modos:
- service_account: usa un JSON compartido de cuenta de servicio.
- oauth: autentica al usuario dueño del Sheets via navegador la primera vez y refresca token automáticamente.
"""

from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from loguru import logger

from config.settings import settings


# Scopes necesarios para leer/escribir Sheets y subir/borrar archivos en Drive.
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# Retorna credenciales de Google según el modo configurado (service_account u oauth).
# El modo se define via GOOGLE_AUTH_MODE en .env (default: service_account).
def get_google_credentials() -> Any:
    mode = settings.google_auth_mode.strip().lower()

    if mode == "oauth":
        return _get_oauth_credentials()

    logger.info("Usando Google Auth con Service Account")
    return ServiceAccountCredentials.from_service_account_file(
        settings.google_credentials_path,
        scopes=GOOGLE_SCOPES,
    )


# Carga token OAuth guardado, refresca si expiró, o abre navegador para autorizar la primera vez.
def _get_oauth_credentials() -> Any:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        from core.exceptions import GoogleAuthError
        raise GoogleAuthError(
            "Falta instalar google-auth-oauthlib. Ejecuta: pip install google-auth-oauthlib"
        ) from exc

    token_path = Path(settings.google_oauth_token_path)
    client_secret_path = Path(settings.google_oauth_client_secret_path)
    credentials = None

    # Intenta cargar token guardado de una autorización previa.
    if token_path.exists():
        credentials = UserCredentials.from_authorized_user_file(
            str(token_path),
            GOOGLE_SCOPES,
        )

    # Si el token es válido, lo usa directamente.
    if credentials and credentials.valid:
        logger.info("Usando Google OAuth con token local")
        return credentials

    # Si expiró pero tiene refresh_token, lo renueva sin abrir navegador.
    if credentials and credentials.expired and credentials.refresh_token:
        logger.info("Refrescando token OAuth de Google")
        credentials.refresh(Request())
    else:
        # No hay token válido ni refresh_token → abre navegador para autorizar.
        if not client_secret_path.exists():
            raise FileNotFoundError(
                f"No existe el cliente OAuth: {client_secret_path}. "
                "Descarga un OAuth Client ID tipo Desktop app y guardalo ahi."
            )

        logger.info("Abriendo navegador para autorizar Google OAuth")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path),
            GOOGLE_SCOPES,
        )
        credentials = flow.run_local_server(port=0)

    # Persiste el token (nuevo o refrescado) para no pedir autorización en cada ejecución.
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    logger.info(f"Token OAuth guardado en {token_path}")
    return credentials
