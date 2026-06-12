"""ScrollNavigator — scroll progresivo buscando formularios de contacto."""

from playwright.async_api import Page
from loguru import logger
from automation.common.script_loader import ScriptLoader


CONTACT_FORM_DETECTION_JS = """
(root) => {
    const CC = CODEX_COMMON;
    const fields = Array.from(root.querySelectorAll('input, select, textarea'))
        .filter((el) => {
            if (!CC.visible(el) || el.disabled || el.type === 'hidden') return false;
            return true;
        })
        .map(CC.keyFor);
    return fields.some(x => x.includes('email') || x.includes('correo'))
        && fields.some(x => x.includes('phone') || x.includes('tel'))
        && fields.some(x => x.includes('name') || x.includes('nombre'));
}
"""


async def detect_contact_form(page: Page) -> bool:
    """Verifica si hay un formulario de contacto visible en la página."""
    try:
        return await page.evaluate(CONTACT_FORM_DETECTION_JS)
    except Exception:
        return False


async def scroll_to_form_id(page: Page, form_id: str) -> bool:
    """Busca un formulario por ID y hace scroll hasta él."""
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


async def scroll_until_contact_form(page: Page, max_scrolls: int = 14) -> None:
    """Scrollea progresivamente hasta encontrar un formulario de contacto."""
    logger.info("Buscando formulario por scroll progresivo")
    for _ in range(max_scrolls):
        if await detect_contact_form(page):
            logger.info("Formulario de contacto visible encontrado")
            return
        await page.evaluate("window.scrollBy(0, Math.round(window.innerHeight * 0.75))")
        await page.wait_for_timeout(600)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1500)
