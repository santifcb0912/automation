"""FormFillerOrchestrator — coordina el llenado completo de formularios.

Flujo:
1. Navegar a la LP
2. Detectar tipo de formulario y scope
3. Preparar el formulario segun tipo (Lateral, Footer, Tarjeta)
4. Obtener la strategy IFormFiller via registry y ejecutar filler.fill()
5. Retornar True/False segun el resultado de la strategy

Las constantes al inicio del modulo definen los timeouts y pausas
de estabilizacion para cada paso, asegurando que el DOM este listo
antes de cada interaccion.
"""

from typing import Optional

from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from loguru import logger

from config.countries import Country
from core.fake_data.service import FakeDataService
from core.models import LeadRow
from automation.form.engine.detectors import FormDetector
from automation.form.engine.form_utils import (
    normalize_form_type,
    resolve_level,
)
from automation.form.engine.program_search import ProgramSearchEngine
from automation.common.scroll_navigator import scroll_to_form_id
from automation.form.contracts.fill_context import FillContext
from automation.form.contracts.i_form_filler import IFormFiller
from automation.form.engine.registry import get_filler


# Timeouts y pausas de estabilizacion en milisegundos para cada
# etapa del ciclo de vida del formulario (navegacion -> preparacion
# -> llenado -> envio).
_GOTO_TIMEOUT_MS = 45000
_SOFT_NETWORK_TIMEOUT_MS = 15000
_STABILIZE_AFTER_NAV_MS = 5000
_STABILIZE_AFTER_SUBMIT_MS = 4000
_TARJETA_POST_OPEN_WAIT_MS = 5000
_SCROLL_VIEW_TIMEOUT_MS = 5000


class FormFillerOrchestrator:
    """Coordina el llenado de formularios usando strategies via registry."""

    def __init__(self, page: Page, country: Country, fake_data_service: FakeDataService):
        self.page = page
        self.country = country
        self._fake_data = fake_data_service
        self._detector = FormDetector(page, country)
        self._form_type: str = ""
        self._tarjeta_product_opened: bool = False
        self._filler: Optional[IFormFiller] = None


# Coordina el ciclo completo de llenado del formulario.
    async def fill(self, lead: LeadRow) -> Optional[str]:
        level = self._prepare_fill_state(lead)
        self._filler = get_filler(self.country, lead.landing_url, self.page, self._fake_data)
        try:
            await self._navigate_to_lp(lead.landing_url)
        except PlaywrightTimeoutError:
            logger.error(f"Timeout navegando a LP: {lead.landing_url}")
            return "Timeout: la pagina LP no cargo en 45s"

        try:
            await self._prepare_form(level)
        except PlaywrightTimeoutError:
            logger.error(f"Timeout preparando formulario tipo {self._form_type}: {lead.landing_url}")
            return f"Timeout: el formulario {self._form_type} no se pudo preparar"

        try:
            scope = await self._find_scope()
        except PlaywrightTimeoutError:
            logger.error(f"Timeout detectando scope del formulario: {lead.landing_url}")
            return "Timeout: no se detecto el scope del formulario"

        if not scope:
            return "No se encontro scope del formulario"

        try:
            return await self._execute_strategy(scope, level, lead)
        except PlaywrightTimeoutError:
            logger.error(f"Timeout llenando formulario {self._form_type}: {lead.landing_url}")
            return "Timeout: el llenado del formulario excedio el tiempo"
        except Exception as e:
            logger.error(f"Error en FormFillerOrchestrator.fill(): {e}")
            return f"Error inesperado: {e}"


# Prepara el estado de llenado del formulario.
    def _prepare_fill_state(self, lead: LeadRow) -> str:
        self._form_type = normalize_form_type(lead.form_type)
        level = resolve_level(self.country, lead.nivel)
        logger.info(f"Abriendo LP: {lead.landing_url}")
        logger.info(f"Formulario: {self._form_type or 'desconocido'} | nivel='{level}'")
        if self.country.id == "mexico":
            logger.info("Reglas Mexico utel.edu activas")
        return level
        

