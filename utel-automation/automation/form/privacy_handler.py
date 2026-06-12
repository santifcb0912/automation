"""PrivacyHandler — maneja el checkbox de políticas de privacidad."""

from playwright.async_api import Locator, Page
from loguru import logger


class PrivacyHandler:
    """Maneja la aceptación del checkbox de privacidad."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    async def check(self) -> bool:
        candidates = [
            self.form_scope.locator("input[type='checkbox']"),
            self.form_scope.locator("label:has-text('Política de Privacidad')"),
            self.form_scope.locator("label:has-text('Politica de Privacidad')"),
            self.form_scope.locator("label:has-text('Privacidad')"),
            self.form_scope.locator(".chakra-checkbox__control"),
            self.form_scope.locator("[class*='checkbox']"),
        ]

        for candidate in candidates:
            count = await candidate.count()
            for i in range(count):
                item = candidate.nth(i)
                try:
                    await item.scroll_into_view_if_needed(timeout=3000)
                    await item.click(force=True, timeout=3000)
                    if await self._is_checked():
                        logger.info("Checkbox privacidad marcado")
                        return True
                except Exception:
                    continue

        try:
            checked = await self.form_scope.evaluate("""
                (root) => {
                    const cb = Array.from(root.querySelectorAll("input[type='checkbox']"))[0];
                    if (cb) {
                        cb.checked = true;
                        cb.setAttribute('checked', 'checked');
                        cb.dispatchEvent(new Event('input', { bubbles: true }));
                        cb.dispatchEvent(new Event('change', { bubbles: true }));
                        cb.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        if (!cb.checked) cb.checked = true;
                        cb.dispatchEvent(new Event('change', { bubbles: true }));
                        return cb.checked;
                    }
                    const target = Array.from(root.querySelectorAll('label, span, div, p'))
                        .find((el) => /privacidad|politica|política/i.test(el.textContent || ''));
                    if (!target) return false;
                    target.click();
                    return true;
                }
            """)
            if checked:
                logger.info("Checkbox privacidad marcado por DOM")
                return True
        except Exception as e:
            logger.debug(f"Checkbox por DOM fallo: {e}")

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
