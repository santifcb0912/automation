"""Punto de entrada FastAPI de UTEL Automation.

La lógica de la aplicación se movió a web/ (app factory + routes).
Este archivo es solo el entry point para uvicorn.

Para desarrollo:
    python main.py

Para producción:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

from web.app import create_app
from config.settings import settings

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level="info",
    )
