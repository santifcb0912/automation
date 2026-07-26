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
from automation.form.engine.form_utils import canonical_level


MAX_TARJETA_RETRIES = 5
RETRY_DELAY_MS = 2500
SOFT_NETWORK_TIMEOUT_MS = 15000


class ProgramSearchEngine:
    """Busca y navega a LP de producto via input de busqueda."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    #Hook: cada pais implementa como obtener el input de busqueda
    async def _locate_search_input(self):
        return self.page.locator("input[placeholder='Buscar programa']")

    #Hook: cada pais implementa como seleccionar y clickear el resultado
    async def _select_and_click_result(self, query: str) -> bool:
        result = self.page.locator(f"a.chakra-link[href*='{query.lower()}']").first
        if await result.count() == 0:
            return False
        await result.click(timeout=5000)
        return True

    #Escribe area en input programa y clickea un programa al azar del dropdown
    async def select_random_program(self, level: str) -> bool:
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


    # Abre LP de producto desde pagina generica. Reintenta hasta 5 veces si Cloudflare bloquea
    async def open_tarjeta_product(self, level: str, original_url: str) -> bool:
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


    #Template method: escribe query en input, espera dropdown, clickea resultado
    async def search_program_from_generic_page(self, level: str, original_url: str) -> bool:
        query = canonical_level(level)
        search_input = await self._locate_search_input()
        if await search_input.count() == 0:
            logger.warning("Tarjeta: no se encontro input de busqueda")
            return False
        await search_input.first.scroll_into_view_if_needed(timeout=5000)
        await search_input.first.fill(query, timeout=5000)
        await self.page.wait_for_timeout(3000)
        clicked = await self._select_and_click_result(query)
        if not clicked:
            logger.info(f"Tarjeta: sin resultados para '{query}'")
            return False
        return await self._wait_for_url_change(original_url)


     #Recarga pagina actual o navega a URL original.
    async def _reload_or_navigate(self, url: str) -> None:
        try:
            if self.page.url != url:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            else:
                await self.page.reload(wait_until="domcontentloaded", timeout=45000)
            await self._soft_wait_network()
            await self.page.wait_for_timeout(1500)
        except Exception as e:
            logger.debug(f"Tarjeta: no se pudo reabrir LP: {e}")


    #Espera networkidle con timeout suave.
    async def _soft_wait_network(self) -> None:
        try:
            await self.page.wait_for_load_state("networkidle", timeout=SOFT_NETWORK_TIMEOUT_MS)
        except Exception:
            pass


    #Espera hasta timeout_ms a que la URL cambie de la original
    async def _wait_for_url_change(self, original_url: str, timeout_ms: int = 10000) -> bool:
        attempts = max(int(timeout_ms / 400), 1)
        for _ in range(attempts):
            if self.page.url != original_url:
                return True
            await self.page.wait_for_timeout(400)
        return False

    #Factory: retorna la subclase segun pais
    @staticmethod
    def for_country(country: str, page: Page, form_scope: Locator) -> 'ProgramSearchEngine':
        if country == "argentina":
            return ArgentinaProgramSearchEngine(page, form_scope)
        return ProgramSearchEngine(page, form_scope)


#Argentina: clickea lupa si input no esta visible
class ArgentinaProgramSearchEngine(ProgramSearchEngine):

    #Click lupa si input oculto, luego retorna el input
    async def _locate_search_input(self):
        search_input = self.page.locator("input[placeholder='Buscar programa']")
        if await search_input.count() == 0:
            logger.info("Argentina: clickeando lupa para revelar input")
            await self.page.evaluate("""
                const p = document.querySelector("path[d*='21.07']");
                const btn = p?.closest("button, [role='button']");
                if (btn) btn.click();
            """)
            await self.page.wait_for_timeout(3000)
            search_input = self.page.locator("input[placeholder='Buscar programa']")
        return search_input

    #Elige resultado al azar del dropdown de Sugerencias
    async def _select_and_click_result(self, query: str) -> bool:
        dropdown = self.page.locator("ul[role='list']:has(span:has-text('Sugerencias'))")
        options = dropdown.locator("a.chakra-link")
        count = await options.count()
        if count == 0:
            return False
        idx = random.randint(0, count - 1)
        await self.page.evaluate("el => el.click()", await options.nth(idx).element_handle())
        return True


