"""CmsFiller — strategy parametrizada por config para llenar formularios CMS.

Secuencia: modalidad -> area -> provincia (si config) -> programa -> contactos -> privacidad -> submit.
Usa los handlers compartidos de automation/form/handlers/.
Los handlers se inyectan por constructor para facilitar pruebas.
"""

import random
from typing import Optional

from playwright.async_api import Page, Locator
from loguru import logger

from config.countries import Country
from config.form_configs import CmsConfig
from automation.form.contracts.fill_context import FillContext
from automation.form.engine.form_utils import level_preferences, modality_preferences
from automation.form.contracts.i_form_filler import IFormFiller
from automation.form.handlers.select_handler import SelectHandler
from automation.form.handlers.contact_fields import ContactFieldFiller
from automation.form.handlers.privacy_handler import PrivacyHandler
from automation.form.handlers.form_submitter import FormSubmitter, SubmissionValidator
from automation.form.engine.detectors import FormDetector
from automation.form.engine.program_search import ProgramSearchEngine
from automation.common.scroll_navigator import scroll_to_form_id


_AFTER_SELECT_WAIT_MS = 4000
_AFTER_PROGRAM_WAIT_MS = 1200
_STABILIZE_AFTER_CTA_MS = 1800
_STABILIZE_AFTER_HAMBURGER_MS = 1500
_STABILIZE_AFTER_CONTACTO_MS = 1500
_STABILIZE_AFTER_FOCUS_MS = 800
_LATERAL_PANEL_POLL_MS = 350
_LATERAL_PANEL_TIMEOUT_MS = 10000
_SCROLL_TIMEOUT_MS = 8000
_CLICK_TIMEOUT_MS = 5000
_FOCUS_TIMEOUT_MS = 5000


