"""SelectHandler — maneja selección en <select> nativos y programáticos."""

from typing import Optional
from playwright.async_api import Locator, Page
from loguru import logger


class SelectHandler:
    """Maneja la interacción con elementos <select> en formularios."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    async def exists(self, field_name: str) -> bool:
        select = self.form_scope.locator(
            f"select[name='{field_name}'], select#{field_name}, select[id*='{field_name}' i]"
        )
        return await select.count() > 0

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
                    if (chosen) { matched = true; break; }
                    chosen = options.find((option) => {
                        const text = norm(option.text);
                        const value = norm(option.value);
                        return text.includes(wanted) || value.includes(wanted) || wanted.includes(text);
                    });
                    if (chosen) { matched = true; break; }
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
            {"preferred": preferred, "requirePreferredMatch": require_preferred_match},
        )

        if chosen:
            logger.info(f"Select '{field_name}': {chosen}")
            return True

        logger.warning(f"Select '{field_name}' sin opcion compatible con {preferred}")
        return False

    async def select_by_context(
        self,
        field_name: str,
        level_preferences: list[str],
        level: str,
    ) -> bool:
        """Busca un select por contexto (score) que matchee el nivel."""
        try:
            result = await self.form_scope.evaluate(
                """
                (root, payload) => {
                    const { preferred } = payload;
                    const clean = (v) => String(v || '').trim();
                    const norm = (v) => clean(v).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden'
                            && r.width > 0 && r.height > 0 && !el.disabled;
                    };
                    const bad = new Set(['', '-', '--', 'seleccionar', 'selecciona', 'select', 'choose']);
                    const labelText = (el) => {
                        const id = el.id ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent || '' : '';
                        const parent = el.closest('label')?.textContent || '';
                        return `${id} ${parent}`;
                    };
                    const optionsFor = (sel) => Array.from(sel.options || [])
                        .map((o, i) => ({ index: i, text: clean(o.textContent), value: clean(o.value), disabled: o.disabled }))
                        .filter((o) => { const t = norm(o.text); const v = norm(o.value); return o.index > 0 && !o.disabled && !bad.has(t) && !bad.has(v); });
                    const pick = (sel) => {
                        const opts = optionsFor(sel);
                        if (!opts.length) return null;
                        for (const w of preferred || []) {
                            const want = norm(w);
                            if (!want) continue;
                            const exact = opts.find(o => norm(o.text) === want || norm(o.value) === want);
                            if (exact) return { ...exact, matched: true };
                            const partial = opts.find(o => { const t = norm(o.text); const v = norm(o.value); return t.includes(want) || v.includes(want) || want.includes(t); });
                            if (partial) return { ...partial, matched: true };
                        }
                        return null;
                    };
                    const candidates = Array.from(root.querySelectorAll('select')).filter(visible)
                        .map((sel) => {
                            const opts = optionsFor(sel);
                            const key = norm(`${sel.name || ''} ${sel.id || ''} ${sel.getAttribute('aria-label') || ''} ${labelText(sel)} ${opts.map(o => o.text).join(' ')}`);
                            const picked = pick(sel);
                            let score = 0;
                            if (/program|programa|carrera|interes/.test(key)) score += 8;
                            if (/licenciatura|maestria|doctorado|bachillerato|bootcamp/.test(key)) score += 5;
                            if (/modalidad|estado|pais|phone|telefono|nombre|correo|email/.test(key)) score -= 6;
                            if (picked?.matched) score += 10;
                            return { select: sel, picked, score };
                        })
                        .filter(item => item.picked && item.score > 0)
                        .sort((a, b) => b.score - a.score);

                    const target = candidates[0];
                    if (!target) return null;
                    target.select.selectedIndex = target.picked.index;
                    target.select.value = target.picked.value;
                    ['input', 'change', 'blur'].forEach(ev => target.select.dispatchEvent(new Event(ev, { bubbles: true })));
                    return { name: target.select.name || '', id: target.select.id || '', text: target.picked.text, score: target.score };
                }
                """,
                {"preferred": [*level_preferences, field_name]},
            )

            if result:
                logger.info(f"Select por contexto '{field_name}': {result}")
                await self.page.wait_for_timeout(1500)
                return True
        except Exception as e:
            logger.debug(f"Select por contexto fallo para '{field_name}': {e}")

        return False

    async def _wait_for_real_options(self, select: Locator, field_name: str, timeout_ms: int = 10000) -> None:
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
            logger.debug(f"Select '{field_name}': no se confirmaron opciones dinamicas")
