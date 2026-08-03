"""PrivacyHandler — maneja los checkboxes de privacidad y consentimiento."""

from playwright.async_api import Locator, Page
from loguru import logger


class PrivacyHandler:
    """Maneja la aceptacion de los checkboxes del formulario."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    # Plan A: marca con click directo cada checkbox del formulario que este desmarcado
    async def _check_direct(self) -> bool:
        cbs = self.form_scope.locator("input[type='checkbox']")
        count = await cbs.count()
        if count == 0:
            return False
        for i in range(count):
            cb = cbs.nth(i)
            try:
                if not await cb.evaluate("el => el.checked"):
                    await cb.dispatch_event("click")
            except Exception:
                logger.debug("dispatch_event fallo en checkbox directo")
        if await self._all_checked():
            logger.info("Checkboxes de privacidad marcados")
            return True
        return False

    # Intenta marcar los checkboxes: plan A directo, plan B fallback con selectores Chakra
    async def check(self) -> bool:
        if await self._check_direct():
            return True

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
                except Exception:
                    continue
            if await self._all_checked():
                logger.info("Checkboxes de privacidad marcados")
                return True

        logger.warning("Checkboxes de privacidad no encontrados")
        return False

    # Verifica que todos los checkboxes esten marcados. Si no hay checkbox, retorna True
    async def _all_checked(self) -> bool:
        try:
            return await self.form_scope.evaluate("""
                (root) => {
                    const cbs = root.querySelectorAll("input[type='checkbox']");
                    return cbs.length === 0 || Array.from(cbs).every((cb) => cb.checked);
                }
            """)
        except Exception:
            return False
