

import re
from playwright.async_api import Page
from loguru import logger

from typing import Optional
from config.countries import Country
from automation.inconcert.auth import InConcertAuth
from automation.inconcert.search import InConcertSearch
from core.utils import human_delay

"""Orquesta el pipeline por lead: login → búsqueda con reintentos
 → apertura del detalle (3 puntos → Gestionar → secciones Creación y Contacto)."""

 
class InConcertClient:
   
    #Constructor
    def __init__(self, page: Page, country: Country):
        self.page = page
        self.country = country
        self.auth = InConcertAuth(page)
        self.search = InConcertSearch(page, self._build_contacts_url())
        self._last_email: Optional[str] = None
        self._missing_contact_area: bool = False


    # dirige la URL completa de la página de contactos, eliminando /home si existe y concatena /contact/people"
    def _build_contacts_url(self) -> str:
        base = self.country.inconcert_url.rstrip("/")
        if base.endswith("/home"):
            base = base[:-5]
        return base + "/contact/people"

    #Navega al home de InConcert primero (para establecer cookies/sesion),
    #luego va a la pagina de contactos y delega el login en InConcertAuth
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

    #Guarda el email del lead y delega la busqueda en Search.py con reintentos hasta 120s
    async def search_lead(self, email: str) -> bool:
        self._last_email = email
        return await self.search.search(email)

    #Abre el detalle del lead en InConcert: click en 3 puntos → Gestionar → espera panel → 
    #expande secciones Creacion y Contacto para la captura
    #Retorna None si todo sale bien, o un str con la razon del error para escribir en Sheets
    _LEAD_NOT_ARRIVED = "Lead no llego durante los 120s"

    async def prepare_screenshot_view(self) -> Optional[str]:
        if not self._last_email:
            return "No hay email para abrir detalle"

        if not await self.search.open_actions_menu(self._last_email):
            return self._LEAD_NOT_ARRIVED

        if not await self.search.click_gestionar():
            return self._LEAD_NOT_ARRIVED

        try:
            await self.page.get_by_text(
                "Gestionar Contacto", exact=True
            ).first.wait_for(state="visible", timeout=10000)
            logger.info("Panel de gestion abierto")
        except Exception:
            return self._LEAD_NOT_ARRIVED

        await self.page.wait_for_timeout(10000)
        logger.info("Espera de 10s completada — paneles deberian estar listos")

        err = await self.search.expand_creation_section()
        if err:
            return self._LEAD_NOT_ARRIVED

        err = await self.search.expand_contact_section()
        if err:
            self._missing_contact_area = True
            msg = "Captura tomada sin campo area de programa de interes en contacto - inconcert"
            logger.warning(msg)

        return None

    @property
    def missing_contact_area(self) -> bool:
        return self._missing_contact_area
