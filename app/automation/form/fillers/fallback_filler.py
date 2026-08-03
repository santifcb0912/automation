"""FallbackFiller — strategy por defecto cuando pais/tipo no tiene implementacion.

Retorna un mensaje de error descriptivo para que llegue a Google Sheets,
en vez de lanzar excepcion o dejar el comportamiento indefinido.
"""

from typing import Optional

from automation.form.contracts.fill_context import FillContext
from automation.form.contracts.i_form_filler import IFormFiller


class FallbackFiller(IFormFiller):
    """Filler por defecto: reporta que el pais/tipo no tiene implementacion."""

    # Guarda la razon por la cual este filler no puede llenar el formulario
    def __init__(self, reason: str):
        self._reason = reason

    # No realiza preparacion alguna (strategy de error)
    async def prepare(self, form_type: str, level: str) -> None:
        pass

    # Retorna la razon del error para que llegue a Sheets y al frontend
    async def fill(self, ctx: FillContext) -> Optional[str]:
        return self._reason
