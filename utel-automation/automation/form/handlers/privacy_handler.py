"""PrivacyHandler — maneja el checkbox de políticas de privacidad."""

from playwright.async_api import Locator, Page
from loguru import logger


class PrivacyHandler:
    """Maneja la aceptación del checkbox de privacidad."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    async def check(self) -> bool:
        cb = self.form_scope.locator("input[type='checkbox']")
        if await cb.count() > 0:
            await cb.first.dispatch_event("click")
            if await self._is_checked():
                logger.info("Checkbox privacidad marcado")
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
                    if await self._is_checked():
                        logger.info("Checkbox privacidad marcado")
                        return True
                except Exception:
                    continue

        logger.warning("Checkbox privacidad no encontrado")
        return False

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
