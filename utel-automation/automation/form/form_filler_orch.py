"""FormFillerOrchestrator — coordina el llenado completo de formularios.

Reemplaza el antiguo FormFiller (2982 líneas) orquestando 7 componentes
especializados, cada uno con una única responsabilidad.

Flujo:
1. Navegar a la LP
2. Detectar tipo de formulario y scope
3. Preparar el formulario según tipo (Lateral, Footer, Tarjeta, México)
4. Llenar campos en orden: modalidad → área → programa → nombre → email → tel → privacidad
5. Validar estado pre-submit
6. Enviar formulario
7. Validar post-submit
"""

from typing import Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from loguru import logger

from config.countries import Country
from core.fake_data.service import FakeDataService
from core.models import LeadRow
from automation.form.detectors import FormDetector
from automation.form.form_utils import (
    normalize_form_type,
    is_mexico_utel_lp,
    is_mexico_universidad_lp,
    level_preferences,
    modality_preferences,
    canonical_level,
    program_query,
)
from automation.form.select_handler import SelectHandler
from automation.form.program_search import ProgramSearchEngine
from automation.form.contact_fields import ContactFieldFiller
from automation.form.privacy_handler import PrivacyHandler
from automation.form.form_submitter import FormSubmitter, SubmissionValidator
from automation.form.mexico_handler import MexicoFormHandler
from automation.common.scroll_navigator import scroll_to_form_id, scroll_until_contact_form
from automation.common.cloudflare import is_cloudflare_blocked

FOOTER_FIELDS_TIMEOUT_MS = 30000
FOOTER_BEFORE_FILL_DELAY_MS = 30000


