"""ScrollNavigator — scroll a formularios por ID."""

from playwright.async_api import Page
from loguru import logger


async def scroll_to_form_id(page: Page, form_id: str) -> bool:
    """Busca un formulario por ID y hace scroll hasta el."""
    locator = page.locator(f"#{form_id}")
    try:
        if await locator.count() == 0:
            return False
        await locator.first.scroll_into_view_if_needed(timeout=8000)
        await page.wait_for_timeout(1200)
        if await locator.first.is_visible():
            logger.info(f"Formulario por ID detectado: #{form_id}")
            return True
    except Exception as e:
        logger.debug(f"No se pudo enfocar #{form_id}: {e}")
    return False
