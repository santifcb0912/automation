"""InConcertSearch — búsqueda de leads en InConcert con reintentos."""

import asyncio
import re
from typing import Optional
from playwright.async_api import Page, TimeoutError
from loguru import logger

from core.utils import human_delay



class InConcertSearch:
    """Busca leads en InConcert por email con reintentos en caso de demorarse el lead."""

   #Constructor: inyecta dependencias necesarias para buscar leads en InConcert
   #page: pestaña de Chromium donde se ejecutan las acciones
   #contacts_url: URL de la pagina de contactos (/contact/people), ya construida por InConcertClient
    def __init__(self, page: Page, contacts_url: str):
        self.page = page
        self.contacts_url = contacts_url
        

    #Entrada: recibe el email del lead e inicia la busqueda en InConcert
    async def search(self, email: str) -> bool:
        logger.info(f"Buscando lead: {email}")
        return await self._perform_search(email)


   #Orquesta: asegura estar en contactos, recarga, pone filtro Email, escribe el correo
   # y reintenta cada 15s hasta 8 veces (120s maximo) verificando si el lead aparece
    async def _perform_search(self, email: str) -> bool:
        try:
            await self._ensure_contacts_page()
            await self.page.reload(wait_until="domcontentloaded")
            await human_delay(2000, 3000)

            await self._select_email_filter()

            search_input = await self._find_search_input()
            if not search_input:
                return False

            await search_input.fill(email)
            await human_delay(300, 600)

            return await self.retry_search()

        except Exception as e:
            logger.error(f"Error en busqueda: {e}")
            return False


    #Navegacion: si no esta en /contact/people, redirige a la pagina de contactos de InConcert
    async def _ensure_contacts_page(self) -> None:
        current = self.page.url
        if "contact/people" not in current:
            await self.page.goto(self.contacts_url, wait_until="domcontentloaded")
            await human_delay(1500, 2000)


    #Filtro: abre el dropdown de busqueda basica y selecciona la opcion "Email" dentro del menu desplegado
    async def _select_email_filter(self) -> bool:
        strategies = [
            ("ngb_dropdown", self.page.locator("button.btn-dropdown-text[ngbdropdowntoggle]").first),
            ("generic_combo", self.page.locator("[role='combobox']:visible, [class*='select']:visible, [class*='dropdown']:visible").first),
        ]
        for name, toggle in strategies:
            try:
                await toggle.wait_for(state="visible", timeout=8000)
                await toggle.click()
                await human_delay(300, 500)
                email_opt = self.page.get_by_role("link", name="Email", exact=True).first
                await email_opt.wait_for(state="visible", timeout=5000)
                await email_opt.click()
                await human_delay(300, 500)
                logger.info(f"Filtro Email seleccionado via {name}")
                return True
            except TimeoutError:
                logger.debug(f"Estrategia '{name}' no disponible (timeout)")
                continue
            except Exception as e:
                logger.debug(f"Estrategia '{name}' fallo: {e}")
                continue
            

    #Input: localiza el campo de texto por su placeholder y lo retorna para escribir el email
    async def _find_search_input(self):
        loc = self.page.get_by_placeholder("Ingrese un texto para buscar")
        if await loc.count() > 0:
            return loc
        logger.warning("No se encontro el campo de busqueda por placeholder")
        return None


    #Reintentos: intenta hasta 8 veces (c/15s) clickear la lupa y verificar si el lead llego a InConcert
    async def retry_search(self) -> bool:
        max_attempts = 8
        interval = 15
        for attempt in range(1, max_attempts + 1):
            await self._click_search_button()
            await human_delay(2000, 3000)
            if await self._has_results():
                logger.success(f"Lead encontrado en intento {attempt}")
                return True
            if attempt < max_attempts:
                logger.info(f"Lead no encontrado — esperando {interval}s (intento {attempt}/{max_attempts})")
                await asyncio.sleep(interval)
        logger.warning(f"TIMEOUT — Lead no llego despues de {max_attempts * interval}s")
        return False


    #Busqueda: localiza el boton "Buscar" por su atributo title y hace click para ejecutar la busqueda
    async def _click_search_button(self) -> None:
        try:
            btn = self.page.get_by_title("Buscar")
            await btn.wait_for(state="visible", timeout=5000)
            await btn.click()
            logger.debug("Click en lupa de busqueda")
        except TimeoutError:
            logger.debug("Boton buscar no disponible (timeout)")
        except Exception as e:
            logger.debug(f"Click en boton buscar fallo: {e}")


    #Verificacion: revisa si ha llegado el lead en la tabla de resultados (input)
    async def _has_results(self) -> bool:
        try:
            no_results = self.page.get_by_text(re.compile("0 resultados", re.IGNORECASE))
            if await no_results.count() > 0 and await no_results.first.is_visible():
                return False

            for selector in ["table tbody tr", ".contact-row", ".result-row", "[class*='contact-item']"]:
                rows = self.page.locator(selector)
                if await rows.count() > 0:
                    return True
            return False
        except Exception as e:
            logger.error(f"Error verificando resultados: {e}")
            return False


    # Abre el menu de acciones del lead
    async def open_actions_menu(self, lead_email: str) -> bool:
        try:
            row = self.page.locator("table tbody tr").first
            await row.wait_for(state="visible", timeout=5000)
            await row.hover(timeout=3000)
            await human_delay(400, 700)
            button = row.locator("button[ngbdropdowntoggle]")
            await button.click(timeout=5000)
            await human_delay(500, 1000)
            return True
        except Exception as e:
            logger.error(f"No se pudo abrir menu de 3 puntos: {e}")
            return False


     # Click en 'Gestionar'
    async def click_gestionar(self) -> bool:
        try:
            await human_delay(800, 1200)
            menu = self.page.locator("[role='menu']")
            item = menu.locator("a.dropdown-item[title='Gestionar']").first
            await item.wait_for(state="attached", timeout=10000)
            async with self.page.expect_navigation(timeout=15000):
                await item.dispatch_event("click")
            logger.info("Click en 'Gestionar'")
            return True
        except Exception as e:
            logger.error(f"No se pudo hacer clic en Gestionar: {e}")
            return False


   #Busca el titulo de la seccion, hace clic para expandirla y confirma que el contenido aparecio.
   #Los parametros opcionales ajustan tiempos si una seccion es mas lenta que otra.
    async def _expand_section(
        self,
        section_text: str,
        verification_text: str,
        *,
        section_timeout: int = 10000,
        scroll_timeout: int = 3000,
        delay_before: tuple = (200, 400),
        delay_after: tuple = (500, 800),
    ) -> Optional[str]:
        try:
            section = self.page.get_by_text(section_text, exact=True).first
            await section.wait_for(state="visible", timeout=section_timeout)
            await section.scroll_into_view_if_needed(timeout=scroll_timeout)
            await human_delay(*delay_before)
            await section.click(timeout=5000)
            await human_delay(*delay_after)

            verify = self.page.get_by_text(verification_text, exact=True).first
            await verify.wait_for(state="visible", timeout=20000)
            await verify.scroll_into_view_if_needed(timeout=3000)
            logger.info(f"Seccion '{section_text}' expandida / {verification_text} visible")
            return None

        except TimeoutError:
            msg = f"{verification_text} no encontrado en {section_text}"
            logger.error(f"Timeout: {msg}")
            return msg
        except Exception as e:
            logger.error(f"Error expandiendo {section_text}: {e}")
            return str(e)

    #Expande la seccion Creacion y verifica Origen Id (usa defaults de _expand_section)
    async def expand_creation_section(self) -> Optional[str]:
        return await self._expand_section("Creación", "Origen Id")

    #Expande la seccion Contacto y verifica Programa de interes (timeouts y delays propios)
    async def expand_contact_section(self) -> Optional[str]:
        return await self._expand_section(
            "Contacto", "Programa de interés",
            section_timeout=15000,
            scroll_timeout=5000,
            delay_before=(300, 500),
            delay_after=(1000, 1500),
        )
