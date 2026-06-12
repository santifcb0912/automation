"""InConcertClient — coordina el flujo completo en InConcert.

Compone:
1. InConcertAuth — login
2. InConcertSearch — búsqueda, acciones, expansión de secciones
3. LeadDetailOpener — abrir detalle del lead
"""

from playwright.async_api import Page
from loguru import logger

from config.countries import Country
from automation.inconcert.auth import InConcertAuth
from automation.inconcert.search import InConcertSearch
from automation.inconcert.lead_detail import LeadDetailOpener


class InConcertClient:
    """Cliente completo de InConcert. Coordina login + búsqueda + detalle + secciones."""

    def __init__(self, page: Page, country: Country):
        self.page = page
        self.country = country
        self.auth = InConcertAuth(page, country)
        self.search = InConcertSearch(page, country)
        self.detail_opener = LeadDetailOpener(page)

    async def login(self) -> bool:
        return await self.auth.login()

    async def search_lead(self, email: str) -> bool:
        return await self.search.search(email)

    async def prepare_screenshot_view(self) -> None:
        """Abre detalle del lead y expande secciones para la captura."""
        await self.detail_opener.open()
        await self.search.expand_creation_section()
        await self.search.expand_contact_section()
