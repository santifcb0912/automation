"""InConcertAuth — login en el CRM InConcert."""

from playwright.async_api import Page
from loguru import logger

from config.settings import settings
from config.countries import Country
from automation.browser import BrowserManager


class InConcertAuth:
    """Maneja el login en InConcert."""

    def __init__(self, page: Page, country: Country):
        self.page = page
        self.country = country

    async def login(self) -> bool:
        try:
            base = self.country.inconcert_url.rstrip("/")
            if base.endswith("/home"):
                base = base[:-5]
            contacts_url = base + "/contact/people"

            logger.info(f"Navegando a InConcert: {contacts_url}")
            await self.page.goto(contacts_url, wait_until="domcontentloaded", timeout=30000)
            await BrowserManager.human_delay(1500, 2500)

            if await self._is_logged_in():
                logger.info("Sesion activa detectada")
                return True

            logger.info("Realizando login...")
            await self._fill_username()
            await BrowserManager.human_delay(300, 600)
            await self._fill_password()
            await BrowserManager.human_delay(500, 1000)
            await self._click_login_button()

            await self.page.wait_for_load_state("networkidle", timeout=15000)
            await BrowserManager.human_delay(2000, 3000)

            if await self._is_logged_in():
                logger.info("Login exitoso en InConcert")
                return True

            logger.error("Login fallido — verifica credenciales en .env")
            return False

        except Exception as e:
            logger.error(f"Error en login: {e}")
            return False

    async def _is_logged_in(self) -> bool:
        try:
            for selector in [".mas-sidebar", "[class*='sidebar']", ".contact-list", "h1:has-text('Contactos')", "[data-testid='contacts']"]:
                element = await self.page.query_selector(selector)
                if element:
                    return True
        except Exception:
            pass
        return False

    async def _fill_username(self) -> None:
        for selector in [
            "input[type='email']", "input[name='username']", "input[name='email']",
            "input[name='user']", "input[placeholder*='usuario']", "input[placeholder*='email']",
            "input[id*='user']", "input[id*='email']",
        ]:
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    await el.click()
                    await self.page.keyboard.type(settings.inconcert_user, delay=80)
                    logger.info("Usuario ingresado")
                    return
            except Exception:
                continue

    async def _fill_password(self) -> None:
        for selector in [
            "input[type='password']", "input[name='password']", "input[name='pass']",
            "input[id*='password']", "input[id*='pass']",
        ]:
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    await el.click()
                    await self.page.keyboard.type(settings.inconcert_password, delay=80)
                    logger.info("Contrasena ingresada")
                    return
            except Exception:
                continue

    async def _click_login_button(self) -> None:
        for selector in [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Ingresar')", "button:has-text('Login')",
            "button:has-text('Entrar')", "button:has-text('Iniciar sesion')",
            ".btn-login", ".login-btn",
        ]:
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    await el.click()
                    logger.info("Click en boton de login")
                    return
            except Exception:
                continue