class FormFillerOrchestrator:
    """Coordina el llenado de formularios usando componentes especializados."""

    def __init__(self, page: Page, country: Country, fake_data_service: FakeDataService):
        self.page = page
        self.country = country
        self._fake_data = fake_data_service
        self.detector = FormDetector(page, country)
        self.form_type: str = ""
        self._tarjeta_product_opened: bool = False
        self._mexico_utel: bool = False
        self._mexico_universidad: bool = False

    async def fill(self, lead: LeadRow) -> bool:
        """Método principal: llena y envía el formulario de la LP."""
        try:
            self.form_type = normalize_form_type(lead.form_type)
            self._mexico_utel = is_mexico_utel_lp(self.country, lead.landing_url)
            self._mexico_universidad = is_mexico_universidad_lp(self.country, lead.landing_url)
            level = self.detector.resolve_level(lead.nivel, lead.landing_url)

            logger.info(f"Abriendo LP: {lead.landing_url}")
            logger.info(f"Formulario: {self.form_type or 'FormLP'} | nivel='{level}'")
            if self._mexico_utel:
                logger.info("Reglas Mexico utel.edu activas")
            if self._mexico_universidad:
                logger.info("Reglas Universidad Mexico activas")

            await self.page.goto(lead.landing_url, wait_until="domcontentloaded", timeout=45000)
            await self._soft_wait_network()
            await self.page.wait_for_timeout(3000)

            await self._prepare_form(level)

            self.detector.form_scope = await self._find_scope()
            if not self.detector.form_scope:
                return False

            if self.form_type == "footer" and self._mexico_utel:
                if not await self._prepare_footer():
                    return False

            await self.detector.log_fields("antes de llenar")

            if self._mexico_universidad:
                filled = await self._fill_universidad(lead.test_email, level, lead.nivel or "")
            else:
                filled = await self._fill_standard(lead.test_email, level, lead.nivel or "")

            await self.detector.log_fields("despues de llenar")
            if not filled:
                return False

            submitter = FormSubmitter(self.page, self.detector.form_scope)
            submitted = await submitter.submit()
            if not submitted:
                return False

            if self._mexico_universidad:
                validator = SubmissionValidator(self.page)
                if not await validator.validate_universidad_mexico():
                    return False

            await self.page.wait_for_timeout(4000)
            logger.info("Formulario enviado; se permite continuar a InConcert")
            return True

        except PlaywrightTimeoutError:
            logger.error(f"Timeout llenando formulario: {lead.landing_url}")
            return False
        except Exception as e:
            logger.error(f"Error en FormFillerOrchestrator.fill(): {e}")
            return False

    async def _soft_wait_network(self) -> None:
        try:
            await self.page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            pass

    async def _prepare_form(self, level: str) -> None:
        """Prepara el formulario según su tipo."""
        if self._mexico_universidad:
            await self._prepare_universidad_mexico()
        elif self.form_type == "lateral":
            await self._prepare_lateral()
        elif self.form_type == "footer":
            await self._prepare_footer_flow()
        elif self.form_type in ("tarjeta", "targeta"):
            await self._prepare_tarjeta(level)
        else:
            logger.info("FormLP: se buscara formulario visible")

    async def _find_scope(self):
        if self._mexico_universidad:
            handler = MexicoFormHandler(self.page, self.page.locator("body"))
            return await handler.find_universidad_scope()
        return await self.detector.detect_form_scope(self.form_type, self._tarjeta_product_opened)

    async def _prepare_footer_flow(self) -> None:
        logger.info("Preparando flujo Footer")
        if await scroll_to_form_id(self.page, "FooterBLC"):
            return
        await scroll_until_contact_form(self.page)

    async def _prepare_footer(self) -> bool:
        logger.info(f"Footer: esperando hasta {FOOTER_FIELDS_TIMEOUT_MS//1000}s para campos")
        ready = await self._wait_for_footer_fields()
        if not ready:
            return False
        self.detector.form_scope = await self.detector.detect_form_scope(self.form_type, self._tarjeta_product_opened)
        if not self.detector.form_scope:
            return False
        logger.info(f"Footer: esperando {FOOTER_BEFORE_FILL_DELAY_MS//1000}s antes de llenar")
        await self.page.wait_for_timeout(FOOTER_BEFORE_FILL_DELAY_MS)
        return True

    async def _wait_for_footer_fields(self, timeout_ms: int = FOOTER_FIELDS_TIMEOUT_MS) -> bool:
        attempts = max(int(timeout_ms / 500), 1)
        for _ in range(attempts):
            try:
                ready = await self.detector.form_scope.evaluate("""
                    (root) => {
                        const visible = (el) => { const s=window.getComputedStyle(el); const b=el.getBoundingClientRect(); return s.display!=='none'&&s.visibility!=='hidden'&&b.width>0&&b.height>0&&!el.disabled&&el.type!=='hidden'; };
                        const fields = Array.from(root.querySelectorAll('input,select,textarea')).filter(visible).map(el=>`${el.name||''} ${el.id||''} ${el.placeholder||''} ${el.type||''}`.toLowerCase());
                        return fields.some(x=>x.includes('email')||x.includes('correo')) && fields.some(x=>x.includes('phone')||x.includes('tel')||x.includes('telefono')||x.includes('celular')||x.includes('mobile')) && fields.some(x=>x.includes('name')||x.includes('nombre')||x.includes('first_name'));
                    }
                """) if self.detector.form_scope else False
                if ready:
                    logger.info("Footer: campos obligatorios visibles")
                    return True
            except Exception:
                pass
            await self.page.wait_for_timeout(500)
        logger.warning("Footer: no cargaron campos obligatorios")
        return False

    async def _prepare_lateral(self) -> None:
        logger.info("Preparando flujo Lateral")
        opened = await self._open_lateral_cta()
        if not opened:
            logger.warning("Lateral: no se pudo hacer click en Solicitar informacion")
            return
        if not await self._wait_for_lateral_panel():
            logger.warning("Lateral: no aparecio panel lateral")

    async def _open_lateral_cta(self) -> bool:
        try:
            result = await self.page.evaluate("""
                () => {
                    const norm = (v) => String(v||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim();
                    const visible = (el) => { const s=window.getComputedStyle(el); const b=el.getBoundingClientRect(); return s.display!=='none'&&s.visibility!=='hidden'&&b.width>0&&b.height>0; };
                    const candidates = Array.from(document.querySelectorAll('a,button,[role=button]')).filter(visible)
                        .map((el) => ({ el, box: el.getBoundingClientRect(), text: norm(el.textContent) }))
                        .filter(({text}) => text.includes('solicitar informacion'))
                        .sort((a,b) => { const aT=a.box.top<180?0:1; const bT=b.box.top<180?0:1; return aT-bT||Math.abs(window.innerWidth-a.box.right)-Math.abs(window.innerWidth-b.box.right); });
                    const target = candidates[0]?.el;
                    if(!target) return false;
                    target.scrollIntoView({block:'center',inline:'center',behavior:'instant'});
                    target.click();
                    return true;
                }
            """)
            if result:
                await self.page.wait_for_timeout(1800)
                logger.info("Click en CTA 'Solicitar informacion'")
                return True
        except Exception as e:
            logger.debug(f"Lateral CTA fallo: {e}")
        return False

    async def _wait_for_lateral_panel(self, timeout_ms: int = 7000) -> bool:
        attempts = max(int(timeout_ms / 350), 1)
        for _ in range(attempts):
            if await scroll_to_form_id(self.page, "LateralBLC"):
                return True
            if await self._lateral_panel_open():
                return True
            await self.page.wait_for_timeout(350)
        return False

    async def _lateral_panel_open(self) -> bool:
        try:
            return await self.page.evaluate("""
                () => {
                    const visible = (el) => { const s=window.getComputedStyle(el); const b=el.getBoundingClientRect(); return s.display!=='none'&&s.visibility!=='hidden'&&b.width>0&&b.height>0; };
                    const vw = window.innerWidth||document.documentElement.clientWidth;
                    const candidates = Array.from(document.querySelectorAll('aside,section,form,div')).filter(visible)
                        .map((el) => ({ el, box: el.getBoundingClientRect(), text: el.textContent||'' }))
                        .filter(({box}) => box.left>vw*0.55||box.right>vw*0.85)
                        .filter(({text}) => /tu meta esta cerca|completa el formulario|modalidad|area de interes/i.test(text));
                    return candidates.some(({el}) => {
                        const fields = Array.from(el.querySelectorAll('input,select,textarea')).filter(visible);
                        const keys = fields.map(f=>`${f.name||''} ${f.id||''} ${f.placeholder||''}`.toLowerCase());
                        return keys.some(x=>x.includes('email')||x.includes('correo')) && keys.some(x=>x.includes('phone')||x.includes('tel')) && keys.some(x=>x.includes('name')||x.includes('nombre'));
                    });
                }
            """)
        except Exception:
            return False

    async def _prepare_tarjeta(self, level: str) -> None:
        logger.info("Preparando flujo Tarjeta")
        self._tarjeta_product_opened = False
        original_url = self.page.url

        searcher = ProgramSearchEngine(self.page, self.page.locator("body"))
        if self._mexico_utel:
            product_opened = await searcher.open_tarjeta_product(level, original_url)
        else:
            product_opened = await searcher._search_program_from_generic_page(level, original_url)

        if not product_opened:
            suffix = " en 120s" if self._mexico_utel else ""
            logger.warning(f"Tarjeta: no se selecciono LP de producto{suffix}")
            return

        self._tarjeta_product_opened = True
        await self._soft_wait_network()
        await self.page.wait_for_timeout(2500)
        if not await scroll_to_form_id(self.page, "TarjetaBLC"):
            await scroll_until_contact_form(self.page)

    async def _fill_standard(self, test_email: str, level: str, raw_level: str) -> bool:
        """Llenado estándar (no Universidad México)."""
        sel = SelectHandler(self.page, self.detector.form_scope)
        contacts = ContactFieldFiller(self.page, self.detector.form_scope)
        privacy = PrivacyHandler(self.page, self.detector.form_scope)

        pref = level_preferences(level)
        mod_pref = modality_preferences(raw_level or level)

        await sel.select("modality", preferred=mod_pref)
        await self.page.wait_for_timeout(4000)

        area_exists = await sel.exists("area")
        area_ok = await sel.select("area", preferred=pref, require_preferred_match=True)
        if area_exists and not area_ok:
            logger.warning(f"No se pudo seleccionar Area: {level}")
            return False
        await self.page.wait_for_timeout(4000)

        program_done = await sel.select("program", preferred=[*pref, program_query(level)])
        if not program_done:
            program_done = await sel.select_by_context(level, pref, program_query(level))
        if not program_done:
            await self._fill_program_input(level)
        await self.page.wait_for_timeout(1200)

        await contacts.set_name(self._fake_data.get_name(self.country.id, self.country.fake_name))
        await contacts.set_email(test_email)
        await contacts.set_phone(self._fake_data.get_phone(self.country.id, self.country.fake_phone))
        await privacy.check()

        state = await self.detector.read_form_state()
        logger.info(f"Estado final pre-submit: {state}")

        validator = SubmissionValidator(self.page)
        return await validator.check_submission_fields(state)

    async def _fill_program_input(self, level: str) -> None:
        """Fallback: llena program como input de texto."""
        query = program_query(level)
        field = self.detector.form_scope.locator(
            "#program, input[name='program'], input[placeholder*='programa' i], input[placeholder*='interes' i]"
        )
        if await field.count() == 0:
            logger.info("Campo program no existe en este formulario")
            return
        try:
            await field.first.scroll_into_view_if_needed(timeout=5000)
            await field.first.click(force=True, timeout=5000)
            await field.first.fill(query, force=True, timeout=5000)
            await field.first.press("ArrowDown")
            await field.first.press("Enter")
            await self.page.wait_for_timeout(1500)
        except Exception as e:
            logger.warning(f"Program input fallo: {e}")

    async def _fill_universidad(self, test_email: str, level: str, raw_level: str) -> bool:
        """Llenado específico para Universidad Mexico."""
        handler = MexicoFormHandler(self.page, self.detector.form_scope)
        contacts = ContactFieldFiller(self.page, self.detector.form_scope)
        privacy = PrivacyHandler(self.page, self.detector.form_scope)

        await handler.fill_cms_sequence(level=level, raw_level=raw_level)
        await self.page.wait_for_timeout(800)

        name = self._fake_data.get_name(self.country.id, self.country.fake_name)
        phone = self._fake_data.get_phone(self.country.id, self.country.fake_phone)

        await handler.fill_universidad_inputs(test_email, name, phone)
        await self.page.wait_for_timeout(800)

        program_selected = await handler.select_custom_program(level)
        if not program_selected:
            logger.warning("Universidad: no se selecciono programa")
            return False

        await handler.fill_universidad_inputs(test_email, name, phone)
        await privacy.check()

        state = await handler.get_form_state()
        logger.info(f"Universidad estado final: {state}")

        if state.get("missing_required"):
            logger.warning(f"Universidad: faltan campos: {state.get('missing_required')}")
            return False
        if state.get("has_program") and not state.get("program"):
            logger.warning("Universidad: programa sin seleccionar")
            return False
        for key in ["name", "email", "phone"]:
            if state.get(f"has_{key}") and not state.get(key):
                logger.warning(f"Universidad: campo '{key}' presente sin completar")
                return False
        if state.get("has_checkbox") and not state.get("checkbox_checked"):
            logger.warning("Universidad: checkbox no marcado")
            return False

        return True
