"""ProgramSearchEngine — busca y selecciona programas educativos en LPs.

Maneja dos flujos:
1. Tarjeta: abrir LP de producto desde página genérica (con reintentos anti-Cloudflare)
2. Búsqueda: escribir en buscador, esperar resultados, clickear el mejor match
"""

from time import monotonic
from typing import Optional

from playwright.async_api import Page, Locator
from loguru import logger

from automation.common.human_click import human_click_point
from automation.common.cloudflare import is_cloudflare_blocked
from automation.form.form_utils import level_preferences, canonical_level


TARJETA_PRODUCT_TIMEOUT = 120
TARJETA_RETRY_DELAY_MS = 2500


class ProgramSearchEngine:
    """Busca y selecciona programas en landing pages."""

    def __init__(self, page: Page, form_scope: Locator):
        self.page = page
        self.form_scope = form_scope

    async def open_tarjeta_product(self, level: str, original_url: str) -> bool:
        """
        Flujo Tarjeta: abre una LP de producto desde una página genérica.
        Reintenta hasta 120s si Cloudflare bloquea.
        """
        deadline = monotonic() + TARJETA_PRODUCT_TIMEOUT
        attempt = 0

        while monotonic() < deadline:
            attempt += 1
            remaining = int(deadline - monotonic())
            logger.info(f"Tarjeta: intento {attempt} para abrir LP de producto; quedan {remaining}s")

            if self.page.url != original_url or attempt > 1:
                await self._reload_or_navigate(original_url)

            product_opened = await self._search_program_from_generic_page(level, original_url)
            if not product_opened and await is_cloudflare_blocked(self.page):
                if monotonic() < deadline:
                    await self.page.wait_for_timeout(TARJETA_RETRY_DELAY_MS)
                continue

            if not product_opened:
                product_opened = await self._open_program_card(level, original_url)

            if product_opened:
                logger.info(f"Tarjeta: LP de producto abierta en intento {attempt}")
                return True

            if monotonic() < deadline:
                await self.page.wait_for_timeout(TARJETA_RETRY_DELAY_MS)

        return False

    async def _reload_or_navigate(self, url: str) -> None:
        try:
            if self.page.url != url:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            else:
                await self.page.reload(wait_until="domcontentloaded", timeout=45000)
            await self._soft_wait_network()
            await self.page.wait_for_timeout(1500)
        except Exception as e:
            logger.debug(f"Tarjeta: no se pudo reabrir LP: {e}")

    async def _soft_wait_network(self) -> None:
        try:
            await self.page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            pass

    async def _open_program_card(self, level: str, original_url: str) -> bool:
        """Encuentra y clickea la tarjeta de programa más relevante en la página."""
        terms = level_preferences(level)
        try:
            result = await self.page.evaluate(
                """
                (terms) => {
                    const norm = (v) => String(v || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().trim();
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const b = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0;
                    };
                    const blocked = ['whatsapp', 'politica', 'privacidad', 'aviso', 'terminos', 'solicitar informacion', 'calcula tu beca', 'enviar'];
                    const scoreNode = (text, href, box) => {
                        if (!text || !terms.some(t => text.includes(t))) return 0;
                        if (blocked.some(t => text.includes(t) || (href || '').includes(t))) return 0;
                        let s = 1;
                        if (/licenciatura|maestria|doctorado|bachillerato|bootcamp|titulacion|hibrida/.test(text)) s += 4;
                        if (/programa|carrera|estudia|educacion|ingenieria|administracion|derecho|psicologia/.test(text)) s += 2;
                        if (href && !/#$/.test(href)) s += 3;
                        if (b.height >= 70 && b.height <= 520 && b.width >= 120) s += 2;
                        if (b.top > 80) s += 1;
                        return s;
                    };
                    const anchors = Array.from(document.querySelectorAll('a[href]')).filter(visible)
                        .map((a) => {
                            const card = a.closest('article, li, section, [class*=card], [class*=Card], [class*=program], [class*=Program]') || a;
                            const b = card.getBoundingClientRect();
                            return { href: a.href, text: norm(card.textContent || a.textContent), score: scoreNode(norm(card.textContent || a.textContent), a.href, b), x: b.left + b.width/2, y: b.top + b.height/2 };
                        }).filter(i => i.score > 0);
                    if (!anchors.length) return null;
                    anchors.sort((a, b) => b.score - a.score || a.y - b.y);
                    const top = anchors.filter(i => i.score >= anchors[0].score - 1).slice(0, 10);
                    const picked = top[Math.floor(Math.random() * top.length)];
                    return { href: picked.href, text: picked.text.slice(0, 180), x: picked.x, y: picked.y };
                }
                """,
                terms,
            )

            if not result:
                logger.info(f"No se encontraron tarjetas para nivel '{level}'")
                return False

            x, y = result.get("x"), result.get("y")
            if x is None or y is None:
                return False

            await human_click_point(self.page, float(x), float(y))
            changed = await self._wait_for_url_change(original_url)
            return changed and not await is_cloudflare_blocked(self.page)

        except Exception as e:
            logger.debug(f"No se pudo abrir tarjeta de programa: {e}")
            return False

    async def _search_program_from_generic_page(self, level: str, original_url: str) -> bool:
        """Usa el buscador de la página para encontrar un programa."""
        await self._open_program_search_if_needed()
        searchers = await self._find_program_search_fields()

        for field in searchers:
            try:
                if await field.count() == 0:
                    continue
                query = canonical_level(level)
                await field.first.click(timeout=3000)
                await self.page.wait_for_timeout(250)
                await field.first.press("Control+A")
                await field.first.press("Backspace")
                await field.first.type(query, delay=80, timeout=6000)

                results_ready = await self._wait_for_search_results(level)
                if not results_ready:
                    continue

                clicked = await self._click_best_search_result(level)
                if not clicked:
                    continue

                changed = await self._wait_for_url_change(original_url, timeout_ms=20000)
                if changed:
                    if await is_cloudflare_blocked(self.page):
                        return False
                    return True
            except Exception:
                continue

        return False

    async def _open_program_search_if_needed(self) -> None:
        if await self._program_search_input_visible():
            return
        try:
            await self.page.evaluate("""
                () => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const b = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0;
                    };
                    const norm = (v) => String(v || '').toLowerCase();
                    const candidates = Array.from(document.querySelectorAll('button, a, [role=button], svg'))
                        .filter(visible)
                        .map((el) => ({ el, box: el.getBoundingClientRect(), text: norm(el.textContent + ' ' + (el.getAttribute('aria-label')||'') + ' ' + (el.className||'')) }))
                        .filter(({ box, text }) => box.top < 190 && box.left < 520 && (text.includes('search') || text.includes('buscar') || text.includes('lupa')));
                    const target = candidates[0]?.el;
                    if (target) { target.click(); return true; }
                    return false;
                }
            """)
            await self.page.wait_for_timeout(800)
        except Exception as e:
            logger.debug(f"No se pudo abrir buscador: {e}")

    async def _program_search_input_visible(self) -> bool:
        try:
            return await self.page.evaluate("""
                () => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const b = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0;
                    };
                    return Array.from(document.querySelectorAll('input, textarea')).some((el) => {
                        if (!visible(el)) return false;
                        const box = el.getBoundingClientRect();
                        const key = `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
                        if (/email|correo|phone|tel|nombre|name|apellido/.test(key)) return false;
                        return box.top < 220 && box.width >= 90;
                    });
                }
            """)
        except Exception:
            return False

    async def _find_program_search_fields(self) -> list[Locator]:
        candidates: list[tuple[int, int, Locator]] = []
        selectors = [
            "input[placeholder*='Buscar programa' i]:visible",
            "input[placeholder*='programa' i]:visible",
            "input[aria-label*='buscar' i]:visible",
            "input[aria-label*='search' i]:visible",
            "input[type='search']:visible",
            "[role='searchbox']:visible",
            "input:visible",
        ]
        for si, sel in enumerate(selectors):
            locator = self.page.locator(sel)
            try:
                count = await locator.count()
            except Exception:
                continue
            for i in range(count):
                field = locator.nth(i)
                score = await self._score_search_field(field)
                if score > 0:
                    candidates.append((score, si, field))
        candidates.sort(key=lambda x: (-x[0], x[1]))
        logger.info(f"Tarjeta: {len(candidates)} campos de busqueda detectados")
        return [f for _, _, f in candidates]

    async def _score_search_field(self, field: Locator) -> int:
        try:
            return await field.evaluate("""
                (el) => {
                    const style = window.getComputedStyle(el);
                    const box = el.getBoundingClientRect();
                    if (style.display === 'none' || style.visibility === 'hidden') return 0;
                    if (box.width < 80 || box.height < 18) return 0;
                    const key = `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''} ${el.getAttribute('class') || ''}`.toLowerCase();
                    if (/email|correo|phone|tel|nombre|name|apellido|first|last/.test(key)) return 0;
                    if (box.top > 260) return 0;
                    let score = 1;
                    if (/search|buscar|programa/.test(key)) score += 8;
                    if (box.top < 190) score += 5;
                    if (box.left < 560) score += 3;
                    if (box.width >= 150) score += 2;
                    return score;
                }
            """)
        except Exception:
            return 0

    async def _wait_for_search_results(self, level: str, timeout_ms: int = 20000) -> bool:
        terms = level_preferences(level)
        attempts = max(int(timeout_ms / 300), 1)
        for _ in range(attempts):
            count = await self._count_search_results(terms)
            if count > 0:
                logger.info(f"Tarjeta: {count} resultados visibles para '{level}'")
                return True
            await self.page.wait_for_timeout(300)
        return False

    async def _count_search_results(self, terms: list[str]) -> int:
        try:
            return await self.page.evaluate(
                """
                (terms) => {
                    const norm = (v) => String(v || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().trim();
                    const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
                    const wanted = terms.map(norm).filter(Boolean);
                    const blocked = ['sugerencias', 'modalidad', 'oferta academica', 'aspirantes', 'conoce utel', 'comunidad', 'becas', 'campus virtual', 'solicitar informacion', 'obtener beca', 'whatsapp', 'inscripciones', 'estudiantes'];
                    const sel = ['a[href]', 'button', '[role=option]', '[role=menuitem]', 'li', 'div', 'span', 'p', '[class*=suggest]', '[class*=option]'].join(',');
                    return Array.from(document.querySelectorAll(sel)).filter(visible)
                        .map(el => ({ text: norm(el.textContent), box: el.getBoundingClientRect() }))
                        .filter(({ text, box }) => text && wanted.some(t => text.includes(t)) && !blocked.some(b => text.includes(b)) && box.top > 40 && box.height >= 18 && box.height < 220 && box.width >= 70)
                        .length;
                }
                """,
                terms,
            )
        except Exception:
            return 0

    async def _click_best_search_result(self, level: str) -> bool:
        terms = level_preferences(level)
        try:
            result = await self.page.evaluate(
                """
                (terms) => {
                    const norm = (v) => String(v || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().trim();
                    const visible = (el) => { const s = window.getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
                    const wanted = terms.map(norm).filter(Boolean);
                    const blocked = ['sugerencias', 'modalidad', 'oferta academica', 'aspirantes', 'conoce utel', 'comunidad', 'becas', 'campus virtual', 'solicitar informacion', 'obtener beca', 'whatsapp', 'inscripciones', 'estudiantes'];
                    const sel = ['a[href]', 'button', '[role=option]', '[role=menuitem]', 'li', 'div', 'span', 'p', '[class*=suggest]', '[class*=option]'].join(',');
                    const scoreItem = (item) => {
                        if (!item.text || !wanted.some(t => item.text.includes(t))) return 0;
                        if (blocked.some(t => item.text.includes(t))) return 0;
                        if (item.top < 70) return 0;
                        if (item.height < 18 || item.height > 170 || item.width < 70) return 0;
                        let s = 1;
                        if (item.href) s += 3;
                        if (item.height <= 120) s += 3;
                        if (/licenciatura|maestria|doctorado|bachillerato|bootcamp|titulacion|ingenieria|administracion|derecho|educacion|psicologia|tecnologia/.test(item.text)) s += 4;
                        if (item.text.length >= 18 && item.text.length <= 180) s += 2;
                        return s;
                    };
                    const nodes = Array.from(document.querySelectorAll(sel)).filter(visible)
                        .map((el) => {
                            const link = el.matches('a[href]') ? el : el.querySelector('a[href]');
                            const clickTarget = link || el.closest('button, [role=option], [role=menuitem], li, [class*=suggest], [class*=option]') || el;
                            const b = clickTarget.getBoundingClientRect();
                            return { text: norm(el.textContent), href: link ? link.href : '', x: b.left + b.width/2, y: b.top + b.height/2, top: b.top, height: b.height, width: b.width, score: 0 };
                        })
                        .map(item => ({ ...item, score: scoreItem(item) }))
                        .filter(i => i.score > 0);
                    if (!nodes.length) return null;
                    nodes.sort((a, b) => b.score - a.score || a.top - b.top);
                    const top = nodes.filter(i => i.score >= nodes[0].score - 1).slice(0, 8);
                    const picked = top[Math.floor(Math.random() * top.length)];
                    return { href: picked.href, x: picked.x, y: picked.y, text: picked.text };
                }
                """,
                terms,
            )

            if not result:
                return False
            x, y = result.get("x"), result.get("y")
            if x is None or y is None:
                return False
            logger.info(f"Resultado seleccionado para '{level}': {result.get('text')}")
            await human_click_point(self.page, float(x), float(y))
            return True
        except Exception as e:
            logger.debug(f"No se pudo clickear resultado: {e}")
            return False

    async def _wait_for_url_change(self, original_url: str, timeout_ms: int = 10000) -> bool:
        attempts = max(int(timeout_ms / 400), 1)
        for _ in range(attempts):
            if self.page.url != original_url:
                return True
            await self.page.wait_for_timeout(400)
        return False
