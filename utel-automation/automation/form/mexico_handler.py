"""MexicoFormHandler — lógica específica para formularios México (CMS y Universidad).

Maneja dos flujos distintos:
1. CMS (utel.edu.mx): formularios estándar con modalidad → área → programa
2. Universidad (universidad.utel.edu.mx): formularios custom con Choices.js
"""

from typing import Optional

from playwright.async_api import Locator, Page
from loguru import logger

from automation.common.human_click import human_click_point
from automation.form.form_utils import level_preferences, modality_preferences, program_query


class MexicoFormHandler:
    """Lógica específica para formularios de México (CMS y Universidad)."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope
        self._universidad_scope_marked = False

    # ---------------------------------------------------------------- #
    #  Form scope detection for Universidad Mexico
    # ---------------------------------------------------------------- #

    async def wait_for_universidad_form(self, timeout_ms: int = 30000) -> bool:
        attempts = max(int(timeout_ms / 500), 1)
        for _ in range(attempts):
            if await self._mark_universidad_form_scope():
                return True
            await self.page.wait_for_timeout(500)
        logger.warning("Universidad Mexico: no se detecto formulario visible")
        return False

    async def find_universidad_scope(self) -> Optional[Locator]:
        if not await self._mark_universidad_form_scope():
            return None
        scope = self.page.locator("[data-codex-universidad-form-scope='true']")
        try:
            if await scope.count() > 0:
                return scope.first
        except Exception:
            pass
        return None

    async def _mark_universidad_form_scope(self) -> bool:
        try:
            result = await self.page.evaluate("""
                () => {
                    const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
                    const fieldVisible = (el) => { if (!visible(el) || el.disabled || el.type === 'hidden') return false; const k = `${el.type||''} ${el.name||''} ${el.id||''}`.toLowerCase(); return !k.includes('search') && !k.includes('buscar'); };
                    const keyFor = (el) => `${el.name||''} ${el.id||''} ${el.placeholder||''} ${el.type||''} ${el.getAttribute('aria-label')||''}`.toLowerCase();
                    const hasSubmit = (root) => Array.from(root.querySelectorAll('button, input[type=submit], [role=button]')).filter(visible).some(e => /enviar|solicitar|informaci|beca|comienza|registr/i.test(e.textContent||e.value||''));
                    const scoreRoot = (root) => {
                        if (!visible(root)) return 0;
                        const fields = Array.from(root.querySelectorAll('input, select, textarea')).filter(fieldVisible);
                        if (fields.length < 2) return 0;
                        const keys = fields.map(keyFor);
                        let score = 0;
                        if (keys.some(x => x.includes('email') || x.includes('correo'))) score += 6;
                        if (keys.some(x => x.includes('phone') || x.includes('tel') || x.includes('telefono') || x.includes('celular') || x.includes('mobile'))) score += 5;
                        if (keys.some(x => x.includes('name') || x.includes('nombre'))) score += 5;
                        if (fields.some(e => e.tagName === 'SELECT')) score += 2;
                        if (fields.some(e => e.required)) score += 2;
                        if (hasSubmit(root)) score += 3;
                        score += Math.min(fields.length, 6);
                        return score;
                    };
                    document.querySelectorAll('[data-codex-universidad-form-scope]').forEach(e => e.removeAttribute('data-codex-universidad-form-scope'));
                    const candidates = Array.from(document.querySelectorAll('form, section, aside, article, div')).filter(visible)
                        .map(el => ({ el, score: scoreRoot(el), area: el.getBoundingClientRect().width * el.getBoundingClientRect().height }))
                        .filter(i => i.score >= 8).sort((a, b) => b.score - a.score || a.area - b.area);
                    if (!candidates.length) return false;
                    candidates[0].el.setAttribute('data-codex-universidad-form-scope', 'true');
                    return true;
                }
            """)
            self._universidad_scope_marked = bool(result)
            return self._universidad_scope_marked
        except Exception as e:
            logger.debug(f"Universidad: no se pudo marcar formulario: {e}")
            return False

    # ---------------------------------------------------------------- #
    #  CMS sequence: modalidad → área → programa
    # ---------------------------------------------------------------- #

    async def fill_cms_sequence(self, level: str, raw_level: str) -> None:
        """Ejecuta la secuencia CMS: nivel → modalidad → área → programa."""
        from automation.form.select_handler import SelectHandler
        sel = SelectHandler(self.page, self.form_scope)

        level_ok = await self._select_universidad_level_by_context(level)
        if not level_ok:
            await sel.select("modality", preferred=modality_preferences(raw_level or level))
        await self.page.wait_for_timeout(3000)

        area_exists = await sel.exists("area")
        area_ok = await sel.select("area", preferred=level_preferences(level), require_preferred_match=True)
        if area_exists and not area_ok:
            logger.warning(f"Universidad CMS: no se pudo seleccionar Area: {level}")
        await self.page.wait_for_timeout(3000)

        program_ok = await self._select_universidad_program_random()
        if not program_ok:
            logger.info("Universidad CMS: programa no resuelto con selects nativos")
            try:
                await sel.select("program", preferred=[*level_preferences(level), program_query(level)])
            except Exception:
                pass

    async def _select_universidad_level_by_context(self, level: str) -> bool:
        preferences = level_preferences(level)
        try:
            result = await self.form_scope.evaluate(
                """
                (root, preferences) => {
                    const clean = (v) => String(v || '').trim();
                    const norm = (v) => clean(v).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0 && !el.disabled; };
                    const bad = /^(|\\-|--|selecciona|seleccione|select|choose)$/;
                    const labelText = (el) => { const id = el.id ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent||'' : ''; const p = el.closest('label')?.textContent||''; return `${id} ${p}`; };
                    const pick = (sel) => {
                        const opts = Array.from(sel.options||[]).map((o,i) => ({ index:i, text:clean(o.textContent), value:clean(o.value), disabled:o.disabled }))
                            .filter(o => { const t=norm(o.text); const v=norm(o.value); return o.index>0 && !o.disabled && !bad.test(t) && !bad.test(v); });
                        for (const w of preferences||[]) {
                            const want = norm(w);
                            if (!want) continue;
                            const found = opts.find(o => { const t=norm(o.text); const v=norm(o.value); return t===want||v===want||t.includes(want)||v.includes(want)||want.includes(t); });
                            if (found) return found;
                        }
                        return null;
                    };
                    const candidates = Array.from(root.querySelectorAll('select')).filter(visible)
                        .map((sel) => {
                            const optText = Array.from(sel.options||[]).map(o=>o.textContent||'').join(' ');
                            const key = norm(`${sel.name||''} ${sel.id||''} ${sel.getAttribute('aria-label')||''} ${labelText(sel)} ${optText}`);
                            const picked = pick(sel);
                            let score = 0;
                            if (/nivel|grado|modalidad|programa|carrera|licenciatura|maestria|doctorado|posgrado/.test(key)) score += 8;
                            if (/nombre|correo|email|telefono|celular|pais|estado/.test(key)) score -= 10;
                            if (picked) score += 20;
                            return { select: sel, picked, score };
                        }).filter(i => i.picked && i.score > 0).sort((a,b) => b.score - a.score);
                    const target = candidates[0];
                    if (!target) return null;
                    target.select.selectedIndex = target.picked.index;
                    target.select.value = target.picked.value;
                    ['input','change','blur'].forEach(ev => target.select.dispatchEvent(new Event(ev, { bubbles: true })));
                    return { name: target.select.name||'', id: target.select.id||'', text: target.picked.text };
                }
                """,
                preferences,
            )
            if result:
                logger.info(f"Universidad: nivel seleccionado por contexto: {result}")
                await self.page.wait_for_timeout(1500)
                return True
        except Exception as e:
            logger.debug(f"Universidad: nivel por contexto fallo: {e}")
        return False

    async def _select_universidad_program_random(self) -> bool:
        try:
            result = await self.form_scope.evaluate("""
                (root) => {
                    const clean = (v) => String(v||'').trim();
                    const norm = (v) => clean(v).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display!=='none' && s.visibility!=='hidden' && b.width>0 && b.height>0 && !el.disabled; };
                    const bad = /^(|\\-|--|selecciona|seleccione|select|choose|programa|selecciona un programa)$/;
                    const labelText = (el) => { const id = el.id ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent||'' : ''; const p = el.closest('label')?.textContent||''; return `${id} ${p}`; };
                    const programSelects = Array.from(root.querySelectorAll('select')).filter(visible)
                        .map((sel) => {
                            const optText = Array.from(sel.options||[]).map(o=>o.textContent||'').join(' ');
                            const key = norm(`${sel.name||''} ${sel.id||''} ${sel.getAttribute('aria-label')||''} ${labelText(sel)} ${optText}`);
                            let score = 0;
                            if (/program|programa|carrera|interes/.test(key)) score += 10;
                            if (/administracion|ingenieria|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria|tecnologias|mercadotecnia/.test(key)) score += 6;
                            if (/modalidad|pais|estado|nombre|correo|email|telefono|celular/.test(key)) score -= 10;
                            return { select: sel, score };
                        }).filter(i => i.score > 0).sort((a,b) => b.score - a.score);
                    for (const item of programSelects) {
                        const opts = Array.from(item.select.options||[]).map((o,i) => ({ index:i, text:clean(o.textContent), value:clean(o.value), disabled:o.disabled }))
                            .filter(o => { const t=norm(o.text); const v=norm(o.value); return o.index>0 && !o.disabled && !bad.test(t) && !bad.test(v); });
                        if (!opts.length) continue;
                        const picked = opts[Math.floor(Math.random() * opts.length)];
                        item.select.selectedIndex = picked.index;
                        item.select.value = picked.value;
                        ['input','change','blur'].forEach(ev => item.select.dispatchEvent(new Event(ev, { bubbles: true })));
                        return { name: item.select.name||'', id: item.select.id||'', text: picked.text, value: picked.value };
                    }
                    return null;
                }
            """)
            if result:
                logger.info(f"Universidad CMS: programa nativo aleatorio: {result}")
                await self.page.wait_for_timeout(1500)
                return True
        except Exception as e:
            logger.debug(f"Universidad CMS: programa aleatorio fallo: {e}")
        return False

    # ---------------------------------------------------------------- #
    #  Custom program select (Choices.js)
    # ---------------------------------------------------------------- #

    async def select_custom_program(self, level: str) -> bool:
        """Selecciona programa en dropdown custom (Choices.js). 4 capas de fallback."""
        if await self._program_is_selected():
            logger.info("Universidad: programa ya seleccionado")
            return True

        # Capa 2: Choices.js
        filled = await self._fill_choices_select("program", level)
        if filled:
            await self.page.wait_for_timeout(800)
            if await self._program_is_selected():
                logger.info("Universidad: programa por Choices.js")
                return True

        # Capa 3: Click visual
        for attempt in range(1, 4):
            target = await self._find_program_control()
            if not target:
                break

            await human_click_point(self.page, float(target["x"]), float(target["y"]))
            await self.page.wait_for_timeout(700)

            options_visible = await self._wait_for_custom_options(timeout_ms=3000)
            if not options_visible:
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(400)
                continue

            clicked = await self._click_visible_program_option(level)
            if not clicked:
                option = await self._random_program_option(level)
                if option:
                    await human_click_point(self.page, float(option["x"]), float(option["y"]))
                    clicked = True

            if clicked:
                await self.page.wait_for_timeout(800)
                await self._sync_native_select_from_custom(level)
                if await self._program_is_selected():
                    return True

        # Capa 4: Keyboard
        if await self._select_program_with_keyboard():
            return True

        logger.error("Universidad: no se pudo seleccionar programa")
        return False

    async def _fill_choices_select(self, select_name: str, level: str) -> bool:
        try:
            result = await self.form_scope.evaluate(
                """
                (root, payload) => {
                    const { selectName, levelTerms } = payload;
                    const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const bad = /^(|--|selecciona|selecciona un programa|programa|choose|select)$/;
                    const native = root.querySelector(`select[name="${selectName}"]`) || root.querySelector(`select[name="data[${selectName}]"]`);
                    if (!native) return { error: 'not_found' };
                    const opts = Array.from(native.options||[]).map((o,i) => ({ index:i, text:String(o.textContent||'').trim(), value:String(o.value||'').trim(), disabled:o.disabled }))
                        .filter(o => o.index>0 && !o.disabled && !bad.test(norm(o.text)) && !bad.test(norm(o.value)));
                    if (!opts.length) return { error: 'no_options' };
                    let picked = null;
                    for (const term of (levelTerms||[])) {
                        const want = norm(term);
                        if (!want) continue;
                        picked = opts.find(o => norm(o.text).includes(want) || norm(o.value).includes(want));
                        if (picked) break;
                    }
                    if (!picked) picked = opts[Math.floor(Math.random() * opts.length)];
                    native.selectedIndex = picked.index;
                    native.value = picked.value;
                    ['input','change','blur'].forEach(ev => native.dispatchEvent(new Event(ev, { bubbles: true })));
                    const wrapper = native.closest('.choices, [data-type="select-one"]') || native.parentElement;
                    let clickedCustom = false;
                    if (wrapper) {
                        const trigger = wrapper.querySelector('.choices__inner, [class*=control], [class*=placeholder], [aria-expanded], [role=combobox], [class*=trigger]');
                        if (trigger) {
                            trigger.click();
                            const optionEls = Array.from(wrapper.querySelectorAll('.choices__item--choice:not(.choices__item--disabled), [role=option], li[data-value], [class*=option-item]'));
                            const wantedNorm = norm(picked.text);
                            for (const el of optionEls) {
                                const t = norm(el.textContent||'');
                                if (t && (t.includes(wantedNorm) || wantedNorm.includes(t))) {
                                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                    clickedCustom = true;
                                    break;
                                }
                            }
                            if (!clickedCustom) trigger.click();
                        }
                    }
                    return { picked: picked.text, value: picked.value, clickedCustom };
                }
                """,
                {"selectName": select_name, "levelTerms": level_preferences(level)},
            )
            if result and not result.get("error"):
                logger.info(f"Choices '{select_name}': {result}")
                await self.page.wait_for_timeout(600)
                return True
            logger.warning(f"Choices '{select_name}': {result}")
        except Exception as e:
            logger.debug(f"Choices fallo para '{select_name}': {e}")
        return False

    async def _find_program_control(self) -> Optional[dict]:
        try:
            return await self.form_scope.evaluate("""
                (root) => {
                    const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display!=='none' && s.visibility!=='hidden' && b.width>0 && b.height>0 && !el.disabled; };
                    const scoreNode = (el) => {
                        if (!visible(el)) return null;
                        const b = el.getBoundingClientRect();
                        if (b.width<120 || b.height<24 || b.height>110) return null;
                        const text = norm(el.textContent||el.getAttribute('aria-label')||el.getAttribute('placeholder')||'');
                        const key = norm(`${el.className||''} ${el.id||''} ${el.getAttribute('role')||''}`);
                        let score = 0;
                        if (text.includes('selecciona un programa')) score += 20;
                        if (text.includes('programa')) score += 8;
                        if (key.includes('select')||key.includes('dropdown')||key.includes('combobox')) score += 5;
                        if (b.width>=180 && b.width<=520 && b.height>=28 && b.height<=80) score += 4;
                        if (/maestria|licenciatura|doctorado|modalidad/.test(text) && !text.includes('programa')) score -= 8;
                        if (/nombre|correo|email|telefono|celular|privacidad/.test(text)) score -= 20;
                        if (score <= 0) return null;
                        return { score, text: (el.textContent||'').trim().slice(0,120), x: b.left + b.width/2, y: b.top + b.height/2 };
                    };
                    const raw = Array.from(root.querySelectorAll('[role=combobox],[aria-haspopup],button,[class*=select],[class*=Select],[class*=dropdown],[class*=Dropdown],div,span'));
                    const candidates = raw.map(el => { const clickable = el.closest('[role=combobox],[aria-haspopup],button,[class*=control],[class*=Control],[class*=select],[class*=Select],[class*=dropdown],[class*=Dropdown]')||el; return scoreNode(clickable); }).filter(Boolean).sort((a,b)=>b.score-a.score);
                    return candidates[0] || null;
                }
            """)
        except Exception as e:
            logger.debug(f"Universidad: no se ubico control custom: {e}")
        return None

    async def _wait_for_custom_options(self, timeout_ms: int = 3000) -> bool:
        attempts = max(int(timeout_ms / 300), 1)
        for _ in range(attempts):
            try:
                count = await self.page.evaluate("""
                    () => {
                        const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                        const bad = /selecciona|programa$|choose|select|--/;
                        const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display!=='none' && s.visibility!=='hidden' && b.width>0 && b.height>0; };
                        const sels = ['.choices__list--dropdown .choices__item--choice:not(.choices__item--disabled)','[role=listbox] [role=option]','[class*=dropdown][class*=open] li','[class*=options-list] li','[aria-expanded=true] [role=option]'];
                        for (const sel of sels) {
                            const items = Array.from(document.querySelectorAll(sel)).filter(visible).filter(el => { const t = norm(el.textContent||''); return t.length>3 && !bad.test(t); });
                            if (items.length>0) return items.length;
                        }
                        return 0;
                    }
                """)
                if count > 0:
                    logger.info(f"Universidad: {count} opciones custom visibles")
                    return True
            except Exception:
                pass
            await self.page.wait_for_timeout(300)
        return False

    async def _click_visible_program_option(self, level: str) -> bool:
        terms = level_preferences(level)
        try:
            result = await self.page.evaluate(
                """
                (terms) => {
                    const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display!=='none' && s.visibility!=='hidden' && b.width>0 && b.height>0; };
                    const wanted = terms.map(norm).filter(Boolean);
                    const blocked = /selecciona|programa de interes|programa$|modalidad|maestria$|licenciatura$|doctorado$|nombre|correo|email|telefono|celular|privacidad|aviso|enviar|whatsapp/;
                    const nodes = Array.from(document.querySelectorAll('[role=option],[id*=option],[class*=option],[class*=Option],li,div')).filter(visible)
                        .map((el) => {
                            const root = el.closest('[role=option],[id*=option],[class*=option],[class*=Option],li')||el;
                            if (!visible(root)) return null;
                            const b = root.getBoundingClientRect();
                            const text = String(root.textContent||'').trim();
                            const normalized = norm(text);
                            if (!normalized||normalized.length<4||normalized.length>180) return null;
                            if (blocked.test(normalized)) return null;
                            if (b.width<140||b.height<18||b.height>80) return null;
                            let score = 0;
                            if (/licenciatura|maestria|doctorado|ingenieria|administracion|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria|tecnologias|mercadotecnia/.test(normalized)) score += 10;
                            if (wanted.some(t => normalized.includes(t))) score += 2;
                            if (root.getAttribute('role')==='option') score += 8;
                            if (/option/.test(norm(root.className||''))) score += 6;
                            if (score<=0) return null;
                            return { root, text, score };
                        }).filter(Boolean);
                    if (!nodes.length) return null;
                    nodes.sort((a,b)=>b.score-a.score);
                    const top = nodes.filter(i=>i.score>=nodes[0].score-3).slice(0,12);
                    const picked = top[Math.floor(Math.random()*top.length)];
                    picked.root.scrollIntoView({block:'center',inline:'center',behavior:'instant'});
                    picked.root.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}));
                    picked.root.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window}));
                    picked.root.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
                    return { text: picked.text.slice(0,140), score: picked.score };
                }
                """,
                terms,
            )
            if result:
                logger.info(f"Universidad: opcion clickeada: {result}")
                return True
        except Exception as e:
            logger.debug(f"Universidad: click opcion fallo: {e}")
        return False

    async def _random_program_option(self, level: str) -> Optional[dict]:
        terms = level_preferences(level)
        try:
            return await self.page.evaluate(
                """
                (terms) => {
                    const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display!=='none' && s.visibility!=='hidden' && b.width>0 && b.height>0; };
                    const wanted = terms.map(norm).filter(Boolean);
                    const blocked = /selecciona|programa$|modalidad|maestria$|licenciatura$|doctorado$|nombre|correo|email|telefono|celular|privacidad|aviso|enviar|whatsapp/;
                    const nodes = Array.from(document.querySelectorAll('[role=option],li,button,div,span,p')).filter(visible)
                        .map((el) => {
                            const b = el.getBoundingClientRect();
                            const text = String(el.textContent||'').trim();
                            const normalized = norm(text);
                            let score = 0;
                            if (!normalized||normalized.length<4||normalized.length>160) return null;
                            if (blocked.test(normalized)) return null;
                            if (b.width<120||b.height<20||b.height>90) return null;
                            if (/licenciatura|maestria|doctorado|ingenieria|administracion|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria/.test(normalized)) score += 8;
                            if (wanted.some(t=>normalized.includes(t))) score += 3;
                            if (el.getAttribute('role')==='option') score += 6;
                            if (/option|item|menu|list/.test(norm(el.className||''))) score += 3;
                            if (score<=0) return null;
                            return { text, score, x: b.left+b.width/2, y: b.top+b.height/2 };
                        }).filter(Boolean);
                    if (!nodes.length) return null;
                    nodes.sort((a,b)=>b.score-a.score);
                    const top = nodes.filter(i=>i.score>=nodes[0].score-2).slice(0,12);
                    return top[Math.floor(Math.random()*top.length)];
                }
                """,
                terms,
            )
        except Exception as e:
            logger.debug(f"Universidad: opcion aleatoria fallo: {e}")
        return None

    async def _select_program_with_keyboard(self) -> bool:
        try:
            await self.page.keyboard.press("ArrowDown")
            await self.page.wait_for_timeout(250)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(1200)
            if await self._program_is_selected():
                logger.info("Universidad: programa seleccionado con teclado")
                return True
            await self.page.keyboard.press("Escape")
        except Exception as e:
            logger.debug(f"Universidad: teclado fallo: {e}")
        return False

    async def _sync_native_select_from_custom(self, level: str) -> None:
        try:
            await self.form_scope.evaluate(
                """
                (root, levelTerms) => {
                    const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const bad = /selecciona|programa$|choose|select|--/;
                    const controlSels = ['.choices__item--selectable:not(.choices__item--choice)','.choices [class*=singleValue]','[aria-selected=true]','[class*=selected-value]','[class*=selectedValue]'];
                    let displayedText = '';
                    for (const sel of controlSels) {
                        const el = root.querySelector(sel);
                        if (el) { const t = String(el.textContent||'').trim(); if(t&&!bad.test(norm(t))){displayedText=t;break;} }
                    }
                    const native = root.querySelector('select[name="program"]') || root.querySelector('select[name="data[program]"]');
                    if (!native||!displayedText) return;
                    const match = Array.from(native.options||[]).find(o => { const oN=norm(o.textContent||''); const dN=norm(displayedText); return oN.includes(dN)||dN.includes(oN); });
                    if (match) {
                        native.selectedIndex = match.index;
                        native.value = match.value;
                        ['input','change','blur'].forEach(ev=>native.dispatchEvent(new Event(ev,{bubbles:true})));
                    }
                }
                """,
                level_preferences(level),
            )
        except Exception as e:
            logger.debug(f"Sync nativo fallo: {e}")

    async def _program_is_selected(self) -> bool:
        try:
            return await self.form_scope.evaluate("""
                (root) => {
                    const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const bad = /^(|--|selecciona|selecciona un programa|programa|choose|select)$/;
                    for (const sel of ['select[name="program"]','select[name="data[program]"]']) {
                        const s = root.querySelector(sel);
                        if (s) {
                            const val = norm(s.value||'');
                            const txt = norm(s.options?.[s.selectedIndex]?.textContent||'');
                            if (val&&!bad.test(val)) return true;
                            if (txt&&!bad.test(txt)) return true;
                        }
                    }
                    const programKeywords = /ingenieria|administracion|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria|tecnologias|mercadotecnia|arquitectura|comunicacion|turismo/;
                    const customSels = ['.choices__item--selectable:not(.choices__item--choice)','[aria-selected=true]','[class*=singleValue]','[class*=selected-value]','[class*=selectedValue]'];
                    for (const sel of customSels) {
                        for (const el of Array.from(root.querySelectorAll(sel))) {
                            const text = norm(el.textContent||'');
                            if (text&&!bad.test(text)&&programKeywords.test(text)) return true;
                        }
                    }
                    return false;
                }
            """)
        except Exception as e:
            logger.debug(f"Programa seleccionado check fallo: {e}")
            return False

    # ---------------------------------------------------------------- #
    #  Fill university inputs (name, email, phone)
    # ---------------------------------------------------------------- #

    async def fill_universidad_inputs(self, test_email: str, fake_name: str, fake_phone: str) -> None:
        payload = {
            "name": fake_name,
            "email": test_email,
            "phone": fake_phone,
            "lastName": fake_name.split(" ")[-1] if fake_name else "Perez",
        }
        try:
            result = await self.form_scope.evaluate(
                """
                (root, payload) => {
                    const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => { const s=window.getComputedStyle(el); const b=el.getBoundingClientRect(); return s.display!=='none'&&s.visibility!=='hidden'&&b.width>0&&b.height>0&&!el.disabled&&el.type!=='hidden'; };
                    const setVal = (el, val) => {
                        const proto = el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;
                        const desc = Object.getOwnPropertyDescriptor(proto,'value');
                        if(desc&&desc.set)desc.set.call(el,val); else el.value=val;
                        el.dispatchEvent(new Event('input',{bubbles:true}));
                        el.dispatchEvent(new Event('change',{bubbles:true}));
                        el.dispatchEvent(new Event('blur',{bubbles:true}));
                    };
                    const labelText = (el) => { const id=el.id?root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent||'':''; const p=el.closest('label')?.textContent||''; return `${id} ${p}`; };
                    const done = [];
                    for (const el of Array.from(root.querySelectorAll('input,textarea')).filter(visible)) {
                        const type = norm(el.type);
                        if(['checkbox','radio','submit','button','file','password'].includes(type)) continue;
                        if(String(el.value||'').trim()) continue;
                        const key = norm(`${el.name||''} ${el.id||''} ${el.placeholder||''} ${el.getAttribute('aria-label')||''} ${labelText(el)}`);
                        if(/search|buscar|utm|captcha|recaptcha/.test(key)) continue;
                        let value='', reason='';
                        if(type==='email'||/email|correo/.test(key)) { value=payload.email; reason='email'; }
                        else if(type==='tel'||/phone|tel|telefono|celular|mobile|whatsapp/.test(key)) { value=payload.phone; reason='phone'; }
                        else if(/apellido|last/.test(key)) { value=payload.lastName; reason='last_name'; }
                        else if(/nombre|name|first/.test(key)) { value=payload.name; reason='name'; }
                        else if(el.required) { value=type==='number'?'1':'Prueba'; reason='required_fallback'; }
                        if(!value) continue;
                        setVal(el,value);
                        done.push({name:el.name||'',id:el.id||'',placeholder:el.placeholder||'',reason});
                    }
                    return done;
                }
                """,
                payload,
            )
            logger.info(f"Universidad: inputs completados: {result}")
        except Exception as e:
            logger.debug(f"Universidad: inputs fallo: {e}")

    async def get_form_state(self) -> dict:
        try:
            return await self.form_scope.evaluate("""
                (root) => {
                    const norm = (v) => String(v||'').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => { const s=window.getComputedStyle(el); const b=el.getBoundingClientRect(); return s.display!=='none'&&s.visibility!=='hidden'&&b.width>0&&b.height>0&&!el.disabled&&el.type!=='hidden'; };
                    const fields = Array.from(root.querySelectorAll('input,select,textarea')).filter(visible);
                    const state = { has_name:false, name:false, has_email:false, email:false, has_phone:false, phone:false, has_program:false, program:false, has_checkbox:false, checkbox_checked:true, missing_required:[] };
                    for (const el of fields) {
                        const type=norm(el.type); const key=norm(`${el.name||''} ${el.id||''} ${el.placeholder||''} ${el.getAttribute('aria-label')||''}`); const val=String(el.value||'').trim();
                        if(type==='checkbox') { state.has_checkbox=true; if(/privacidad|politica|aviso|terminos|acepto/.test(key)||el.required){state.checkbox_checked=Boolean(el.checked);} if(el.required&&!el.checked)state.missing_required.push(key||'checkbox'); continue; }
                        if(/email|correo/.test(key)||type==='email'){state.has_email=true;state.email=Boolean(val);}
                        if(/phone|tel|telefono|celular|mobile|whatsapp/.test(key)||type==='tel'){state.has_phone=true;state.phone=Boolean(val);}
                        if(/nombre|name|first/.test(key)&&!/apellido|last/.test(key)){state.has_name=true;state.name=Boolean(val);}
                        if(/program|programa|carrera|interes|licenciatura|maestria|doctorado/.test(key)){state.has_program=true;state.program=Boolean(val)&&!/selecciona|select|choose/.test(norm(val));}
                        if(el.required&&!val)state.missing_required.push(key||el.tagName.toLowerCase());
                    }
                    for (const sel of ['select[name="program"]','select[name="data[program]"]']) {
                        const ns=root.querySelector(sel); if(ns){const v=String(ns.value||'').trim();const b=/selecciona|select|choose|^$/.test(v.toLowerCase()); if(v&&!b){state.has_program=true;state.program=true;state.missing_required=state.missing_required.filter(k=>!/program|programa/.test(k));}}}
                    return state;
                }
            """)
        except Exception:
            return {}
