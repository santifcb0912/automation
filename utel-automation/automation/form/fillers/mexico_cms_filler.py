"""MexicoCmsFiller — strategy para llenar formularios CMS Mexico (utel.edu.mx).

Secuencia: modalidad -> area -> programa -> contactos -> privacidad -> submit.
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

_AFTER_SELECT_WAIT_MS = 4000
_AFTER_PROGRAM_WAIT_MS = 1200


class MexicoCmsFiller(IFormFiller):
    """Llena formularios CMS Mexico siguiendo: modalidad, area, programa, contactos, submit."""

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

    # Pipeline: cada paso retorna None (ok) o str (error corta el flujo)
    async def fill(self, ctx: FillContext) -> Optional[str]:
        self._ensure_handlers(ctx)
        logger.info("MexicoCmsFiller: iniciando secuencia de llenado")
        for step in [self._select_modality, self._select_area, self._select_program,
                     self._fill_contacts]:
            error = await step(ctx)
            if error is not None: return error
        for step in [self._check_privacy, self._validate_pre_submit, self._submit]:
            error = await step()
            if error is not None: return error
        logger.info("MexicoCmsFiller: secuencia completada con exito")
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
        logger.info(f"MexicoCmsFiller: estado pre-submit: {state}")
        error = await self._validator.check_submission_fields(state)
        if error is not None:
            return f"Validacion: {error}"
        return None

    # Busca boton submit y ejecuta dispatch_event("click")
    async def _submit(self) -> Optional[str]:
        if not await self._submitter.submit():
            return "No se encontro boton de submit"
        return None
