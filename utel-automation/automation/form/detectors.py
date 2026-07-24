"""FormDetector — detección de tipo, scope y estado de formularios."""

from typing import Optional

from playwright.async_api import Page, Locator
from loguru import logger

from config.countries import Country, get_level_name
from automation.form.form_utils import canonical_level, get_form_id


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

        form_id = get_form_id(form_type)
        if not form_id:
            logger.warning(f"No hay form_id mapeado para tipo '{form_type}'")
            return None

        form = self.page.locator(f"#{form_id}")
        try:
            if await form.count() > 0 and await form.first.is_visible():
                logger.info(f"Usando formulario #{form_id}")
                self.form_scope = form.first
                return self.form_scope
        except Exception as e:
            logger.warning(f"No se pudo acceder al formulario #{form_id}: {e}")

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
