"""FormDetector — detección de tipo, scope y estado de formularios."""

from typing import Optional

from playwright.async_api import Page, Locator
from loguru import logger

from config.countries import Country, get_level_name
from automation.form.form_utils import FORM_IDS, canonical_level, get_form_id


class FormDetector:
    """Detecta y analiza formularios en landing pages."""

    def __init__(self, page: Page, country: Country):
        self.page = page
        self.country = country
        self.form_scope: Optional[Locator] = None
        self.form_type: str = ""

    def resolve_level(self, lead_nivel: str, landing_url: str) -> str:
        raw_level = lead_nivel or ""
        level_name = get_level_name(self.country, raw_level) or raw_level
        return canonical_level(level_name)

    async def detect_form_scope(self, form_type: str, tarjeta_product_opened: bool = False) -> Optional[Locator]:
        self.form_type = form_type

        if form_type == "tarjeta" and not tarjeta_product_opened:
            logger.warning("Tarjeta: no se abrio LP de producto; no se llenara formulario")
            return None

        if form_type == "lateral":
            lateral = self.page.locator("#LateralBLC")
            try:
                if await lateral.count() > 0 and await lateral.first.is_visible():
                    logger.info("Usando formulario #LateralBLC")
                    self.form_scope = lateral.first
                    return self.form_scope
            except Exception:
                pass

            panel = await self._find_lateral_panel_scope()
            if panel:
                logger.info("Usando panel lateral visible como scope")
                self.form_scope = panel
                return self.form_scope

            logger.warning("Lateral: no se encontro formulario usable")
            return None

        preferred_ids = []
        mapped = get_form_id(form_type)
        if mapped:
            preferred_ids.append(mapped)
        preferred_ids.extend(["FooterBLC", "LateralBLC", "TarjetaBLC"])

        for form_id in dict.fromkeys(preferred_ids):
            form = self.page.locator(f"#{form_id}")
            try:
                if await form.count() > 0 and await form.first.is_visible():
                    logger.info(f"Usando formulario #{form_id}")
                    self.form_scope = form.first
                    return self.form_scope
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
            self.form_scope = best
            return self.form_scope

        body = self.page.locator("body")
        logger.warning("Fallback a body como scope de formulario")
        self.form_scope = body
        return self.form_scope

    async def _score_form(self, form: Locator) -> int:
        try:
            return await form.evaluate("""
                (root) => {
                    let score = 0;
                    for (const el of Array.from(root.querySelectorAll('input, select, textarea'))) {
                        const visible = (el) => {
                            const s = window.getComputedStyle(el);
                            const r = el.getBoundingClientRect();
                            return s.display !== 'none' && s.visibility !== 'hidden'
                                && r.width > 0 && r.height > 0 && !el.disabled
                                && el.type !== 'hidden';
                        };
                        if (!visible(el)) continue;
                        const key = `${el.name || ''} ${el.id || ''} ${el.placeholder || ''}`.toLowerCase();
                        if (key.includes('email') || key.includes('correo')) score += 4;
                        if (key.includes('phone') || key.includes('tel')) score += 4;
                        if (key.includes('name') || key.includes('nombre')) score += 3;
                        if (key.includes('modality') || key.includes('area') || key.includes('program')) score += 2;
                    }
                    return score;
                }
            """)
        except Exception:
            return 0

    async def _find_lateral_panel_scope(self) -> Optional[Locator]:
        panels = self.page.locator("aside:visible, section:visible, form:visible, div:visible")
        count = await panels.count()
        for i in range(count):
            panel = panels.nth(i)
            try:
                score = await panel.evaluate("""
                    (el) => {
                        const visible = (node) => {
                            const style = window.getComputedStyle(node);
                            const box = node.getBoundingClientRect();
                            return style.display !== 'none' && style.visibility !== 'hidden'
                                && box.width > 0 && box.height > 0;
                        };
                        const box = el.getBoundingClientRect();
                        const vpw = window.innerWidth || document.documentElement.clientWidth;
                        if (box.left < vpw * 0.50 && box.right < vpw * 0.85) return 0;
                        const text = String(el.textContent || '').toLowerCase();
                        let score = /tu meta est|completa el formulario|modalidad|area de interes/.test(text) ? 5 : 0;
                        const fields = Array.from(el.querySelectorAll('input, select, textarea')).filter(visible);
                        const keys = fields.map(f => `${f.name || ''} ${f.id || ''} ${f.placeholder || ''}`.toLowerCase());
                        if (keys.some(x => x.includes('email') || x.includes('correo'))) score += 4;
                        if (keys.some(x => x.includes('phone') || x.includes('tel'))) score += 4;
                        if (keys.some(x => x.includes('name') || x.includes('nombre'))) score += 3;
                        if (keys.some(x => x.includes('modality') || x.includes('area') || x.includes('program'))) score += 2;
                        return score;
                    }
                """)
                if score >= 12:
                    return panel
            except Exception:
                continue
        return None

    async def read_form_state(self) -> dict:
        try:
            return await (self.form_scope or self.page.locator("body")).evaluate("""
                (root) => {
                    const pick = (sel) => root.querySelector(sel)?.value?.trim() || '';
                    const checkbox = root.querySelector("input[type='checkbox']");
                    return {
                        modality: pick("select[name='modality'], select#modality"),
                        area: pick("select[name='area'], select#area"),
                        program: pick("select[name='program'], select#program, input[name='program'], input#program"),
                        first_name: pick("#first_name, input[name='first_name'], input[name='name'], input[name*='nombre' i], input[id*='nombre' i]"),
                        email: pick("#email, input[name='email'], input[type='email'], input[name*='correo' i], input[id*='correo' i]"),
                        phone: pick("#phone, input[name='phone'], input[type='tel'], input[name*='telefono' i], input[id*='telefono' i], input[name*='celular' i], input[id*='celular' i], input[name*='mobile' i]"),
                        has_checkbox: Boolean(checkbox),
                        checkbox_checked: checkbox ? checkbox.checked : true,
                    };
                }
            """)
        except Exception as e:
            logger.debug(f"No se pudo leer estado del formulario: {e}")
            return {}

    async def log_fields(self, moment: str) -> None:
        try:
            fields = await (self.form_scope or self.page.locator("body")).evaluate("""
                (root) => Array.from(root.querySelectorAll('input, select, textarea')).map((el) => ({
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    value: el.type === 'password' ? '***' : (el.value || ''),
                    options: el.tagName === 'SELECT'
                        ? Array.from(el.options || []).map(o => ({ text: (o.textContent || '').trim(), value: o.value || '' })).slice(0, 10)
                        : [],
                }))
            """)
            logger.info(f"Campos del formulario {moment}: {fields}")
        except Exception as e:
            logger.debug(f"No se pudieron listar campos {moment}: {e}")
