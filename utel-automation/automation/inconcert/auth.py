"""InConcertAuth — login en el CRM InConcert."""

import asyncio
from playwright.async_api import Page
from loguru import logger

from config.settings import settings
from core.utils import human_delay


class InConcertAuth:
    """Maneja el login en InConcert."""

    #Inyeccion de dependencias: recibe la pestana de Chromium donde se ejecutara el login en InConcert
    def __init__(self, page: Page):
        self.page = page

    #Login: verifica sesion activa → si no, llena credenciales → click Ingresar → confirma autenticacion
    async def login(self) -> bool:
        try:
            if await self._is_logged_in():
                logger.info("Sesion activa detectada")
                return True

            logger.info("Realizando login...")
            await self._fill_username()
            await human_delay(300, 600)
            await self._fill_password()
            await human_delay(500, 1000)
            await self._click_login_button()

            for _ in range(20):
                if await self._is_logged_in():
                    logger.info("Login exitoso en InConcert")
                    return True
                await asyncio.sleep(1)

            logger.error("Login fallido — verifica credenciales en .env")
            return False

        except Exception as e:
            logger.error(f"Error en login: {e}")
            return False
            

     #Verifica si ya hay sesion activa en InConcert buscando elementos del DOM
     #que solo aparecen despues del login exitoso (sidebar, lista de contactos).
     #Retorna True si encuentra alguno, False si no hay sesion.       
    async def _is_logged_in(self) -> bool:
        try:
            for selector in [".mas-sidebar", "[class*='sidebar']", ".contact-list", "h1:has-text('Contactos')", "[data-testid='contacts']"]:
                element = await self.page.query_selector(selector)
                if element:
                    return True
        except Exception:
            pass
        return False
        

    #Busca el campo usuario por input[name='userId'] (o email/username/placeholder),
    #escribe settings.inconcert_user con fill() y retorna. Si no lo encuentra, solo advierte.
    async def _fill_username(self) -> None:
        for selector in [
            "input[name='userId']",
            "input[type='email']",
            "input[name='username']",
            "input[placeholder*='usuario']",
        ]:
            el = await self.page.query_selector(selector)
            if el and await el.is_visible():
                await el.fill(settings.inconcert_user)
                logger.info("Usuario ingresado")
                return
        logger.warning("No se encontro campo de usuario en InConcert")


    #Busca el campo password por input[type='password'] (o name/id/placeholder),
    #escribe settings.inconcert_password con fill() y retorna. Si no lo encuentra, solo advierte.
    async def _fill_password(self) -> None:
        for selector in [
            "input[type='password']",
            "input[name='password']",
            "input[id='password']",
            "input[placeholder*='contraseña']",
        ]:
            el = await self.page.query_selector(selector)
            if el and await el.is_visible():
                await el.fill(settings.inconcert_password)
                logger.info("Contrasena ingresada")
                return
        logger.warning("No se encontro campo de contrasena en InConcert")


    #Localiza el boton de inicio de sesion por selectores semanticos, hace click y retorna.
    #Si no encuentra el boton en ningun selector, loguea advertencia sin interrumpir el flujo.
    async def _click_login_button(self) -> None:
        for selector in [
            "button[type='submit']",
            "button:has-text('Ingresar')",
            "button:has-text('Iniciar sesion')",
            ".btn-login",
        ]:
            el = await self.page.query_selector(selector)
            if el and await el.is_visible():
                await el.click()
                logger.info("Click en boton de login")
                return
        logger.warning("No se encontro boton de login en InConcert")