# Navega a la landing page, espera networkidle con timeout suave y una pausa de estabilizacion para permitir renderizado.
    async def _navigate_to_lp(self, url: str) -> None:
        await self.page.goto(url, wait_until="domcontentloaded", timeout=_GOTO_TIMEOUT_MS)
        await self._soft_wait_network()
        await self.page.wait_for_timeout(_STABILIZE_AFTER_NAV_MS)


# Ejecuta la strategy IFormFiller via registry.
    async def _execute_strategy(self, scope: Locator, level: str, lead: LeadRow) -> Optional[str]:
        await self._detector.log_fields("antes de llenar")
        ctx = FillContext(
            form_scope=scope,
            level=level,
            raw_level=lead.nivel or "",
            test_email=lead.test_email,
            fake_name=self._fake_data.get_name(),
            fake_phone=self._fake_data.get_phone(self.country.id),
        )
        error = await self._filler.fill(ctx)
        await self._detector.log_fields("despues de llenar")
        if error is not None:
            logger.warning(f"Strategy fallo: {error}")
            return error
        await self.page.wait_for_timeout(_STABILIZE_AFTER_SUBMIT_MS)
        logger.info("Formulario enviado; verificacion pre-submit aprobada")
        return None


    # Espera networkidle con timeout suave. Si no llega (Cloudflare, WebSockets, etc.) captura la excepcion y continua.
    async def _soft_wait_network(self) -> None:
        try:
            await self.page.wait_for_load_state("networkidle", timeout=_SOFT_NETWORK_TIMEOUT_MS)
        except Exception:
            pass


    # Prepara el flujo de llenado según el tipo de formulario.
    async def _prepare_form(self, level: str) -> None:
        await self._filler.prepare(self._form_type, level)
        if self._form_type == "footer":
            await self._prepare_footer_flow()
        elif self._form_type == "tarjeta":
            await self._prepare_tarjeta(level)
        elif self._form_type not in ("lateral",):
            logger.warning(f"Tipo de formulario desconocido para CMS: '{self._form_type}'")


# Busca el scope del formulario en el DOM.
    async def _find_scope(self):
        return await self._detector.detect_form_scope(self._form_type, self._tarjeta_product_opened)


# Prepara el flujo de llenado para el footer.
    async def _prepare_footer_flow(self) -> None:
        logger.info("Preparando flujo Footer")
        await scroll_to_form_id(self.page, "FooterBLC")


# Tarjeta: si #TarjetaBLC ya existe en la LP, Plan A (fill directo).
# Si no, Plan B: buscar LP de producto via ProgramSearchEngine.
    async def _prepare_tarjeta(self, level: str) -> None:
        logger.info("Preparando flujo Tarjeta")
        self._tarjeta_product_opened = False

        tarjeta = self.page.locator("#TarjetaBLC")
        if await tarjeta.count() > 0:
            logger.info("Tarjeta: #TarjetaBLC encontrado en LP actual (Plan A)")
            self._tarjeta_product_opened = True
            await scroll_to_form_id(self.page, "TarjetaBLC")
            return

        logger.info("Tarjeta: #TarjetaBLC no encontrado, buscando LP de producto (Plan B)")
        original_url = self.page.url
        searcher = ProgramSearchEngine.for_country(self.country.id, self.page, self.page.locator("body"))
        product_opened = await searcher.open_tarjeta_product(level, original_url)

        if not product_opened:
            logger.warning("Tarjeta: no se selecciono LP de producto en 120s")
            return

        self._tarjeta_product_opened = True
        await self._soft_wait_network()
        await self.page.wait_for_timeout(_TARJETA_POST_OPEN_WAIT_MS)
        await scroll_to_form_id(self.page, "TarjetaBLC")
