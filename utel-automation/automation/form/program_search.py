"""ProgramSearchEngine — busca programas en LPs y navega a LP de producto.

Flujo Plan B (Tarjeta):
1. Escribir area de interes en input[placeholder="Buscar programa"]
2. Esperar 3s a que aparezca el dropdown
3. Click en a.chakra-link con el programa
4. Verificar cambio de URL y Cloudflare
5. Reintentar hasta 5 veces si Cloudflare bloquea

select_random_program():
Usado por lateral/footer durante el llenado del formulario.
Escribe el area en el input programa y selecciona un programa al azar via teclado.
"""

import random

from playwright.async_api import Page, Locator
from loguru import logger

from automation.common.cloudflare import is_cloudflare_blocked
from automation.form.form_utils import canonical_level


MAX_TARJETA_RETRIES = 5
RETRY_DELAY_MS = 2500
SOFT_NETWORK_TIMEOUT_MS = 15000


class ProgramSearchEngine:
    """Busca y navega a LP de producto via input de busqueda."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    async def select_random_program(self, level: str) -> bool:
        """Escribe area en input programa y clickea un programa al azar del dropdown."""
        query = canonical_level(level)
        inp = self.form_scope.locator("input[name='program']")
        if await inp.count() == 0:
            return False
        await inp.first.scroll_into_view_if_needed(timeout=5000)
        await inp.first.fill(query, timeout=5000)
        await self.page.wait_for_timeout(3000)
        options = self.page.locator("div[id^='result-']")
        count = await options.count()
        if count == 0:
            return False
        idx = random.randint(0, count - 1)
        await options.nth(idx).click()
        await self.page.wait_for_timeout(1500)
        return True

    async def open_tarjeta_product(self, level: str, original_url: str) -> bool:
        """Abre LP de producto desde pagina generica. Reintenta hasta 5 veces si Cloudflare bloquea."""
        for attempt in range(1, MAX_TARJETA_RETRIES + 1):
            logger.info(f"Tarjeta: intento {attempt}/{MAX_TARJETA_RETRIES}")
            if self.page.url != original_url or attempt > 1:
                await self._reload_or_navigate(original_url)
            opened = await self.search_program_from_generic_page(level, original_url)
            if opened:
                if await is_cloudflare_blocked(self.page):
                    logger.warning("Tarjeta: Cloudflare detectado, reintentando")
                    await self.page.wait_for_timeout(RETRY_DELAY_MS)
                    continue
                logger.info(f"Tarjeta: LP de producto abierta en intento {attempt}")
                return True
            await self.page.wait_for_timeout(RETRY_DELAY_MS)
        return False

    async def search_program_from_generic_page(self, level: str, original_url: str) -> bool:
        """Escribe area de interes en input, espera dropdown, clickea un resultado."""
        query = canonical_level(level)
        search_input = self.page.locator("input[placeholder='Buscar programa']")
        if await search_input.count() == 0:
            logger.warning("Tarjeta: no se encontro input de busqueda")
            return False
        await search_input.first.scroll_into_view_if_needed(timeout=5000)
        await search_input.first.fill(query, timeout=5000)
        await self.page.wait_for_timeout(3000)
        result = self.page.locator(f"a.chakra-link[href*='{query.lower()}']").first
        if await result.count() == 0:
            logger.info(f"Tarjeta: sin resultados para '{query}'")
            return False
        await result.click(timeout=5000)
        return await self._wait_for_url_change(original_url)

    async def _reload_or_navigate(self, url: str) -> None:
        """Recarga pagina actual o navega a URL original."""
        try:
            if self.page.url != url:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            else:
                await self.page.reload(wait_until="domcontentloaded", timeout=45000)
            await self._soft_wait_network()
            await self.page.wait_for_timeout(1500)
        except Exception as e:
            logger.debug(f"Tarjeta: no se pudo reabrir LP: {e}")

    async def _soft_wait_network(self) -> None:
        """Espera networkidle con timeout suave."""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=SOFT_NETWORK_TIMEOUT_MS)
        except Exception:
            pass

    async def _wait_for_url_change(self, original_url: str, timeout_ms: int = 10000) -> bool:
        """Espera hasta timeout_ms a que la URL cambie de la original."""
        attempts = max(int(timeout_ms / 400), 1)
        for _ in range(attempts):
            if self.page.url != original_url:
                return True
            await self.page.wait_for_timeout(400)
        return False
