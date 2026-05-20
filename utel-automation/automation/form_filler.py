# ============================================================
# automation/form_filler.py
# Llena formularios UTEL sin cambiar el frontend del sistema.
# Estrategia:
#   1. Usar Location para abrir el formulario correcto.
#   2. Usar Nivel de Sheets como fuente principal del producto.
#   3. Llenar dentro del form detectado, no en toda la pagina.
#   4. Respetar dependencias: modality -> area -> program -> contacto.
# ============================================================

import unicodedata
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
    "licenciatura": "Licenciatura",
    "licenciaturas": "Licenciatura",
    "doctorado": "Doctorado",
    "doctorados": "Doctorado",
    "maestria": "Maestria",
    "maestrias": "Maestria",
    "maestria ejecutiva": "Maestria ejecutiva",
    "maestrias ejecutivas": "Maestria ejecutiva",
    "licenciatura hibrida": "Licenciatura hibrida",
    "licenciaturas hibridas": "Licenciatura hibrida",
    "bootcamp": "Bootcamp",
    "bootcamps": "Bootcamp",
    "bachillerato": "Bachillerato",
    "doble titulacion mex usa": "Doble titulacion",
    "doble titulacion mexusa": "Doble titulacion",
}

LEVEL_ALIASES = {
    "Licenciatura": ["Licenciatura", "Licenciaturas"],
    "Doctorado": ["Doctorado", "Doctorados"],
    "Maestria": ["Maestria", "Maestrias", "Maestría", "Maestrías", "Master", "Máster"],
    "Maestrias ejecutivas": [
        "Maestrias ejecutivas",
        "Maestrías ejecutivas",
        "Maestria ejecutiva",
        "Maestría ejecutiva",
    ],
    "Licenciaturas hibridas": [
        "Licenciaturas hibridas",
        "Licenciaturas híbridas",
        "Licenciatura hibrida",
        "Licenciatura híbrida",
        "Modalidad Hibrida",
        "Modalidad Híbrida",
    ],
    "Bootcamps": ["Bootcamps", "Bootcamp"],
    "Bachillerato": ["Bachillerato"],
    "Doble titulacion Mex-USA": [
        "Doble titulacion Mex-USA",
        "Doble titulación Mex-USA",
        "Doble titulacion",
        "Doble titulación",
        "Mex-USA",
    ],
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
            raw_level = lead.nivel or infer_level_from_url(lead.landing_url) or ""
            level = self._canonical_level(get_level_name(self.country, raw_level) or raw_level)

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
                await self._prepare_tarjeta_flow(level)
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
        raw = self._norm(form_type).replace(" ", "")
        if raw in ["formlp", "form"]:
            return "formlp"
        if raw in ["targeta", "tarjeta"]:
            return "tarjeta"
        return raw

    def _norm(self, value: str) -> str:
        text = str(value or "").strip().lower()
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        return "".join(ch for ch in text if ch.isalnum() or ch.isspace()).strip()

    def _canonical_level(self, level: str) -> str:
        raw = (level or "").strip()
        normalized = self._norm(raw)
        for canonical, aliases in LEVEL_ALIASES.items():
            if normalized in {self._norm(alias) for alias in aliases}:
                return canonical
        return raw

    def _level_preferences(self, level: str) -> list[str]:
        canonical = self._canonical_level(level)
        preferences = [level, canonical]
        preferences.extend(LEVEL_ALIASES.get(canonical, []))
        return list(dict.fromkeys([item for item in preferences if item]))

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

        opened = await self._open_lateral_cta()
        if not opened:
            logger.warning("Location=Lateral: no se pudo hacer click en Solicitar informacion")
            return

        if await self._wait_for_lateral_panel():
            return

        logger.warning("Location=Lateral: se hizo click, pero no aparecio el panel lateral requerido")

    async def _prepare_tarjeta_flow(self, level: str) -> None:
        logger.info("Preparando flujo Tarjeta")
        if await self._scroll_to_form_id("TarjetaBLC"):
            return

        await self._search_program_from_generic_page(level)
        await self._soft_wait_network()
        await self.page.wait_for_timeout(2500)
        await self._scroll_to_form_id("TarjetaBLC")

    async def _open_lateral_cta(self) -> bool:
        clicked = await self.page.evaluate(
            """
            () => {
                const normalize = (value) => String(value || '')
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '')
                    .toLowerCase()
                    .trim();
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    const box = el.getBoundingClientRect();
                    return style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && box.width > 0
                        && box.height > 0;
                };

                const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                const candidates = Array.from(document.querySelectorAll('a, button, [role=button]'))
                    .filter(visible)
                    .map((el) => ({ el, box: el.getBoundingClientRect(), text: normalize(el.textContent) }))
                    .filter(({ text }) => text.includes('solicitar informacion'))
                    .sort((a, b) => {
                        const aTopScore = a.box.top < 180 ? 0 : 1;
                        const bTopScore = b.box.top < 180 ? 0 : 1;
                        if (aTopScore !== bTopScore) return aTopScore - bTopScore;
                        return Math.abs(viewportWidth - a.box.right) - Math.abs(viewportWidth - b.box.right);
                    });

                const target = candidates[0]?.el;
                if (!target) return false;
                target.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
                target.click();
                return true;
            }
            """
        )

        if clicked:
            await self.page.wait_for_timeout(1800)
            logger.info("Click ejecutado en CTA visible 'Solicitar informacion'")
            return True

        logger.warning("No se encontro CTA 'Solicitar informacion' para formulario lateral")
        return False

    async def _wait_for_lateral_panel(self, timeout_ms: int = 7000) -> bool:
        attempts = max(int(timeout_ms / 350), 1)
        for _ in range(attempts):
            if await self._scroll_to_form_id("LateralBLC"):
                return True
            if await self._lateral_panel_is_open():
                return True
            await self.page.wait_for_timeout(350)
        return False

    async def _lateral_panel_is_open(self) -> bool:
        try:
            return await self.page.evaluate(
                """
                () => {
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0;
                    };
                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    const candidates = Array.from(document.querySelectorAll('aside, section, form, div'))
                        .filter(visible)
                        .map((el) => ({ el, box: el.getBoundingClientRect(), text: el.textContent || '' }))
                        .filter(({ box }) => box.left > viewportWidth * 0.55 || box.right > viewportWidth * 0.85)
                        .filter(({ text }) => /tu meta esta cerca|tu meta está cerca|completa el formulario|modalidad|area de interes|área de interés/i.test(text));

                    return candidates.some(({ el }) => {
                        const fields = Array.from(el.querySelectorAll('input, select, textarea')).filter(visible);
                        const keys = fields.map((field) =>
                            `${field.name || ''} ${field.id || ''} ${field.placeholder || ''}`.toLowerCase()
                        );
                        return keys.some((x) => x.includes('email') || x.includes('correo'))
                            && keys.some((x) => x.includes('phone') || x.includes('tel'))
                            && keys.some((x) => x.includes('name') || x.includes('nombre'));
                    });
                }
                """
            )
        except Exception as e:
            logger.debug(f"No se pudo detectar panel lateral: {e}")
            return False

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

    async def _search_program_from_generic_page(self, level: str) -> None:
        query = self._program_query(level)
        searchers = [
            self.page.get_by_placeholder("Buscar programa"),
            self.page.get_by_role("searchbox"),
            self.page.locator("input[type='search']:visible"),
            self.page.locator("input[placeholder*='programa' i]:visible"),
        ]

        for field in searchers:
            try:
                if await field.count() == 0:
                    continue
                await field.first.click(force=True, timeout=3000)
                await field.first.fill(query, force=True, timeout=3000)
                await self.page.wait_for_timeout(1500)
                clicked = await self._click_search_result_for_level(level)
                if not clicked:
                    await self.page.keyboard.press("ArrowDown")
                    await self.page.keyboard.press("Enter")
                logger.info(f"Busqueda de tarjeta usada: '{query}'")
                return
            except Exception as e:
                logger.debug(f"Buscador no usable para tarjeta: {e}")

        logger.warning("No se pudo usar el buscador global para flujo Tarjeta")

    async def _click_search_result_for_level(self, level: str) -> bool:
        terms = self._level_preferences(level)
        try:
            clicked = await self.page.evaluate(
                """
                (terms) => {
                    const normalize = (value) => String(value || '')
                        .normalize('NFD')
                        .replace(/[\\u0300-\\u036f]/g, '')
                        .toLowerCase()
                        .trim();
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0;
                    };
                    const wanted = terms.map(normalize).filter(Boolean);
                    const candidates = Array.from(document.querySelectorAll(
                        'a, button, [role=option], [role=menuitem], li, div'
                    )).filter(visible);
                    const result = candidates.find((el) => {
                        const text = normalize(el.textContent);
                        return text && wanted.some((term) => text.includes(term));
                    });
                    if (!result) return false;
                    result.click();
                    return true;
                }
                """,
                terms,
            )
            if clicked:
                logger.info(f"Resultado de tarjeta seleccionado para nivel '{level}'")
            return bool(clicked)
        except Exception as e:
            logger.debug(f"No se pudo seleccionar resultado de tarjeta: {e}")
            return False

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
        if form_type == "lateral":
            lateral = self.page.locator("#LateralBLC")
            try:
                if await lateral.count() > 0 and await lateral.first.is_visible():
                    logger.info("Usando formulario #LateralBLC")
                    return lateral.first
            except Exception:
                pass

            lateral_panel = await self._find_lateral_panel_scope()
            if lateral_panel:
                logger.info("Usando panel lateral visible como scope de formulario")
                return lateral_panel

            logger.warning("Location=Lateral, pero no se encontro formulario/panel lateral usable")
            return None

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

    async def _find_lateral_panel_scope(self) -> Optional[Locator]:
        panels = self.page.locator("aside:visible, section:visible, form:visible, div:visible")
        count = await panels.count()
        for i in range(count):
            panel = panels.nth(i)
            try:
                score = await panel.evaluate(
                    """
                    (el) => {
                        const visible = (node) => {
                            const style = window.getComputedStyle(node);
                            const box = node.getBoundingClientRect();
                            return style.display !== 'none'
                                && style.visibility !== 'hidden'
                                && box.width > 0
                                && box.height > 0;
                        };
                        const box = el.getBoundingClientRect();
                        const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                        if (box.left < viewportWidth * 0.50 && box.right < viewportWidth * 0.85) return 0;

                        const text = String(el.textContent || '').toLowerCase();
                        let score = /tu meta est|completa el formulario|modalidad|area de interes|área de interés/.test(text) ? 5 : 0;
                        const fields = Array.from(el.querySelectorAll('input, select, textarea')).filter(visible);
                        const keys = fields.map((field) =>
                            `${field.name || ''} ${field.id || ''} ${field.placeholder || ''}`.toLowerCase()
                        );
                        if (keys.some((x) => x.includes('email') || x.includes('correo'))) score += 4;
                        if (keys.some((x) => x.includes('phone') || x.includes('tel'))) score += 4;
                        if (keys.some((x) => x.includes('name') || x.includes('nombre'))) score += 3;
                        if (keys.some((x) => x.includes('modality') || x.includes('area') || x.includes('program'))) score += 2;
                        return score;
                    }
                    """
                )
                if score >= 12:
                    return panel
            except Exception:
                continue
        return None

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

        level_preferences = self._level_preferences(level)

        await self._select_field("modality", preferred=["En linea", "En línea", "Online"])
        await self.page.wait_for_timeout(4000)

        area_exists = await self._select_exists("area")
        area_ok = await self._select_field(
            "area",
            preferred=level_preferences,
            require_preferred_match=True,
        )
        if area_exists and not area_ok:
            logger.warning(f"No se pudo seleccionar el nivel requerido en Area: {level}")
            return False
        await self.page.wait_for_timeout(4000)

        await self._fill_program(level, level_preferences)
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

    async def _select_exists(self, field_name: str) -> bool:
        select = self._scope().locator(f"select[name='{field_name}'], select#{field_name}, select[id*='{field_name}' i]")
        return await select.count() > 0

    async def _select_field(
        self,
        field_name: str,
        preferred: list[str],
        require_preferred_match: bool = False,
    ) -> bool:
        select = self._scope().locator(f"select[name='{field_name}'], select#{field_name}, select[id*='{field_name}' i]")
        if await select.count() == 0:
            logger.info(f"Select {field_name} no existe en este formulario")
            return False

        locator = select.first
        await self._wait_select_real_options(locator, field_name)
        chosen = await locator.evaluate(
            """
            (select, payload) => {
                const { preferred, requirePreferredMatch } = payload;
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
                let matched = false;
                for (const wantedRaw of preferred || []) {
                    const wanted = norm(wantedRaw);
                    if (!wanted) continue;
                    chosen = options.find((option) => {
                        const text = norm(option.text);
                        const value = norm(option.value);
                        return text === wanted || value === wanted;
                    });
                    if (chosen) {
                        matched = true;
                        break;
                    }
                    chosen = options.find((option) => {
                        const text = norm(option.text);
                        const value = norm(option.value);
                        return text.includes(wanted) || value.includes(wanted) || wanted.includes(text);
                    });
                    if (chosen) {
                        matched = true;
                        break;
                    }
                }

                if (requirePreferredMatch && !matched) return null;
                chosen = chosen || options[0];
                select.selectedIndex = chosen.index;
                select.value = chosen.value;
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
                select.dispatchEvent(new Event('blur', { bubbles: true }));
                return { ...chosen, matched };
            }
            """,
            {
                "preferred": preferred,
                "requirePreferredMatch": require_preferred_match,
            },
        )

        if chosen:
            logger.info(f"Select {field_name}: {chosen}")
            return True

        logger.warning(f"Select {field_name} sin opcion compatible con {preferred}")
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

    async def _fill_program(self, level: str, level_preferences: list[str]) -> bool:
        select_done = await self._select_field(
            "program",
            preferred=[*level_preferences, self._program_query(level)],
        )
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
        key = self._norm(level)
        return PROGRAM_SEARCH_BY_LEVEL.get(key, level or "Licenciatura")

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
            self._scope().locator("label:has-text('Política de Privacidad')"),
            self._scope().locator("label:has-text('Politica de Privacidad')"),
            self._scope().locator("label:has-text('Privacidad')"),
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
                    if await self._privacy_is_checked():
                        logger.info("Checkbox privacidad marcado")
                        return True
                except Exception:
                    continue

        try:
            checked = await self._scope().evaluate(
                """
                (root) => {
                    const checkbox = Array.from(root.querySelectorAll("input[type='checkbox']"))[0];
                    if (checkbox) {
                        checkbox.checked = true;
                        checkbox.setAttribute('checked', 'checked');
                        checkbox.dispatchEvent(new Event('input', { bubbles: true }));
                        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                        checkbox.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        if (!checkbox.checked) checkbox.checked = true;
                        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                        return checkbox.checked;
                    }
                    const target = Array.from(root.querySelectorAll('label, span, div, p'))
                        .find((el) => /privacidad|politica|política/i.test(el.textContent || ''));
                    if (!target) return false;
                    target.click();
                    return true;
                }
                """
            )
            if checked:
                logger.info("Checkbox privacidad marcado por DOM")
                return True
        except Exception as e:
            logger.debug(f"Checkbox privacidad por DOM fallo: {e}")

        logger.warning("Checkbox privacidad no encontrado")
        return False

    async def _privacy_is_checked(self) -> bool:
        try:
            return await self._scope().evaluate(
                """
                (root) => {
                    const checkbox = root.querySelector("input[type='checkbox']");
                    return checkbox ? Boolean(checkbox.checked) : true;
                }
                """
            )
        except Exception:
            return False

    async def _submit_form(self) -> bool:
        buttons = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Calcula tu beca')",
            "button:has-text('Enviar información')",
            "button:has-text('Enviar informacion')",
            "button:has-text('Continua por Whatsapp')",
            "button:has-text('Continúa por Whatsapp')",
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
