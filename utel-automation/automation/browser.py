# ============================================================
# automation/browser.py
# Maneja el ciclo de vida del navegador Playwright
# Aplica stealth mode para evitar detección por Cloudflare
# Equivalente a un @Component que maneja recursos en Spring Boot
# ============================================================

import asyncio                              # Para operaciones asíncronas
import random                               # Para tiempos aleatorios (comportamiento humano)
from typing import Optional                 # Para tipos opcionales
from playwright.async_api import (          # Importamos lo necesario de Playwright
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright
)
from loguru import logger                   # Para logs


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
        # ... usar la página ...
        await browser_manager.close()
    """

    def __init__(self):
        # Instancia de Playwright — el motor que controla el navegador
        self._playwright: Optional[Playwright] = None

        # El navegador Chromium
        self._browser: Optional[Browser] = None

        # El contexto del navegador — equivale a una ventana del browser
        # Un contexto puede tener múltiples pestañas (Pages)
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

        # Iniciamos Playwright
        self._playwright = await async_playwright().start()

        # Lanzamos Chromium con configuraciones específicas anti-detección
        self._browser = await self._playwright.chromium.launch(
            # headless=False significa que el navegador ES visible
            # Lo ponemos visible para debugging — en producción puede ponerse True
            headless=False,

            # Argumentos que hacen el browser más parecido a un humano real
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                # Deshabilitamos la automatización de Chrome
                "--disable-blink-features=AutomationControlled",
            ]
        )

        # Creamos el contexto del navegador con configuración de stealth
        self._context = await self._browser.new_context(
            # User agent de un Chrome real en Windows
            # Si el user agent dice "HeadlessChrome", Cloudflare lo bloquea
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),

            # Tamaño de pantalla real — los bots suelen tener tamaños raros
            viewport={"width": 1366, "height": 768},

            # Idioma del navegador
            locale="es-MX",

            # Zona horaria de México
            timezone_id="America/Mexico_City",

            # Permitimos JavaScript — algunos sites lo bloquean si está desactivado
            java_script_enabled=True,

            # Ignoramos errores de certificados SSL (útil en algunos entornos)
            ignore_https_errors=True,
        )

        # Aplicamos scripts de stealth ANTES de que cargue cualquier página
        # Estos scripts modifican propiedades del browser que delatan automatización
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

        # Creamos una nueva página (pestaña) en el contexto
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
            # Cerramos el contexto (todas las pestañas)
            if self._context:
                await self._context.close()
                self._context = None

            # Cerramos el navegador
            if self._browser:
                await self._browser.close()
                self._browser = None

            # Detenemos Playwright
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
        # Generamos un tiempo aleatorio entre min y max
        delay_ms = random.randint(min_ms, max_ms)

        # asyncio.sleep recibe segundos, dividimos entre 1000
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
        # Primero hacemos click en el campo para enfocarlo
        await page.click(selector)

        # Pequeña pausa antes de empezar a escribir (como un humano que piensa)
        await BrowserManager.human_delay(200, 600)

        # Escribimos letra por letra con pausas aleatorias
        await page.type(
            selector,
            text,
            delay=random.randint(50, 150)  # Pausa entre 50ms y 150ms entre letras
        )
