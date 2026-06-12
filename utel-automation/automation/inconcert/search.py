"""InConcertSearch — búsqueda de leads en InConcert con reintentos."""

import asyncio
import re
from playwright.async_api import Page, TimeoutError
from loguru import logger

from config.countries import Country
from automation.browser import BrowserManager



class InConcertSearch:
    """Busca leads en InConcert por email con reintentos."""

    #Constructor: asigna page y pais al buscador
    def __init__(self, page: Page, country: Country):
        self.page = page
        self.country = country

    #Entrada: recibe el email del lead e inicia la busqueda en InConcert
    async def search(self, email: str) -> bool:
        logger.info(f"Buscando lead: {email}")
        return await self._perform_search(email)

    #Orquesta: navega a contactos, recarga, selecciona filtro Email, escribe el correo y delega en el polling
    async def _perform_search(self, email: str) -> bool:
        try:
            await self._ensure_contacts_page()
            await self.page.reload(wait_until="domcontentloaded")
            await self.page.wait_for_load_state("networkidle")
            await BrowserManager.human_delay(1000, 1500)

            await self._select_email_filter()

            search_input = await self._find_search_input()
            if not search_input:
                return False

            await search_input.fill(email)
            await BrowserManager.human_delay(300, 600)

            return await self._reintentar_busqueda()

        except Exception as e:
            logger.error(f"Error en busqueda: {e}")
            return False

    #Navegacion: si no esta en /contact/people, redirige a la pagina de contactos de InConcert
    async def _ensure_contacts_page(self) -> None:
        current = self.page.url
        if "contact/people" not in current:
            base = self.country.inconcert_url.rstrip("/")
            if base.endswith("/home"):
                base = base[:-5]
            await self.page.goto(base + "/contact/people", wait_until="domcontentloaded")
            await BrowserManager.human_delay(1500, 2000)

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
                await BrowserManager.human_delay(300, 500)
                email_opt = self.page.get_by_role("link", name="Email", exact=True).first
                await email_opt.wait_for(state="visible", timeout=5000)
                await email_opt.click()
                await BrowserManager.human_delay(300, 500)
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

    #Reintentos: intenta hasta 8 veces (c/15s) clickear la lupa y verificar si el lead llego a InConcert
    async def _reintentar_busqueda(self) -> bool:
        max_attempts = 8
        interval = 15
        for attempt in range(1, max_attempts + 1):
            await self._click_search_button()
            await BrowserManager.human_delay(2000, 3000)
            if await self._has_results():
                logger.success(f"Lead encontrado en intento {attempt}")
                return True
            if attempt < max_attempts:
                logger.info(f"Lead no encontrado — esperando {interval}s (intento {attempt}/{max_attempts})")
                await asyncio.sleep(interval)
        logger.warning(f"TIMEOUT — Lead no llego despues de {max_attempts * interval}s")
        return False

    #Verificacion: revisa si aparecio el mensaje "0 resultados" o si ha llegado el lead en la tabla de resultados
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
            row = self.page.locator("tr, .contact-row, .result-row").filter(
                has_text=lead_email
            )
            await row.wait_for(state="visible", timeout=5000)

            # ⚠️ Técnico: busca botón por icono de 3 puntos (sin aria-label).
            #   Si InConcert cambia de librería de iconos (Font Awesome → SVG propio → Lucide),
            #   este selector fallará. Alternativa futura: botón que dispare un dropdown.
            button = row.locator("button").filter(
                has=self.page.locator(
                    "span[class*='ellipsis'], i[class*='ellipsis'], svg[class*='ellipsis']"
                )
            )
            await button.wait_for(state="visible", timeout=5000)

            await button.scroll_into_view_if_needed(timeout=3000)
            await BrowserManager.human_delay(250, 500)
            await button.click(timeout=4000)

            menu = self.page.locator("[role='menu'], .dropdown-menu, .dropdown-list").filter(
                has_text="Gestionar"
            )
            await menu.wait_for(state="visible", timeout=5000)

            return True

        except TimeoutError as e:
            logger.error(f"Timeout abriendo menu para {lead_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return False
            

    # Clica en la opcion 'Gestionar' del menu de acciones
    async def click_gestionar(self) -> bool:
        try:
            menu = self.page.locator("[role='menu'], .dropdown-menu")
            await menu.wait_for(state="visible", timeout=5000)

            item = menu.locator("a.dropdown-item[title='Gestionar']")
            await item.wait_for(state="visible", timeout=5000)
            await item.click(timeout=4000)
            logger.info("Click en 'Gestionar'")
            return True

        except TimeoutError:
            logger.error("Menu de acciones no esta abierto o 'Gestionar' no disponible")
            return False
        except Exception as e:
            logger.error(f"Error clicando Gestionar: {e}")
            return False

    # Expande la seccion 'Creacion' y verifica que 'Origen Id' sea visible
    async def expand_creation_section(self) -> bool:
        try:
            section = self.page.locator("div.timeline-title").filter(
                has_text="Creación"
            )
            await section.wait_for(state="visible", timeout=10000)
            await section.scroll_into_view_if_needed(timeout=3000)
            await BrowserManager.human_delay(200, 400)
            await section.click(timeout=5000)
            await BrowserManager.human_delay(500, 800)

            origen = self.page.locator("div.title-widget-text").filter(
                has_text="Origen Id"
            )
            await origen.wait_for(state="visible", timeout=10000)
            logger.info("Seccion 'Creacion' expandida / Origen Id visible")
            return True

        except TimeoutError:
            logger.error("Timeout expandiendo seccion Creacion / Origen Id")
            return False
        except Exception as e:
            logger.error(f"Error expandiendo Creacion: {e}")
            return False

    # Expande la seccion 'Contacto' y verifica que 'Programa de interes' sea visible
    async def expand_contact_section(self) -> bool:
        try:
            section = self.page.get_by_text("Contacto", exact=True).first
            await section.wait_for(state="visible", timeout=15000)
            await section.scroll_into_view_if_needed(timeout=5000)
            await BrowserManager.human_delay(300, 500)
            await section.click(timeout=5000)
            await BrowserManager.human_delay(1000, 1500)

            programa = self.page.get_by_text("Programa de interés", exact=True).first
            await programa.wait_for(state="visible", timeout=20000)
            await programa.scroll_into_view_if_needed(timeout=3000)
            logger.info("Seccion 'Contacto' expandida / Programa de interes visible")
            return True

        except TimeoutError:
            logger.error("Timeout expandiendo seccion Contacto / Programa de interes")
            return False
        except Exception as e:
            logger.error(f"Error expandiendo Contacto: {e}")
            return False