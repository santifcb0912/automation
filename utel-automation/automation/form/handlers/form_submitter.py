"""FormSubmitter — envía el formulario y valida el resultado."""

from typing import Optional

from playwright.async_api import Locator, Page
from loguru import logger


class FormSubmitter:
    """Busca el botón submit y envía el formulario."""

    def __init__(self, page: Page, form_scope: Locator, submit_buttons: list[str]):
        self.page = page
        self.form_scope = form_scope
        self._submit_buttons = submit_buttons

    async def submit(self) -> bool:
        for selector in self._submit_buttons:
            button = self.form_scope.locator(selector)
            if await button.count() == 0:
                continue
            try:
                await button.first.dispatch_event("click")
                logger.info(f"Submit ejecutado con '{selector}'")
                return True
            except Exception as e:
                logger.debug(f"Submit fallo con '{selector}': {e}")

        logger.warning("No se encontro boton de submit")
        return False


class SubmissionValidator:
    """Valida que los campos del formulario estén completos pre-submit."""

    def __init__(self, page: Page):
        self.page = page

    async def check_submission_fields(self, state: dict) -> Optional[str]:
        for name, key in [
            ("Area", "area"),
            ("Programa", "program"),
            ("Nombre", "first_name"),
            ("Email", "email"),
            ("Telefono", "phone"),
        ]:
            if not state.get(key):
                return f"Campo {name}: no se pudo completar"
        if state.get("has_checkbox") and not state.get("checkbox_checked"):
            return "Checkbox de privacidad: no quedo marcado"
        return None
