import asyncio
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from loguru import logger

from core.exceptions import BrowserNotReadyError


# Script anti-deteccion que oculta las señales de Chrome automatizado
_STEALTH_INIT_SCRIPT = """
    // Oculta que navigator.webdriver es True
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

    // Ocultamos la propiedad que identifica Chrome headless
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
"""

# Argumentos de lanzamiento que ocultan el modo automatizado de Chrome
_BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-accelerated-2d-canvas",
    "--no-first-run",
    "--no-zygote",
    "--disable-gpu",
    "--disable-blink-features=AutomationControlled",
    "--start-maximized",
]

# User agent fijo de Chrome real para evitar el fingerprinting
_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class BrowserManager:
    """
    Maneja la creación y configuración de Google Chrome.
    Aplica técnicas de stealth para que Cloudflare no detecte el bot.


    Uso típico:
        browser_manager = BrowserManager()
        await browser_manager.launch()
        page = await browser_manager.new_page()
        await browser_manager.close()
    """

    # Inicializa el gestor sin abrir el navegador — llama a launch() despues
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        logger.debug("BrowserManager creado")

    # Abre Chrome con perfil persistente y configuracion anti-deteccion Cloudflare
    async def launch(self) -> None:
        logger.info("Iniciando Chrome con stealth mode...")

        self._playwright = await async_playwright().start()
        self._context = await self._launch_persistent_context()
        await self._context.add_init_script(_STEALTH_INIT_SCRIPT)

        logger.info("Chrome iniciado con stealth mode activado")

    # Lanza el contexto persistente de Chrome con perfil y configuracion anti-deteccion
    async def _launch_persistent_context(self) -> BrowserContext:
        return await self._playwright.chromium.launch_persistent_context(
            user_data_dir="./chrome_profile",
            channel="chrome",
            headless=False,
            no_viewport=True,
            args=_BROWSER_ARGS,
            user_agent=_CHROME_USER_AGENT,
            locale="es-MX",
            timezone_id="America/Mexico_City",
            ignore_https_errors=True,
        )

    # Abre una nueva pestana en el navegador ya iniciado
    async def new_page(self) -> Page:
        if not self._context:
            raise BrowserNotReadyError("El navegador no está iniciado. Llama a launch() primero.")

        page = await self._context.new_page()

        # Auto-descarta dialogos JS que cuelgan las operaciones de Playwright
        page.on("dialog", lambda dialog: asyncio.create_task(self._dismiss_dialog(dialog)))
        # Loguea errores JS del renderer para diagnosticar colgadas
        page.on("console", lambda msg: logger.debug(f"JS console ({msg.type}): {msg.text}") if msg.type == "error" else None)

        logger.debug("Nueva pagina creada")
        return page

    # Descarta un dialogo JS y lo reporta en el log
    async def _dismiss_dialog(self, dialog) -> None:
        logger.warning(f"Dialogo JS detectado: {dialog.message}")
        try:
            await dialog.dismiss()
        except Exception as e:
            logger.debug(f"No se pudo descartar dialogo: {e}")

    # Cierra el navegador y libera recursos. Tolerante a errores parciales
    async def close(self) -> None:
        try:
            if self._context:
                await self._context.close()
                self._context = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            logger.info("Navegador cerrado correctamente")

        except Exception as e:
            logger.warning(f"Error cerrando navegador: {e}")


