"""FormSubmitter — envía el formulario y valida el resultado."""

from playwright.async_api import Locator, Page
from loguru import logger


SUBMIT_BUTTONS = [
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Calcula tu beca')",
    "button:has-text('Enviar información')",
    "button:has-text('Enviar informacion')",
    "button:has-text('Continua por Whatsapp')",
    "button:has-text('Continúa por Whatsapp')",
    "button:has-text('Solicitar información')",
    "button:has-text('Solicitar informacion')",
    "button:has-text('Enviar')",
]


class FormSubmitter:
    """Busca el botón submit y envía el formulario."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    async def submit(self) -> bool:
        for selector in SUBMIT_BUTTONS:
            button = self.form_scope.locator(selector)
            if await button.count() == 0:
                continue
            try:
                await button.first.scroll_into_view_if_needed(timeout=5000)
                await button.first.click(force=True, timeout=5000)
                logger.info(f"Submit ejecutado con '{selector}'")
                return True
            except Exception as e:
                logger.debug(f"Submit fallo con '{selector}': {e}")

        logger.warning("No se encontro boton de submit")
        return False


class SubmissionValidator:
    """Valida que el envío fue exitoso (para flujos especiales como Universidad México)."""

    def __init__(self, page: Page):
        self.page = page

    async def validate_universidad_mexico(self, timeout_ms: int = 10000) -> bool:
        attempts = max(int(timeout_ms / 500), 1)
        for _ in range(attempts):
            status = await self._submission_status()
            if status.get("success"):
                logger.info(f"Universidad Mexico: envio confirmado: {status}")
                return True
            if status.get("blocking_error"):
                logger.warning(f"Universidad Mexico: error visible post-submit: {status}")
                return False
            await self.page.wait_for_timeout(500)

        logger.info("Universidad Mexico: sin error visible; se continua a InConcert")
        return True

    async def _submission_status(self) -> dict:
        try:
            return await self.page.evaluate("""
                () => {
                    const text = String(document.body?.innerText || '').toLowerCase();
                    const success = /gracias|thank you|registro exitoso|solicitud recibida|nos pondremos en contacto|datos enviados/.test(text);
                    const blocking = /campo requerido|campos requeridos|obligatorio|ingresa un|introduce un|correo invalido|teléfono invalido|telefono invalido/.test(text);
                    return { success, blocking_error: blocking };
                }
            """)
        except Exception:
            return {"success": False, "blocking_error": False}

    async def check_submission_fields(self, state: dict) -> bool:
        missing = [key for key in ["first_name", "email", "phone"] if not state.get(key)]
        if missing:
            logger.warning(f"Faltan campos de contacto: {missing}")
            return False
        if state.get("has_checkbox") and not state.get("checkbox_checked"):
            logger.warning("Checkbox de privacidad no quedo marcado")
            return False
        return True
