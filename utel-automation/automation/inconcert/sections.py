"""SectionExpander — expande secciones en el detalle del lead en InConcert.

Usa locators de Playwright (get_by_role, get_by_text) en vez de
coordenadas o JS inline. Robusto ante cambios de layout.
"""

import re
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from loguru import logger


class SectionExpander:
    """Expande secciones colapsables en el panel de detalle del lead.
    
    Cada seccion se identifica por texto (regex, case-insensitive) y se
    verifica que el contenido expandido sea visible tras el click.
    """

    def __init__(self, page: Page):
        self.page = page

    async def expand_creation_event(self) -> None:
        await self._expand_section(
            section_text="creaci[oó]n",
            label="Creacion / Origen Id",
            verification_text="origen",
        )

    async def expand_contact_section(self) -> None:
        await self._expand_section(
            section_text="contacto",
            label="Contacto / Nivel de programa",
            verification_text="nivel de programa",
        )

    async def _expand_section(
        self,
        section_text: str,
        label: str,
        verification_text: str,
        timeout: int = 20000,
        retries: int = 1,
    ) -> None:
        attempts = 0
        last_error = None
        while attempts <= retries:
            try:
                section = self.page.get_by_text(re.compile(section_text, re.IGNORECASE)).first
                await section.click(timeout=timeout)
                await self.page.get_by_text(
                    re.compile(verification_text, re.IGNORECASE)
                ).wait_for(state="visible", timeout=15000)
                logger.info(f"Sección '{label}' expandida")
                return
            except PlaywrightTimeout:
                last_error = f"timeout ({timeout}ms)"
                if attempts < retries:
                    await self.page.wait_for_timeout(2000)
                attempts += 1
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Error expandiendo {label}: {e}")
                return

        logger.warning(f"No se pudo expandir {label}: {last_error}")
