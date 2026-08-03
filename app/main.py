"""Arranca el servidor web.

Uso:
    uvicorn main:app --reload    # desarrollo
    uvicorn main:app             # producción
"""

from web.app import create_app

app = create_app()
