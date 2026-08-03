"""Orquesta el pipeline por lead: login → búsqueda con reintentos → apertura del detalle."""

from typing import Optional

from playwright.async_api import Page
from loguru import logger

from config.countries import Country
from automation.inconcert.auth import InConcertAuth
from automation.inconcert.search import InConcertSearch
from core.utils import human_delay


_LEAD_NOT_ARRIVED = "Lead no llego durante los 120s"


class InConcertClient:
    # Inyecta page, pais y los componentes de auth y busqueda
    def __init__(self, page: Page, country: Country):
        self.page = page
        self.country = country
        self.auth = InConcertAuth(page)
        self.search = InConcertSearch(page, self._build_contacts_url())
        self._last_email: Optional[str] = None
        self._missing_contact_area: bool = False

    # Construye la URL de la pagina de contactos normalizando /mas y /home si existen
    def _build_contacts_url(self) -> str:
        base = self.country.inconcert_url.rstrip("/")
        if base.endswith("/home"):
            base = base[:-5]
        if not base.endswith("/mas"):
            base += "/mas"
        return base + "/contact/people"

    # Navega al home primero (cookies/sesion), luego a contactos y delega el login en InConcertAuth
    async def login(self) -> bool:
        home_url = self.country.inconcert_url
        logger.info(f"Navegando a InConcert (home): {home_url}")
        await self.page.goto(home_url, wait_until="domcontentloaded", timeout=30000)
        await human_delay(1500, 2500)

        contacts_url = self._build_contacts_url()
        logger.info(f"Navegando a contactos: {contacts_url}")
        await self.page.goto(contacts_url, wait_until="domcontentloaded", timeout=30000)
        await human_delay(1500, 2500)

        return await self.auth.login()

    # Guarda el email del lead y delega la busqueda en Search.py con reintentos hasta 120s
    async def search_lead(self, email: str) -> bool:
        self._last_email = email
        return await self.search.search(email)

    # Prepara la vista para captura: 3 puntos → Gestionar → secciones Creacion y Contacto
    async def prepare_screenshot_view(self) -> Optional[str]:
        if not self._last_email:
            return "No hay email para abrir detalle"

        if not await self.search.open_actions_menu(self._last_email):
            return self._LEAD_NOT_ARRIVED

        if not await self.search.click_gestionar():
            return self._LEAD_NOT_ARRIVED

        if not await self._wait_management_panel():
            return self._LEAD_NOT_ARRIVED

        await self.page.wait_for_timeout(10000)
        logger.info("Espera de 10s completada — paneles deberian estar listos")

        err = await self.search.expand_creation_section()
        if err:
            return self._LEAD_NOT_ARRIVED

        err = await self.search.expand_contact_section()
        if err:
            self._missing_contact_area = True
            logger.warning("Captura tomada sin campo area de programa de interes en contacto - inconcert")

        return None

    # Espera a que el panel de gestion del contacto sea visible
    async def _wait_management_panel(self) -> bool:
        try:
            await self.page.get_by_text(
                "Gestionar Contacto", exact=True
            ).first.wait_for(state="visible", timeout=10000)
            logger.info("Panel de gestion abierto")
            return True
        except Exception:
            return False

    # Retorna True si la seccion de contacto no tenia area de programa de interes
    @property
    def missing_contact_area(self) -> bool:
        return self._missing_contact_area
