class CountryNotFoundError(ValueError):
    """País no encontrado en la configuración."""


class BrowserNotReadyError(RuntimeError):
    """El navegador no está iniciado o no se pudo lanzar."""


class GoogleAuthError(RuntimeError):
    """Error de autenticación con Google (Service Account u OAuth)."""