class CmsFiller(IFormFiller):
    """Llena formularios CMS siguiendo: modalidad, area, provincia, programa, contactos, submit."""

    # Config con selectores del pais + page Playwright + handlers inyectables
    def __init__(
        self,
        config: CmsConfig,
        page: Page,
        country: Country,
        fake_data,
        select_handler=None,
        contact_filler=None,
        privacy_handler=None,
        submitter=None,
        detector=None,
        validator=None,
    ):
        self._config = config
        self._page = page
        self._country = country
        self._fake_data = fake_data
        self._sel = select_handler
        self._contacts = contact_filler
        self._privacy = privacy_handler
        self._submitter = submitter
        self._detector = detector
        self._validator = validator

    # Abre panel lateral o realiza otra preparacion segun el tipo de formulario.
    async def prepare(self, form_type: str, level: str) -> None:
        if form_type == "lateral":
            await self._prepare_lateral()

    # Pipeline: cada paso retorna None (ok) o str (error corta el flujo)
    async def fill(self, ctx: FillContext) -> Optional[str]:
        self._ensure_handlers(ctx)
        logger.info("CmsFiller: iniciando secuencia de llenado")
        for step in [self._select_modality, self._select_eres_bachiller, self._select_area,
                     self._select_ciudad, self._select_provincia, self._select_program,
                     self._select_pais, self._select_canal_preferido, self._fill_contacts]:
            error = await step(ctx)
            if error is not None: return error
        for step in [self._check_privacy, self._validate_pre_submit, self._submit]:
            error = await step()
            if error is not None: return error
        logger.info("CmsFiller: secuencia completada con exito")
        return None

    # Crea handlers default si no fueron inyectados por constructor
    def _ensure_handlers(self, ctx: FillContext):
        if self._sel is None:
            self._sel = SelectHandler(self._page, ctx.form_scope)
        if self._contacts is None:
            self._contacts = ContactFieldFiller(self._page, ctx.form_scope)
        if self._privacy is None:
            self._privacy = PrivacyHandler(self._page, ctx.form_scope)
        if self._submitter is None:
            self._submitter = FormSubmitter(self._page, ctx.form_scope, self._config.submit_buttons)
        if self._detector is None:
            self._detector = FormDetector(self._page, self._country, ctx.form_scope)
        if self._validator is None:
            self._validator = SubmissionValidator(self._page)

    # Lateral: plan A CTA directo; plan B menu hamburguesa -> CTA.
    async def _prepare_lateral(self) -> None:
        logger.info("Preparando flujo Lateral")
        opened = await self._open_lateral_cta()
        if not opened:
            logger.info("CTA directo no disponible, probando menu hamburguesa")
            opened = await self._open_lateral_via_hamburger()
        if not opened:
            logger.warning("Lateral: no se pudo abrir el panel")
            return
        if not await self._wait_for_lateral_panel():
            logger.warning("Lateral: no aparecio panel lateral, se omite focus")
            return
        await scroll_to_form_id(self._page, "LateralBLC")
        modality = self._page.locator("select[name='modality']")
        if await modality.count() > 0:
            await modality.first.focus(timeout=_FOCUS_TIMEOUT_MS)
            await self._page.wait_for_timeout(_STABILIZE_AFTER_FOCUS_MS)

    # Plan A: hace click en el boton CTA lateral usando cta_texts de la config.
    async def _open_lateral_cta(self) -> bool:
        try:
            for text in self._config.cta_texts:
                cta = self._page.locator(f"button:has-text('{text}')")
                if await cta.count() > 0:
                    await cta.first.scroll_into_view_if_needed(timeout=_SCROLL_TIMEOUT_MS)
                    await cta.first.click(timeout=_CLICK_TIMEOUT_MS)
                    await self._page.wait_for_timeout(_STABILIZE_AFTER_CTA_MS)
                    logger.info(f"Click en CTA '{text}'")
                    return True
        except Exception as e:
            logger.debug(f"Lateral CTA fallo: {e}")
        return False

    # Sondea cada _LATERAL_PANEL_POLL_MS hasta _LATERAL_PANEL_TIMEOUT_MS si el panel lateral ya esta visible.
    async def _wait_for_lateral_panel(self) -> bool:
        max_attempts = max(int(_LATERAL_PANEL_TIMEOUT_MS / _LATERAL_PANEL_POLL_MS), 1)
        for _ in range(max_attempts):
            if await scroll_to_form_id(self._page, "LateralBLC"):
                return True
            await self._page.wait_for_timeout(_LATERAL_PANEL_POLL_MS)
        return False

    # Plan B: abre menu hamburguesa y hace click en CTA lateral.
    async def _open_lateral_via_hamburger(self) -> bool:
        logger.info("Abriendo menu hamburguesa")
        try:
            hamburger = self._page.locator("svg.chakra-icon").first
            if await hamburger.count() == 0:
                logger.warning("Icono hamburguesa no encontrado")
                return False
            await hamburger.dispatch_event("click")
            await self._page.wait_for_timeout(_STABILIZE_AFTER_HAMBURGER_MS)
            for text in self._config.cta_texts:
                btn = self._page.locator(f"button:has-text('{text}')")
                if await btn.count() > 0:
                    await btn.first.dispatch_event("click")
                    await self._page.wait_for_timeout(_STABILIZE_AFTER_CONTACTO_MS)
                    logger.info(f"Click en '{text}' desde menu hamburguesa")
                    return True
            return True
        except Exception as e:
            logger.debug(f"Menu hamburguesa fallo: {e}")
            return False

    # Selecciona modalidad segun nivel; si no existe el campo lo salta (footer)
    async def _select_modality(self, ctx: FillContext) -> Optional[str]:
        if not await self._sel.exists(self._config.field_modality):
            return None
        mod_pref = modality_preferences(ctx.raw_level or ctx.level)
        ok = await self._sel.select(self._config.field_modality, preferred=mod_pref)
        await self._page.wait_for_timeout(_AFTER_SELECT_WAIT_MS)
        if not ok:
            return f"No se pudo seleccionar Modalidad para: {ctx.raw_level or ctx.level}"
        return None

    # Selecciona area por nivel; si no existe el campo lo salta
    async def _select_area(self, ctx: FillContext) -> Optional[str]:
        pref = level_preferences(ctx.level)
        area_exists = await self._sel.exists(self._config.field_area)
        area_ok = await self._sel.select(self._config.field_area, preferred=pref, require_preferred_match=True)
        await self._page.wait_for_timeout(_AFTER_SELECT_WAIT_MS)
        if area_exists and not area_ok:
            return f"No se pudo seleccionar Area: {ctx.level}"
        return None

    # Selecciona provincia aleatoria del dropdown si el campo existe en la config.
    async def _select_provincia(self, ctx: FillContext) -> Optional[str]:
        if not self._config.field_provincia:
            return None
        if not await self._sel.exists(self._config.field_provincia):
            return None
        values = await ctx.form_scope.locator(f"[name='{self._config.field_provincia}']").first.evaluate("""
            (el) => Array.from(el.options).filter((o, i) => i > 0 && o.value && !o.disabled).map(o => o.value)
        """)
        if not values:
            return "Provincia: sin opciones disponibles"
        pick = random.choice(values)
        ok = await self._sel.select(self._config.field_provincia, preferred=[pick])
        if not ok:
            return f"No se pudo seleccionar Provincia: {pick}"
        await self._page.wait_for_timeout(_AFTER_SELECT_WAIT_MS)
        return None

    # Selecciona ciudad aleatoria del dropdown si el campo existe en la config
    async def _select_ciudad(self, ctx: FillContext) -> Optional[str]:
        if not self._config.field_ciudad:
            return None
        if not await self._sel.exists(self._config.field_ciudad):
            return None
        values = await ctx.form_scope.locator(f"[name='{self._config.field_ciudad}']").first.evaluate("""
            (el) => Array.from(el.options).filter((o, i) => i > 0 && o.value && !o.disabled).map(o => o.value)
        """)
        if not values:
            return "Ciudad: sin opciones disponibles"
        pick = random.choice(values)
        ok = await self._sel.select(self._config.field_ciudad, preferred=[pick])
        if not ok:
            return f"No se pudo seleccionar Ciudad: {pick}"
        await self._page.wait_for_timeout(_AFTER_SELECT_WAIT_MS)
        return None

    # Selecciona SI/NO aleatorio si el campo eresBachiller existe
    async def _select_eres_bachiller(self, ctx: FillContext) -> Optional[str]:
        if not self._config.field_eres_bachiller:
            return None
        if not await self._sel.exists(self._config.field_eres_bachiller):
            return None
        pick = random.choice(["SI", "NO"])
        ok = await self._sel.select(self._config.field_eres_bachiller, preferred=[pick])
        if not ok:
            return f"eresBachiller: no se pudo seleccionar {pick}"
        await self._page.wait_for_timeout(_AFTER_SELECT_WAIT_MS)
        return None

    # Selecciona canal de contacto aleatorio si el campo Canal_Preferido existe
    async def _select_canal_preferido(self, ctx: FillContext) -> Optional[str]:
        if not self._config.field_canal_preferido:
            return None
        if not await self._sel.exists(self._config.field_canal_preferido):
            return None
        await self._sel.select(self._config.field_canal_preferido, preferred=[])
        await self._page.wait_for_timeout(_AFTER_SELECT_WAIT_MS)
        return None

    # Selecciona el pais del formulario (paisesPIVI) segun el prefijo del nivel del lead
    async def _select_pais(self, ctx: FillContext) -> Optional[str]:
        if not self._config.field_pais:
            return None
        if not await self._sel.exists(self._config.field_pais):
            return None
        prefix = next((k for k in self._config.pais_value_map if ctx.raw_level.startswith(k)), None)
        if not prefix:
            return f"Pais no encontrado para nivel: {ctx.raw_level}"
        value = self._config.pais_value_map[prefix]
        ok = await self._sel.select(self._config.field_pais, preferred=[value])
        if not ok:
            return f"No se pudo seleccionar Pais: {value}"
        await self._page.wait_for_timeout(_AFTER_SELECT_WAIT_MS)
        return None

    # Determina si programa es SELECT o INPUT y delega
    async def _select_program(self, ctx: FillContext) -> Optional[str]:
        program_field = ctx.form_scope.locator("[name='program']")
        if await program_field.count() == 0:
            return f"Campo programa no encontrado: {ctx.level}"
        tag = await program_field.first.evaluate("el => el.tagName")
        if tag == "SELECT":
            return await self._select_program_select(ctx.form_scope)
        if tag == "INPUT":
            return await self._select_program_input(ctx)
        return f"Tipo de campo programa no soportado: {tag}"

    # Extrae opciones del <select>, elige una al azar y la selecciona
    async def _select_program_select(self, form_scope: Locator) -> Optional[str]:
        values = await form_scope.locator("[name='program']").first.evaluate("""
            (el) => Array.from(el.options).filter((o, i) => i > 0 && o.value && !o.disabled).map(o => o.value)
        """)
        if not values:
            return "Programa select: sin opciones disponibles"
        pick = random.choice(values)
        ok = await self._sel.select(self._config.field_program, preferred=[pick])
        if not ok:
            return f"No se pudo seleccionar Programa: {pick}"
        await self._page.wait_for_timeout(_AFTER_PROGRAM_WAIT_MS)
        return None

    # Busca y selecciona programa por autocompletado
    async def _select_program_input(self, ctx: FillContext) -> Optional[str]:
        searcher = ProgramSearchEngine(self._page, ctx.form_scope)
        ok = await searcher.select_random_program(ctx.level)
        if not ok:
            return "Programa input: no se pudo seleccionar"
        return None

    # Llena nombre, email, telefono; falla en el primer campo vacio
    async def _fill_contacts(self, ctx: FillContext) -> Optional[str]:
        if not await self._contacts.set_name(ctx.fake_name):
            return "Campo nombre no se pudo completar"
        if not await self._contacts.set_email(ctx.test_email):
            return "Campo email no se pudo completar"
        if not await self._contacts.set_phone(ctx.fake_phone):
            return "Campo telefono no se pudo completar"
        return None

    # Marca checkbox de privacidad
    async def _check_privacy(self) -> Optional[str]:
        if not await self._privacy.check():
            return "Checkbox de privacidad no se pudo marcar"
        return None

    # Verifica que todos los campos obligatorios tengan valor
    async def _validate_pre_submit(self) -> Optional[str]:
        state = await self._detector.read_form_state()
        logger.info(f"CmsFiller: estado pre-submit: {state}")
        error = await self._validator.check_submission_fields(state)
        if error is not None:
            return f"Validacion: {error}"
        return None

    # Busca boton submit y ejecuta dispatch_event("click")
    async def _submit(self) -> Optional[str]:
        if not await self._submitter.submit():
            return "No se encontro boton de submit"
        return None