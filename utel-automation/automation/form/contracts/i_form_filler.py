"""IFormFiller — interfaz comun para todas las strategies de llenado de formularios."""

from typing import Optional, Protocol

from automation.form.contracts.fill_context import FillContext


class IFormFiller(Protocol):
    """Contrato que toda strategy de formulario debe implementar."""

    # Prepara el formulario (abrir panel lateral, etc.) segun el tipo y nivel.
    async def prepare(self, form_type: str, level: str) -> None:
        ...

    # Llena el formulario completo. Retorna None si tuvo exito, o un string con la razon del error.
    async def fill(self, ctx: FillContext) -> Optional[str]:
        ...
