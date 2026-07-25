"""ContactFieldFiller — llena campos de contacto (nombre, email, telefono)."""

from typing import Optional
from playwright.async_api import Locator, Page
from loguru import logger


class ContactFieldFiller:
    """Encarcado de poner los datos en los campos de contacto en formularios."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    # Busca el primer campo que exista en el DOM y lo llena con el valor dado
    async def set_input(self, selectors: list[str], value: str, label: str) -> bool:
        field = await self._first_existing(selectors)
        if not field:
            logger.warning(f"Campo '{label}' no encontrado")
            return False

        try:
            await field.scroll_into_view_if_needed(timeout=5000)
            await field.fill(value, timeout=5000)
            current = await field.input_value(timeout=3000)
            if current.strip():
                logger.info(f"Campo '{label}' completado")
                return True
        except Exception as e:
            logger.debug(f"Fill directo fallo para '{label}': {e}")

        logger.warning(f"No se pudo completar '{label}'")
        return False

    # Llena el campo nombre con un nombre ficticio
    async def set_name(self, fake_name: str) -> bool:
        return await self.set_input(
            ["#first_name", "input[name='first_name']", "input[name='name']", "input[name*='nombre' i]", "input[id*='nombre' i]"],
            fake_name,
            "nombre",
        )

    # Llena el campo email con el email de prueba del lead
    async def set_email(self, test_email: str) -> bool:
        return await self.set_input(
            ["#email", "input[name='email']", "input[type='email']", "input[name*='correo' i]", "input[id*='correo' i]"],
            test_email,
            "email",
        )

    # Llena el campo telefono con un telefono ficticio
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

    # Retorna el primer locator del DOM que coincida con algun selector de la lista, o None
    async def _first_existing(self, selectors: list[str]) -> Optional[Locator]:
        for selector in selectors:
            locator = self.form_scope.locator(selector)
            try:
                if await locator.count() > 0:
                    return locator.first
            except Exception:
                continue
        return None
