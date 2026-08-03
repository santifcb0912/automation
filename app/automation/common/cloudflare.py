"""CloudflareDetector — detecta si Cloudflare bloqueó la página."""

from playwright.async_api import Page
from loguru import logger


CLOUDFLARE_JS = """
() => {
    const text = String(document.body?.innerText || '').toLowerCase();
    return text.includes('why have i been blocked')
        || text.includes('cloudflare ray id')
        || text.includes('this website is using a security service');
}
"""


# Detecta si Cloudflare bloqueo la pagina evaluando texto clave del DOM
async def is_cloudflare_blocked(page: Page) -> bool:
    try:
        return await page.evaluate(CLOUDFLARE_JS)
    except Exception as e:
        logger.debug(f"No se pudo detectar Cloudflare: {e}")
        return False
