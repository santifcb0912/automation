"""ContactFieldFiller — llena campos de contacto (nombre, email, teléfono)."""

from typing import Optional
from playwright.async_api import Locator, Page
from loguru import logger


class ContactFieldFiller:
    """Llena campos de contacto en formularios."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    async def set_input(self, selectors: list[str], value: str, label: str) -> bool:
        field = await self._first_existing(selectors)
        if not field:
            logger.warning(f"Campo '{label}' no encontrado")
            return False

        try:
            await field.scroll_into_view_if_needed(timeout=5000)
            await field.fill(value, force=True, timeout=5000)
            current = await field.input_value(timeout=3000)
            if current.strip():
                logger.info(f"Campo '{label}' completado")
                return True
        except Exception as e:
            logger.debug(f"Fill directo fallo para '{label}': {e}")

        return await self._set_value_dom(field, value, label)

    async def set_name(self, fake_name: str) -> bool:
        return await self.set_input(
            ["#first_name", "input[name='first_name']", "input[name='name']", "input[name*='nombre' i]", "input[id*='nombre' i]"],
            fake_name,
            "nombre",
        )

    async def set_email(self, test_email: str) -> bool:
        return await self.set_input(
            ["#email", "input[name='email']", "input[type='email']", "input[name*='correo' i]", "input[id*='correo' i]"],
            test_email,
            "email",
        )

    async def set_phone(self, fake_phone: str) -> bool:
        return await self.set_input(
            [
                "#phone", "input[name='phone']", "input[type='tel']",
                "input[name*='telefono' i]", "input[id*='telefono' i]",
                "input[name*='celular' i]", "input[id*='celular' i]",
                "input[name*='mobile' i]",
            ],
            fake_phone,
            "telefono",
        )

    async def _set_value_dom(self, field: Locator, value: str, label: str) -> bool:
        try:
            await field.evaluate(
                """
                (el, value) => {
                    const proto = el.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (descriptor && descriptor.set) descriptor.set.call(el, value);
                    else el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                }
                """,
                value,
            )
            logger.info(f"Campo '{label}' completado por DOM")
            return True
        except Exception as e:
            logger.warning(f"No se pudo completar '{label}': {e}")
            return False

    async def _first_existing(self, selectors: list[str]) -> Optional[Locator]:
        for selector in selectors:
            locator = self.form_scope.locator(selector)
            try:
                if await locator.count() > 0:
                    return locator.first
            except Exception:
                continue
        return None
