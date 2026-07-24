"""MexicoCmsFiller — strategy para llenar formularios CMS Mexico (utel.edu.mx).

Secuencia: modalidad -> area -> programa -> contactos -> privacidad -> submit.
Usa los handlers compartidos de automation/form/handlers/.
Los handlers se inyectan por constructor para facilitar pruebas.
"""

import random
from typing import Optional

from playwright.async_api import Page
from loguru import logger

from config.countries import Country
from config.form_configs import CmsConfig
from automation.form.fill_context import FillContext
from automation.form.form_utils import level_preferences, modality_preferences
from automation.form.handlers.select_handler import SelectHandler
from automation.form.handlers.contact_fields import ContactFieldFiller
from automation.form.handlers.privacy_handler import PrivacyHandler
from automation.form.handlers.form_submitter import FormSubmitter, SubmissionValidator
from automation.form.detectors import FormDetector
from automation.form.program_search import ProgramSearchEngine


class MexicoCmsFiller:
    """Llena formularios CMS Mexico siguiendo: modalidad, area, programa, contactos, submit."""

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

    async def fill(self, ctx: FillContext) -> Optional[str]:
        self._ensure_handlers(ctx)

        logger.info("MexicoCmsFiller: iniciando secuencia de llenado")

        result = await self._select_modality(ctx)
        if result is not None: return result
        result = await self._select_area(ctx)
        if result is not None: return result
        result = await self._select_program(ctx)
        if result is not None: return result
        result = await self._fill_contacts(ctx)
        if result is not None: return result
        result = await self._check_privacy()
        if result is not None: return result
        result = await self._validate_pre_submit(ctx)
        if result is not None: return result
        result = await self._submit()
        if result is not None: return result

        logger.info("MexicoCmsFiller: secuencia completada con exito")
        return None

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
            self._detector = FormDetector(self._page, self._country)
            self._detector.form_scope = ctx.form_scope
        if self._validator is None:
            self._validator = SubmissionValidator(self._page)

    async def _select_modality(self, ctx: FillContext) -> Optional[str]:
        mod_pref = modality_preferences(ctx.raw_level or ctx.level)
        await self._sel.select(self._config.field_modality, preferred=mod_pref)
        await self._page.wait_for_timeout(4000)
        return None

    async def _select_area(self, ctx: FillContext) -> Optional[str]:
        pref = level_preferences(ctx.level)
        area_exists = await self._sel.exists(self._config.field_area)
        area_ok = await self._sel.select(self._config.field_area, preferred=pref, require_preferred_match=True)
        await self._page.wait_for_timeout(4000)
        if area_exists and not area_ok:
            return f"No se pudo seleccionar Area: {ctx.level}"
        return None

    async def _select_program(self, ctx: FillContext) -> Optional[str]:
        program_field = ctx.form_scope.locator("[name='program']")
        if await program_field.count() == 0:
            return f"Campo programa no encontrado: {ctx.level}"
        tag = await program_field.first.evaluate("el => el.tagName")
        if tag == "SELECT":
            options = await program_field.first.evaluate("""
                el => Array.from(el.options).map(o => o.value).filter(v => v)
            """)
            if not options:
                return "Programa select: sin opciones disponibles"
            pick = random.choice(options)
            ok = await self._sel.select(self._config.field_program, preferred=[pick])
            if not ok:
                return f"No se pudo seleccionar Programa: {pick}"
            await self._page.wait_for_timeout(1200)
            return None
        if tag == "INPUT":
            searcher = ProgramSearchEngine(self._page, ctx.form_scope)
            ok = await searcher.select_random_program(ctx.level)
            if not ok:
                return "Programa input: no se pudo seleccionar"
            return None
        return f"Tipo de campo programa no soportado: {tag}"

    async def _fill_contacts(self, ctx: FillContext) -> Optional[str]:
        if not await self._contacts.set_name(ctx.fake_name):
            return "Campo nombre no se pudo completar"
        if not await self._contacts.set_email(ctx.test_email):
            return "Campo email no se pudo completar"
        if not await self._contacts.set_phone(ctx.fake_phone):
            return "Campo telefono no se pudo completar"
        return None

    async def _check_privacy(self) -> Optional[str]:
        if not await self._privacy.check():
            return "Checkbox de privacidad no se pudo marcar"
        return None

    async def _validate_pre_submit(self, ctx: FillContext) -> Optional[str]:
        state = await self._detector.read_form_state()
        logger.info(f"MexicoCmsFiller: estado pre-submit: {state}")
        error = await self._validator.check_submission_fields(state)
        if error is not None:
            return f"Validacion: {error}"
        return None

    async def _submit(self) -> Optional[str]:
        if not await self._submitter.submit():
            return "No se encontro boton de submit"
        return None
