# ============================================================
# automation/form_filler.py
# Llena formularios UTEL sin cambiar el frontend del sistema.
# Estrategia principal tomada del QA previo con Selenium:
#   1. Ubicar form por ID segun Location: FooterBLC/LateralBLC/TarjetaBLC.
#   2. Llenar dentro de ese form, nunca en toda la pagina.
#   3. Respetar dependencias: modality -> area -> program -> contacto.
#   4. Validar valores antes de enviar.
# ============================================================

from typing import Optional

from loguru import logger
from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.countries import Country, get_level_name, infer_level_from_url
from config.models import LeadRow


FORM_IDS = {
    "footer": "FooterBLC",
    "lateral": "LateralBLC",
    "tarjeta": "TarjetaBLC",
    "targeta": "TarjetaBLC",
}

PROGRAM_SEARCH_BY_LEVEL = {
    "licenciatura": "Administracion",
    "licenciaturas": "Administracion",
    "licenciaturas hibridas": "Administracion",
    "maestria": "Administracion",
    "maestria ejecutiva": "Administracion",
    "maestría": "Administracion",
    "doctorado": "Gestion",
    "diplomado": "Project",
    "diplomados": "Project",
    "bachillerato": "Bachillerato",
}


class FormFiller:
    """Llena y envia formularios de LPs UTEL usando Playwright."""

    def __init__(self, page: Page, country: Country):
        self.page = page
        self.country = country
        self.form_scope: Optional[Locator] = None
        self.form_type: str = ""
        logger.debug(f"FormFiller creado para {country.id}")

    async def fill(self, lead: LeadRow) -> bool:
        """Abre la LP, prepara el formulario correcto y lo envia."""
        try:
            self.form_type = self._normalize_form_type(lead.form_type)
            level = get_level_name(self.country, lead.nivel or "")
            if not level:
                level = infer_level_from_url(lead.landing_url) or ""

            logger.info(f"Abriendo LP: {lead.landing_url}")
            logger.info(f"Formulario: {self.form_type or 'formlp'} | nivel='{level}'")

            await self.page.goto(
                lead.landing_url,
                wait_until="domcontentloaded",
                timeout=45000,
            )
            await self._soft_wait_network()
            await self.page.wait_for_timeout(3000)

            if self.form_type == "lateral":
                await self._prepare_lateral_flow(level)
            elif self.form_type == "footer":
                await self._prepare_footer_flow()
            elif self.form_type in ["tarjeta", "targeta"]:
                await self._prepare_tarjeta_flow(lead)
            else:
                logger.info("Form LP: se buscara formulario visible")

            self.form_scope = await self._find_form_scope(self.form_type)
            if not self.form_scope:
                logger.warning("No se encontro formulario usable")
                return False

            await self._log_fields("antes de llenar")
            filled = await self._fill_form(test_email=lead.test_email, level=level)
            await self._log_fields("despues de llenar")
            if not filled:
                return False

            submitted = await self._submit_form()
            if not submitted:
                return False

            await self.page.wait_for_timeout(4000)
            logger.info("Formulario enviado; se permite continuar a InConcert")
            return True

        except PlaywrightTimeoutError:
            logger.error(f"Timeout llenando formulario: {lead.landing_url}")
            return False
        except Exception as e:
            logger.error(f"Error en FormFiller.fill(): {e}")
            return False

    def _normalize_form_type(self, form_type: str) -> str:
        raw = (form_type or "").strip().lower().replace(" ", "")
        if raw in ["formlp", "form"]:
            return "formlp"
        if raw in ["targeta", "tarjeta"]:
            return raw
        return raw

    async def _soft_wait_network(self) -> None:
        try:
            await self.page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            logger.debug("networkidle no completo; continuo con DOM cargado")

    async def _prepare_footer_flow(self) -> None:
        logger.info("Preparando flujo Footer")
        if await self._scroll_to_form_id("FooterBLC"):
            return
        await self._scroll_until_contact_form()

    async def _prepare_lateral_flow(self, level: str) -> None:
        logger.info("Preparando flujo Lateral")

        if await self._scroll_to_form_id("LateralBLC"):
            return

        opened = await self._open_hamburger_menu()
        if opened:
            await self._click_menu_option(["En linea", "En línea", "Online"])
            await self.page.wait_for_timeout(1000)
            await self._click_menu_option([level, "Licenciaturas", "Licenciatura"])
            await self._soft_wait_network()
            await self.page.wait_for_timeout(2500)

        if await self._scroll_to_form_id("LateralBLC"):
            return

        if await self._scroll_to_form_id("FooterBLC"):
            return

        await self._scroll_until_contact_form()

    async def _prepare_tarjeta_flow(self, lead: LeadRow) -> None:
        logger.info("Preparando flujo Tarjeta")
        if await self._scroll_to_form_id("TarjetaBLC"):
            return
        await self._search_program_from_generic_page(lead)
        await self._scroll_to_form_id("TarjetaBLC")

    async def _open_hamburger_menu(self) -> bool:
        selectors = [
            "button[aria-label*='menu' i]",
            "button[aria-label*='menú' i]",
            "[role='button'][aria-label*='menu' i]",
            ".hamburger",
            "[class*='hamburger']",
            "button:has(svg)",
        ]

        for selector in selectors:
            items = self.page.locator(selector)
            count = await items.count()
            for i in range(count):
                item = items.nth(i)
                try:
                    box = await item.bounding_box()
                    if not box:
                        continue
                    if box["y"] < 180 or box["x"] > 850:
                        await item.click(force=True, timeout=3000)
                        await self.page.wait_for_timeout(1200)
                        if await self._menu_is_open():
                            logger.info("Menu hamburguesa abierto")
                            return True
                except Exception:
                    continue

        try:
            viewport = self.page.viewport_size or {"width": 1366, "height": 768}
            await self.page.mouse.click(viewport["width"] - 95, 100)
            await self.page.wait_for_timeout(1200)
            return await self._menu_is_open()
        except Exception:
            return False

    async def _menu_is_open(self) -> bool:
        try:
            return await self.page.locator("text='Buscar programa', text='Modalidad'").count() > 0
        except Exception:
            return False

    async def _click_menu_option(self, labels: list[str]) -> bool:
        for label in labels:
            loc = self.page.get_by_text(label, exact=False)
            count = await loc.count()
            for i in range(count):
                item = loc.nth(i)
                try:
                    if await item.is_visible():
                        await item.scroll_into_view_if_needed()
                        await item.click(force=True, timeout=5000)
                        logger.info(f"Menu lateral: click en '{label}'")
                        return True
                except Exception:
                    continue
        return False

    async def _search_program_from_generic_page(self, lead: LeadRow) -> None:
        level = get_level_name(self.country, lead.nivel or "Licenciatura")
        query = self._program_query(level)
        searchers = [
            self.page.get_by_placeholder("Buscar programa"),
            self.page.get_by_role("searchbox"),
            self.page.locator("input[type='search']:visible"),
        ]

        for field in searchers:
            try:
                if await field.count() == 0:
                    continue
                await field.first.click(force=True, timeout=3000)
                await field.first.fill(query, force=True, timeout=3000)
                await self.page.wait_for_timeout(1500)
                await self.page.keyboard.press("ArrowDown")
                await self.page.keyboard.press("Enter")
                await self._soft_wait_network()
                await self.page.wait_for_timeout(2000)
                logger.info(f"Busqueda de tarjeta usada: '{query}'")
                return
            except Exception:
                continue

    async def _scroll_to_form_id(self, form_id: str) -> bool:
        locator = self.page.locator(f"#{form_id}")
        try:
            if await locator.count() == 0:
                return False
            await locator.first.scroll_into_view_if_needed(timeout=8000)
            await self.page.wait_for_timeout(1200)
            if await locator.first.is_visible():
                logger.info(f"Formulario por ID detectado: #{form_id}")
                return True
        except Exception as e:
            logger.debug(f"No se pudo enfocar #{form_id}: {e}")
        return False

    async def _scroll_until_contact_form(self, max_scrolls: int = 14) -> None:
        logger.info("Buscando formulario por scroll progresivo")
        for _ in range(max_scrolls):
            if await self._visible_contact_form_exists():
                logger.info("Formulario de contacto visible encontrado")
                return
            await self.page.evaluate("window.scrollBy(0, Math.round(window.innerHeight * 0.75))")
            await self.page.wait_for_timeout(600)
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await self.page.wait_for_timeout(1500)

    async def _visible_contact_form_exists(self) -> bool:
        return await self.page.evaluate(
            """
            () => {
                const visible = (el) => {
                    const s = window.getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    return s.display !== 'none' && s.visibility !== 'hidden'
                        && r.width > 0 && r.height > 0 && !el.disabled
                        && el.type !== 'hidden';
                };
                const fields = Array.from(document.querySelectorAll('input, select, textarea'))
                    .filter(visible)
                    .map(el => `${el.name || ''} ${el.id || ''} ${el.placeholder || ''}`.toLowerCase());
                return fields.some(x => x.includes('email') || x.includes('correo'))
                    && fields.some(x => x.includes('phone') || x.includes('tel'))
                    && fields.some(x => x.includes('name') || x.includes('nombre'));
            }
            """
        )

    async def _find_form_scope(self, form_type: str) -> Optional[Locator]:
        preferred_ids = []
        mapped = FORM_IDS.get(form_type)
        if mapped:
            preferred_ids.append(mapped)
        preferred_ids.extend(["FooterBLC", "LateralBLC", "TarjetaBLC"])

        for form_id in dict.fromkeys(preferred_ids):
            form = self.page.locator(f"#{form_id}")
            try:
                if await form.count() > 0 and await form.first.is_visible():
                    logger.info(f"Usando formulario #{form_id}")
                    return form.first
            except Exception:
                continue

        forms = self.page.locator("form:visible")
        count = await forms.count()
        best = None
        best_score = -1
        for i in range(count):
            form = forms.nth(i)
            score = await self._score_form(form)
            if score > best_score:
                best = form
                best_score = score

        if best and best_score > 0:
            logger.info(f"Usando formulario visible por score={best_score}")
            return best

        body = self.page.locator("body")
        logger.warning("Fallback a body como scope de formulario")
        return body

    async def _score_form(self, form: Locator) -> int:
        try:
            return await form.evaluate(
                """
                (root) => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden'
                            && r.width > 0 && r.height > 0 && !el.disabled
                            && el.type !== 'hidden';
                    };
                    let score = 0;
                    for (const el of Array.from(root.querySelectorAll('input, select, textarea'))) {
                        if (!visible(el)) continue;
                        const key = `${el.name || ''} ${el.id || ''} ${el.placeholder || ''}`.toLowerCase();
                        if (key.includes('email') || key.includes('correo')) score += 4;
                        if (key.includes('phone') || key.includes('tel')) score += 4;
                        if (key.includes('name') || key.includes('nombre')) score += 3;
                        if (key.includes('modality') || key.includes('area') || key.includes('program')) score += 2;
                    }
                    return score;
                }
                """
            )
        except Exception:
            return 0

    async def _fill_form(self, test_email: str, level: str) -> bool:
        logger.info("Llenando formulario en orden dependiente")

        await self._select_field("modality", preferred=[level, "En linea", "En línea", "Online"])
        await self.page.wait_for_timeout(4000)

        await self._select_field("area", preferred=[level])
        await self.page.wait_for_timeout(4000)

        await self._fill_program(level)
        await self.page.wait_for_timeout(1200)

        await self._set_input(["#first_name", "input[name='first_name']", "input[name='name']"], self.country.fake_name, "nombre")
        await self._set_input(["#email", "input[name='email']", "input[type='email']"], test_email, "email")
        await self._set_input(["#phone", "input[name='phone']", "input[type='tel']"], self.country.fake_phone, "telefono")
        await self._check_privacy()

        state = await self._form_state()
        logger.info(f"Estado final antes de submit: {state}")

        missing = [
            key for key in ["first_name", "email", "phone"]
            if not state.get(key)
        ]
        if missing:
            logger.warning(f"Faltan campos de contacto: {missing}")
            return False

        if state.get("has_checkbox") and not state.get("checkbox_checked"):
            logger.warning("Checkbox de privacidad no quedo marcado")
            return False

        return True

    async def _select_field(self, field_name: str, preferred: list[str]) -> bool:
        select = self._scope().locator(f"select[name='{field_name}'], select#{field_name}, select[id*='{field_name}' i]")
        if await select.count() == 0:
            logger.info(f"Select {field_name} no existe en este formulario")
            return False

        locator = select.first
        await self._wait_select_real_options(locator, field_name)
        chosen = await locator.evaluate(
            """
            (select, preferred) => {
                const bad = new Set(['', '-', '--', 'seleccionar', 'selecciona', 'select', 'choose']);
                const clean = (s) => String(s || '').trim();
                const norm = (s) => clean(s).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                const options = Array.from(select.options || [])
                    .map((option, index) => ({
                        index,
                        text: clean(option.textContent),
                        value: clean(option.value),
                        disabled: option.disabled
                    }))
                    .filter((option) => {
                        const t = norm(option.text);
                        const v = norm(option.value);
                        return !option.disabled && !bad.has(t) && !bad.has(v)
                            && !t.endsWith(':') && option.index > 0;
                    });

                if (!options.length) return null;

                let chosen = null;
                for (const wantedRaw of preferred || []) {
                    const wanted = norm(wantedRaw);
                    if (!wanted) continue;
                    chosen = options.find((option) => {
                        const text = norm(option.text);
                        const value = norm(option.value);
                        return text.includes(wanted) || value.includes(wanted) || wanted.includes(text);
                    });
                    if (chosen) break;
                }
                chosen = chosen || options[0];
                select.selectedIndex = chosen.index;
                select.value = chosen.value;
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
                select.dispatchEvent(new Event('blur', { bubbles: true }));
                return chosen;
            }
            """,
            preferred,
        )

        if chosen:
            logger.info(f"Select {field_name}: {chosen}")
            return True

        logger.warning(f"Select {field_name} sin opciones reales")
        return False

    async def _wait_select_real_options(self, select: Locator, field_name: str, timeout_ms: int = 10000) -> None:
        try:
            await self.page.wait_for_function(
                """
                ([select, fieldName]) => {
                    const bad = new Set(['', '-', '--', 'seleccionar', 'selecciona', 'select', 'choose']);
                    const norm = (s) => String(s || '').trim().toLowerCase();
                    const real = Array.from(select.options || []).filter((option, index) => {
                        const text = norm(option.textContent);
                        const value = norm(option.value);
                        return index > 0 && !option.disabled && !bad.has(text)
                            && !bad.has(value) && !text.endsWith(':');
                    });
                    return fieldName !== 'area' || real.length > 0;
                }
                """,
                [await select.element_handle(), field_name],
                timeout=timeout_ms,
            )
        except Exception:
            logger.debug(f"Select {field_name}: no se confirmaron opciones dinamicas en espera")

    async def _fill_program(self, level: str) -> bool:
        select_done = await self._select_field("program", preferred=[level, self._program_query(level)])
        if select_done:
            return True

        field = self._scope().locator("#program, input[name='program'], input[placeholder*='programa' i], input[placeholder*='interes' i], input[placeholder*='interés' i]")
        if await field.count() == 0:
            logger.info("Campo program no existe en este formulario")
            return False

        query = self._program_query(level)
        input_field = field.first
        try:
            await input_field.scroll_into_view_if_needed(timeout=5000)
            await input_field.click(force=True, timeout=5000)
            await input_field.fill(query, force=True, timeout=5000)
            await input_field.press("ArrowDown")
            await input_field.press("Enter")
            await self.page.wait_for_timeout(1500)
            logger.info(f"Programa escrito/seleccionado con query '{query}'")
            return True
        except Exception as e:
            logger.warning(f"No se pudo llenar program con accion directa: {e}")
            await self._set_value_dom(input_field, query, "program")
            return True

    def _program_query(self, level: str) -> str:
        key = (level or "").strip().lower()
        return PROGRAM_SEARCH_BY_LEVEL.get(key, "Administracion")

    async def _set_input(self, selectors: list[str], value: str, label: str) -> bool:
        field = await self._first_existing(selectors)
        if not field:
            logger.warning(f"Campo {label} no encontrado")
            return False

        try:
            await field.scroll_into_view_if_needed(timeout=5000)
            await field.fill(value, force=True, timeout=5000)
            current = await field.input_value(timeout=3000)
            if current.strip():
                logger.info(f"Campo {label} completado")
                return True
        except Exception as e:
            logger.debug(f"fill directo fallo para {label}: {e}")

        return await self._set_value_dom(field, value, label)

    async def _set_value_dom(self, field: Locator, value: str, label: str) -> bool:
        try:
            await field.evaluate(
                """
                (el, value) => {
                    const proto = el.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (descriptor && descriptor.set) descriptor.set.call(el, value);
                    else el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                }
                """,
                value,
            )
            logger.info(f"Campo {label} completado por DOM")
            return True
        except Exception as e:
            logger.warning(f"No se pudo completar {label}: {e}")
            return False

    async def _check_privacy(self) -> bool:
        candidates = [
            self._scope().locator("input[type='checkbox']"),
            self._scope().locator(".chakra-checkbox__control"),
            self._scope().locator("[class*='checkbox']"),
        ]

        for candidate in candidates:
            count = await candidate.count()
            for i in range(count):
                item = candidate.nth(i)
                try:
                    await item.scroll_into_view_if_needed(timeout=3000)
                    await item.click(force=True, timeout=3000)
                    logger.info("Checkbox privacidad marcado")
                    return True
                except Exception:
                    continue

        logger.warning("Checkbox privacidad no encontrado")
        return False

    async def _submit_form(self) -> bool:
        buttons = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Calcula tu beca')",
            "button:has-text('Enviar información')",
            "button:has-text('Enviar informacion')",
            "button:has-text('Solicitar información')",
            "button:has-text('Solicitar informacion')",
            "button:has-text('Enviar')",
        ]

        for selector in buttons:
            button = self._scope().locator(selector)
            if await button.count() == 0:
                continue
            try:
                await button.first.scroll_into_view_if_needed(timeout=5000)
                await button.first.click(force=True, timeout=5000)
                logger.info(f"Submit ejecutado con selector {selector}")
                return True
            except Exception as e:
                logger.debug(f"Submit fallo con {selector}: {e}")

        logger.warning("No se encontro boton de submit")
        return False

    async def _form_state(self) -> dict:
        try:
            return await self._scope().evaluate(
                """
                (root) => {
                    const pick = (selector) => root.querySelector(selector)?.value?.trim() || '';
                    const checkbox = root.querySelector("input[type='checkbox']");
                    return {
                        modality: pick("select[name='modality'], select#modality"),
                        area: pick("select[name='area'], select#area"),
                        program: pick("select[name='program'], select#program, input[name='program'], input#program"),
                        first_name: pick("input#first_name, input[name='first_name'], input[name='name']"),
                        email: pick("input#email, input[name='email'], input[type='email']"),
                        phone: pick("input#phone, input[name='phone'], input[type='tel']"),
                        has_checkbox: Boolean(checkbox),
                        checkbox_checked: checkbox ? checkbox.checked : true
                    };
                }
                """
            )
        except Exception as e:
            logger.debug(f"No se pudo leer estado del formulario: {e}")
            return {}

    async def _log_fields(self, moment: str) -> None:
        try:
            fields = await self._scope().evaluate(
                """
                (root) => Array.from(root.querySelectorAll('input, select, textarea')).map((el) => ({
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    value: el.type === 'password' ? '***' : (el.value || ''),
                    options: el.tagName === 'SELECT'
                        ? Array.from(el.options || []).map(o => ({
                            text: (o.textContent || '').trim(),
                            value: o.value || ''
                        })).slice(0, 10)
                        : []
                }))
                """
            )
            logger.info(f"Campos del formulario {moment}: {fields}")
        except Exception as e:
            logger.debug(f"No se pudieron listar campos {moment}: {e}")

    def _scope(self) -> Locator:
        return self.form_scope or self.page.locator("body")

    async def _first_existing(self, selectors: list[str]) -> Optional[Locator]:
        scope = self._scope()
        for selector in selectors:
            locator = scope.locator(selector)
            try:
                if await locator.count() > 0:
                    return locator.first
            except Exception:
                continue
        return None
