"""Administrador del ciclo de vida de Playwright.

Crea un contexto Chromium estable con viewport, locale y ajustes anti-deteccion 
usados tanto por las landing pages como por InConcert.
"""

import asyncio
import random
from typing import Optional
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright
)
from loguru import logger


class BrowserManager:
    """
    Maneja la creación y configuración del navegador Chromium.
    Aplica técnicas de stealth para que Cloudflare no detecte el bot.

    Equivalente a un @Component con @PreDestroy en Spring Boot —
    maneja recursos que necesitan abrirse y cerrarse limpiamente.

    Uso típico:
        browser_manager = BrowserManager()
        await browser_manager.launch()
        page = await browser_manager.new_page()
        await browser_manager.close()
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None

        self._browser: Optional[Browser] = None

        self._context: Optional[BrowserContext] = None

        logger.debug("🌐 BrowserManager creado")

    async def launch(self) -> None:
        """
        Abre el navegador con configuración de stealth mode.
        Debe llamarse antes de crear páginas.

        Stealth mode: conjunto de configuraciones que hacen que el browser
        parezca un usuario humano real en lugar de un bot automatizado.
        """
        logger.info("🚀 Iniciando navegador Chromium con stealth mode...")

        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=False,

            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),

            viewport={"width": 1366, "height": 768},

            locale="es-MX",

            timezone_id="America/Mexico_City",

            java_script_enabled=True,

            ignore_https_errors=True,
        )

        await self._context.add_init_script("""
            // Ocultamos que navigator.webdriver es True
            // Esta es la primera señal que busca Cloudflare
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Simulamos que hay plugins instalados (los browsers reales tienen plugins)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Simulamos idiomas del navegador como un humano real
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-MX', 'es', 'en-US', 'en'],
            });

            // Chrome real tiene chrome.runtime — el headless no lo tiene
            window.chrome = {
                runtime: {},
            };

            // Ocultamos la propiedad que identifica Chromium headless
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        logger.info("✅ Navegador iniciado con stealth mode activado")

    async def new_page(self) -> Page:
        """
        Crea y retorna una nueva pestaña del navegador.
        Equivalente a abrir una nueva pestaña en Chrome.

        Retorna un objeto Page de Playwright que se usa para
        navegar, hacer clicks, llenar formularios, etc.
        """
        if not self._context:
            raise RuntimeError("El navegador no está iniciado. Llama a launch() primero.")

        page = await self._context.new_page()

        logger.debug("📄 Nueva página creada")
        return page

    async def close(self) -> None:
        """
        Cierra el navegador y libera todos los recursos.
        Debe llamarse al terminar de usar el browser.
        Equivalente a @PreDestroy en Spring Boot.
        """
        try:
            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            logger.info("🔒 Navegador cerrado correctamente")

        except Exception as e:
            logger.warning(f"⚠️  Error cerrando navegador: {e}")

    @staticmethod
    async def human_delay(min_ms: int = 500, max_ms: int = 1500) -> None:
        """
        Espera un tiempo aleatorio entre acciones para simular comportamiento humano.
        Un bot que hace todo a la misma velocidad perfecta es fácil de detectar.

        Parámetros:
            min_ms: tiempo mínimo de espera en milisegundos
            max_ms: tiempo máximo de espera en milisegundos
        """
        delay_ms = random.randint(min_ms, max_ms)

        await asyncio.sleep(delay_ms / 1000)

    @staticmethod
    async def human_type(page: Page, selector: str, text: str) -> None:
        """
        Escribe texto en un campo como lo haría un humano — letra por letra
        con pequeñas pausas entre cada carácter.

        Un bot que escribe todo de golpe con fill() es detectable.
        Un humano escribe con pausas irregulares entre letras.

        Parámetros:
            page: la página de Playwright
            selector: selector CSS del campo de texto
            text: texto a escribir
        """
        await page.click(selector)

        await BrowserManager.human_delay(200, 600)

        await page.type(
            selector,
            text,
            delay=random.randint(50, 150)
        )
