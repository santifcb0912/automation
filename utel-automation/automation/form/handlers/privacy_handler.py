"""PrivacyHandler — maneja el checkbox de políticas de privacidad."""

from playwright.async_api import Locator, Page
from loguru import logger


class PrivacyHandler:
    """Maneja la aceptación del checkbox del boton privacidad en el form."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    # Intenta marcar el checkbox de privacidad: plan A directo, plan B fallback con selectores Chakra
    async def check(self) -> bool:
        cb = self.form_scope.locator("input[type='checkbox']")
        if await cb.count() > 0:
            try:
                await cb.first.dispatch_event("click")
                if await self._is_checked():
                    logger.info("Checkbox privacidad marcado")
                    return True
            except Exception:
                logger.debug("dispatch_event fallo en checkbox directo")

        for selector in [
            "label.chakra-checkbox",
            "label:has-text('Política de Privacidad')",
            "label:has-text('Politica de Privacidad')",
            "label:has-text('Privacidad')",
            ".chakra-checkbox__control",
            "[class*='checkbox']",
        ]:
            candidate = self.form_scope.locator(selector)
            count = await candidate.count()
            for i in range(count):
                item = candidate.nth(i)
                try:
                    await item.scroll_into_view_if_needed(timeout=3000)
                    await item.click(timeout=3000)
                    if await self._is_checked():
                        logger.info("Checkbox privacidad marcado")
                        return True
                except Exception:
                    continue

        logger.warning("Checkbox privacidad no encontrado")
        return False

    # Verifica si el checkbox esta marcado. Si no existe checkbox, retorna True (no requiere accion)
    async def _is_checked(self) -> bool:
        try:
            return await self.form_scope.evaluate("""
                (root) => {
                    const cb = root.querySelector("input[type='checkbox']");
                    return cb ? Boolean(cb.checked) : true;
                }
            """)
        except Exception:
            return False
