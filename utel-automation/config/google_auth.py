"""Fabrica de credenciales de Google para Sheets y Drive.

El sistema puede usar service account u OAuth de usuario.
OAuth es la opcion adecuada cuando las capturas y escrituras deben hacerse con una cuenta Google que ya tiene acceso al Sheet corporativo.
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from loguru import logger

from config.settings import settings


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_google_credentials():
    """Retorna credenciales de Google usando service account u OAuth de usuario."""
    mode = (settings.google_auth_mode or "service_account").strip().lower()

    if mode in {"oauth", "user", "usuario"}:
        return _get_oauth_credentials()

    logger.info("Usando Google Auth con Service Account")
    return ServiceAccountCredentials.from_service_account_file(
        settings.google_credentials_path,
        scopes=GOOGLE_SCOPES,
    )


def _get_oauth_credentials():
    """Carga/refresca OAuth de usuario y abre navegador la primera vez."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Falta instalar google-auth-oauthlib. Ejecuta: "
            "pip install google-auth-oauthlib"
        ) from exc

    token_path = Path(settings.google_oauth_token_path)
    client_secret_path = Path(settings.google_oauth_client_secret_path)
    credentials = None

    if token_path.exists():
        credentials = UserCredentials.from_authorized_user_file(
            str(token_path),
            GOOGLE_SCOPES,
        )

    if credentials and credentials.valid:
        logger.info("Usando Google OAuth con token local")
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        logger.info("Refrescando token OAuth de Google")
        credentials.refresh(Request())
    else:
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

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    logger.info(f"Token OAuth guardado en {token_path}")
    return credentials
