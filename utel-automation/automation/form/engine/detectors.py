"""FormDetector — detección de tipo, scope y estado de formularios."""

import json
from typing import Optional

from playwright.async_api import Page, Locator
from loguru import logger

from config.countries import Country
from config.form_configs import FORM_STATE_SELECTORS
from automation.form.engine.form_utils import get_form_id


class FormDetector:
    """Detecta y analiza formularios en landing pages."""

    # Page + pais + scope opcional (se asigna luego si es None)
    def __init__(self, page: Page, country: Country, form_scope: Optional[Locator] = None):
        self.page = page
        self.country = country
        self.form_scope = form_scope
        self.form_type: str = ""


    # Localiza el contenedor del formulario por form_type. Retorna el scope o None.
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


    # Lee valores actuales de campos: modalidad, area, programa, nombre, email, telefono + checkbox
    async def read_form_state(self) -> dict:
        try:
            selectors_json = json.dumps(FORM_STATE_SELECTORS)
            return await (self.form_scope or self.page.locator("body")).evaluate(f"""
                (root) => {{
                    const sel = {selectors_json};
                    const pick = (s) => root.querySelector(s)?.value?.trim() || '';
                    const cb = root.querySelector("input[type='checkbox']");
                    return {{
                        modality: pick(sel.modality),
                        area: pick(sel.area),
                        program: pick(sel.program),
                        first_name: pick(sel.first_name),
                        email: pick(sel.email),
                        phone: pick(sel.phone),
                        has_checkbox: Boolean(cb),
                        checkbox_checked: cb ? cb.checked : true
                    }};
                }}
            """)
        except Exception as e:
            logger.debug(f"No se pudo leer estado del formulario: {e}")
            return {}
            

 # Loguea todos los input/select/textarea del scope para debugging
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
