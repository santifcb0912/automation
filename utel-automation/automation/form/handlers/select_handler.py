"""SelectHandler — maneja selección en <select> nativos y programáticos."""

from typing import Optional
from playwright.async_api import Locator, Page
from loguru import logger

_SELECT_JS_FN = """(el, payload) => {
    const norm = s => String(s || '').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
    const clean = s => String(s || '').trim();
    const bad = new Set(['', '-', '--', 'seleccionar', 'selecciona', 'select', 'choose']);
    const options = Array.from(el.options || [])
        .map((opt, i) => ({ index: i, text: clean(opt.textContent), value: clean(opt.value), disabled: opt.disabled }))
        .filter(opt => {
            const t = norm(opt.text), v = norm(opt.value);
            return !opt.disabled && !bad.has(t) && !bad.has(v) && !t.endsWith(':') && opt.index > 0;
        });
    if (!options.length) return null;
    let chosen = null;
    for (const raw of payload.preferred || []) {
        const wanted = norm(raw);
        if (!wanted) continue;
        let found = options.find(o => norm(o.text) === wanted || norm(o.value) === wanted);
        if (found) { chosen = { ...found, matched: true }; break; }
        found = options.find(o => norm(o.text).includes(wanted) || norm(o.value).includes(wanted) || wanted.includes(norm(o.text)));
        if (found) { chosen = { ...found, matched: true }; break; }
    }
    if (payload.requirePreferredMatch && !chosen?.matched) return null;
    chosen = chosen || options[0];
    el.selectedIndex = chosen.index;
    el.value = chosen.value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
    return { ...chosen, matched: chosen?.matched || false };
}"""


class SelectHandler:
    """Maneja la interacción con elementos <select> en formularios."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    # Verifica si un <select> existe en el formulario por su name/id
    async def exists(self, field_name: str) -> bool:
        select = self.form_scope.locator(
            f"select[name='{field_name}'], select#{field_name}, select[id*='{field_name}' i]"
        )
        return await select.count() > 0

    # Selecciona una opcion en un <select> por nombre del campo; retorna True/False
    async def select(
        self,
        field_name: str,
        preferred: list[str],
        require_preferred_match: bool = False,
    ) -> bool:
        select = self.form_scope.locator(
            f"select[name='{field_name}'], select#{field_name}, select[id*='{field_name}' i]"
        )
        if await select.count() == 0:
            logger.info(f"Select '{field_name}' no existe en este formulario")
            return False

        locator = select.first
        await self._wait_for_real_options(locator, field_name)
        chosen = await locator.evaluate(
            _SELECT_JS_FN,
            {"preferred": preferred, "requirePreferredMatch": require_preferred_match},
        )

        if chosen:
            logger.info(f"Select '{field_name}': {chosen}")
            return True

        logger.warning(f"Select '{field_name}' sin opcion compatible con {preferred}")
        return False

    # Espera hasta que opciones reales esten disponibles en un <select> dinamico (area)
    async def _wait_for_real_options(self, select: Locator, field_name: str, timeout_ms: int = 10000) -> None:
        try:
            await self.page.wait_for_function(
                """([select, fieldName]) => {
                    const norm = s => String(s || '').trim().toLowerCase();
                    const bad = new Set(['', '-', '--', 'seleccionar', 'selecciona', 'select', 'choose']);
                    const real = Array.from(select.options || []).filter((option, index) => {
                        const text = norm(option.textContent);
                        const value = norm(option.value);
                        return index > 0 && !option.disabled && !bad.has(text)
                            && !bad.has(value) && !text.endsWith(':');
                    });
                    return fieldName !== 'area' || real.length > 0;
                }""",
                [await select.element_handle(), field_name],
                timeout=timeout_ms,
            )
        except Exception:
            logger.debug(f"Select '{field_name}': no se confirmaron opciones dinamicas")
