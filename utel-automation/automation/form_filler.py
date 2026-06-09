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
from time import monotonic
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

TARJETA_PRODUCT_TIMEOUT_SECONDS = 120
TARJETA_PRODUCT_RETRY_DELAY_MS = 2500
FOOTER_FIELDS_TIMEOUT_MS = 30000
FOOTER_BEFORE_FILL_DELAY_MS = 30000

PROGRAM_SEARCH_BY_LEVEL = {
    "licenciatura": "Licenciatura",
    "licenciaturas": "Licenciatura",
    "licenciatura ejecutiva": "Licenciatura",
    "licenciaturas ejecutivas": "Licenciatura",
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
    "Licenciatura": [
        "Licenciatura",
        "Licenciaturas",
        "Licenciatura ejecutiva",
        "Licenciaturas ejecutivas",
    ],
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
        self._tarjeta_product_opened: bool = False
        self._mexico_utel_lp: bool = False
        self._mexico_universidad_lp: bool = False
        logger.debug(f"FormFiller creado para {country.id}")

    async def fill(self, lead: LeadRow) -> bool:
        """Abre la LP, prepara el formulario correcto y lo envia."""
        try:
            self.form_type = self._normalize_form_type(lead.form_type)
            self._mexico_utel_lp = self._is_mexico_utel_lp(lead.landing_url)
            self._mexico_universidad_lp = self._is_mexico_universidad_lp(lead.landing_url)
            raw_level = lead.nivel or infer_level_from_url(lead.landing_url) or ""
            level = self._canonical_level(get_level_name(self.country, raw_level) or raw_level)

            logger.info(f"Abriendo LP: {lead.landing_url}")
            logger.info(f"Formulario: {self.form_type or 'formlp'} | nivel='{level}'")
            if self._mexico_utel_lp:
                logger.info("Reglas Mexico utel.edu activas para esta LP")
            if self._mexico_universidad_lp:
                logger.info("Reglas Universidad Mexico activas para esta LP")

            await self.page.goto(
                lead.landing_url,
                wait_until="domcontentloaded",
                timeout=45000,
            )
            await self._soft_wait_network()
            await self.page.wait_for_timeout(3000)

            if self._mexico_universidad_lp:
                await self._prepare_universidad_mexico_flow()
            elif self.form_type == "lateral":
                await self._prepare_lateral_flow(level)
            elif self.form_type == "footer":
                await self._prepare_footer_flow()
            elif self.form_type in ["tarjeta", "targeta"]:
                await self._prepare_tarjeta_flow(level)
            else:
                logger.info("Form LP: se buscara formulario visible")

            if self._mexico_universidad_lp:
                self.form_scope = await self._find_universidad_mexico_form_scope()
            else:
                self.form_scope = await self._find_form_scope(self.form_type)
            if not self.form_scope:
                logger.warning("No se encontro formulario usable")
                return False

            if self.form_type == "footer" and self._mexico_utel_lp:
                footer_ready = await self._wait_for_footer_fields()
                if not footer_ready:
                    return False
                self.form_scope = await self._find_form_scope(self.form_type)
                if not self.form_scope:
                    logger.warning("Footer: no se encontro formulario usable despues de esperar campos")
                    return False
                logger.info(f"Footer: espera fija de {int(FOOTER_BEFORE_FILL_DELAY_MS / 1000)}s antes de llenar campos")
                await self.page.wait_for_timeout(FOOTER_BEFORE_FILL_DELAY_MS)

            await self._log_fields("antes de llenar")
            if self._mexico_universidad_lp:
                filled = await self._fill_universidad_mexico_form(
                    test_email=lead.test_email,
                    level=level,
                    raw_level=raw_level,
                )
            else:
                filled = await self._fill_form(
                    test_email=lead.test_email,
                    level=level,
                    modality_level=raw_level if self._mexico_utel_lp else level,
                )
            await self._log_fields("despues de llenar")
            if not filled:
                return False

            submitted = await self._submit_form()
            if not submitted:
                return False

            if self._mexico_universidad_lp:
                if not await self._validate_universidad_mexico_submission():
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

    def _is_mexico_utel_lp(self, url: str) -> bool:
        return self.country.id == "mexico" and str(url or "").strip().lower().startswith("https://utel.edu")

    def _is_mexico_universidad_lp(self, url: str) -> bool:
        return self.country.id == "mexico" and str(url or "").strip().lower().startswith(
            "https://universidad.utel.edu.mx"
        )

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

    def _modality_preferences(self, level: str) -> list[str]:
        normalized = self._norm(level)
        if "hibrid" in normalized:
            return ["Hibrida", "Híbrida", "Modalidad Hibrida", "Modalidad Híbrida"]
        if "ejecutiv" in normalized:
            return ["Ejecutiva", "Ejecutivo", "Modalidad Ejecutiva"]
        return ["En linea", "En línea", "Online"]

    async def _soft_wait_network(self) -> None:
        try:
            await self.page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            logger.debug("networkidle no completo; continuo con DOM cargado")

    async def _prepare_footer_flow(self) -> None:
        logger.info("Preparando flujo Footer")
        if await self._scroll_to_form_id("FooterBLC"):
            if self._mexico_utel_lp:
                await self._wait_for_footer_fields()
            return
        await self._scroll_until_contact_form()
        if self._mexico_utel_lp:
            await self._wait_for_footer_fields()

    async def _prepare_universidad_mexico_flow(self) -> None:
        logger.info("Preparando flujo Universidad Mexico: formulario visible de LP")
        if await self._wait_for_universidad_mexico_form(timeout_ms=15000):
            return

        await self._scroll_until_contact_form(max_scrolls=10)
        await self._wait_for_universidad_mexico_form(timeout_ms=30000)

    async def _wait_for_universidad_mexico_form(self, timeout_ms: int = 30000) -> bool:
        attempts = max(int(timeout_ms / 500), 1)
        for _ in range(attempts):
            if await self._mark_universidad_mexico_form_scope():
                logger.info("Universidad Mexico: formulario visible detectado")
                return True
            await self.page.wait_for_timeout(500)

        logger.warning("Universidad Mexico: no se detecto formulario visible dentro del tiempo esperado")
        return False

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
        self._tarjeta_product_opened = False
        original_url = self.page.url

        if self._mexico_utel_lp:
            product_opened = await self._open_tarjeta_product_with_retries(level, original_url)
        else:
            product_opened = await self._search_program_from_generic_page(level, original_url)
        if not product_opened:
            suffix = f" en {TARJETA_PRODUCT_TIMEOUT_SECONDS}s" if self._mexico_utel_lp else ""
            logger.warning(f"Location=Tarjeta: no se selecciono una LP de producto{suffix}")
            return

        self._tarjeta_product_opened = True
        await self._soft_wait_network()
        await self.page.wait_for_timeout(2500)
        if not await self._scroll_to_form_id("TarjetaBLC"):
            await self._scroll_until_contact_form()

    async def _open_tarjeta_product_with_retries(self, level: str, original_url: str) -> bool:
        deadline = monotonic() + TARJETA_PRODUCT_TIMEOUT_SECONDS
        attempt = 0

        while monotonic() < deadline:
            attempt += 1
            remaining = int(deadline - monotonic())
            logger.info(f"Tarjeta: intento {attempt} para abrir LP de producto; quedan {remaining}s")

            try:
                if self.page.url != original_url:
                    await self.page.goto(original_url, wait_until="domcontentloaded", timeout=45000)
                    await self._soft_wait_network()
                    await self.page.wait_for_timeout(1500)
                elif attempt > 1:
                    await self.page.reload(wait_until="domcontentloaded", timeout=45000)
                    await self._soft_wait_network()
                    await self.page.wait_for_timeout(1500)
            except Exception as e:
                logger.debug(f"Tarjeta: no se pudo reabrir LP original en intento {attempt}: {e}")

            product_opened = await self._search_program_from_generic_page(level, original_url)
            if not product_opened and await self._is_cloudflare_blocked():
                logger.warning("Tarjeta: pagina bloqueada por Cloudflare; se reabrira la LP original")
                if monotonic() < deadline:
                    await self.page.wait_for_timeout(TARJETA_PRODUCT_RETRY_DELAY_MS)
                continue

            if not product_opened:
                product_opened = await self._open_program_card_for_level(level, original_url)

            if product_opened:
                logger.info(f"Tarjeta: LP de producto abierta en intento {attempt}: {self.page.url}")
                return True

            if monotonic() < deadline:
                logger.info(
                    "Tarjeta: no se logro abrir producto; "
                    f"reintentando en {TARJETA_PRODUCT_RETRY_DELAY_MS}ms"
                )
                await self.page.wait_for_timeout(TARJETA_PRODUCT_RETRY_DELAY_MS)

        return False

    async def _open_program_card_for_level(self, level: str, original_url: str) -> bool:
        terms = self._level_preferences(level)
        try:
            result = await self.page.evaluate(
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
                    const blocked = [
                        'whatsapp',
                        'politica',
                        'privacidad',
                        'aviso',
                        'terminos',
                        'solicitar informacion',
                        'calcula tu beca',
                        'enviar',
                    ];
                    const isBlocked = (text, href) => blocked.some((term) => text.includes(term) || href.includes(term));
                    const scoreNode = (text, href, box) => {
                        if (!text || !wanted.some((term) => text.includes(term))) return 0;
                        if (isBlocked(text, href)) return 0;
                        let score = 1;
                        if (/licenciatura|maestria|doctorado|bachillerato|bootcamp|titulacion|hibrida/.test(text)) score += 4;
                        if (/programa|carrera|estudia|educacion|ingenieria|administracion|derecho|psicologia/.test(text)) score += 2;
                        if (href && !/#$/.test(href)) score += 3;
                        if (box.height >= 70 && box.height <= 520 && box.width >= 120) score += 2;
                        if (box.top > 80) score += 1;
                        return score;
                    };

                    const anchors = Array.from(document.querySelectorAll('a[href]'))
                        .filter(visible)
                        .map((anchor) => {
                            const card = anchor.closest('article, li, section, [class*=card], [class*=Card], [class*=program], [class*=Program]') || anchor;
                            const box = card.getBoundingClientRect();
                            const text = normalize(card.textContent || anchor.textContent);
                            const href = String(anchor.href || anchor.getAttribute('href') || '');
                            return {
                                href,
                                text,
                                score: scoreNode(text, href.toLowerCase(), box),
                                top: box.top,
                                x: box.left + box.width / 2,
                                y: box.top + box.height / 2,
                            };
                        })
                        .filter((item) => item.score > 0);

                    if (!anchors.length) return null;
                    anchors.sort((a, b) => b.score - a.score || a.top - b.top);
                    const bestScore = anchors[0].score;
                    const topGroup = anchors.filter((item) => item.score >= bestScore - 1).slice(0, 10);
                    const picked = topGroup[Math.floor(Math.random() * topGroup.length)];
                    return {
                        href: picked.href,
                        text: picked.text.slice(0, 180),
                        score: picked.score,
                        x: picked.x,
                        y: picked.y,
                    };
                }
                """,
                terms,
            )

            if not result:
                logger.info(f"Tarjeta: no se encontraron tarjetas/enlaces visibles para nivel '{level}'")
                return False

            logger.info(f"Tarjeta: tarjeta de programa seleccionada para nivel '{level}': {result}")

            x = result.get("x")
            y = result.get("y")
            if x is None or y is None:
                return False
            await self._human_click_point(float(x), float(y))
            changed = await self._wait_for_url_change(original_url)
            return changed and not await self._is_cloudflare_blocked()
        except Exception as e:
            logger.debug(f"No se pudo abrir tarjeta de programa: {e}")
            return False

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

    async def _search_program_from_generic_page(self, level: str, original_url: str) -> bool:
        query = self._program_query(level)
        await self._open_program_search_if_needed()
        searchers = await self._program_search_fields()

        for field in searchers:
            try:
                if await field.count() == 0:
                    continue
                field_info = await self._field_debug_info(field.first)
                logger.info(f"Tarjeta: probando buscador visible: {field_info}")
                await field.first.click(timeout=3000)
                await self.page.wait_for_timeout(250)
                await field.first.press("Control+A")
                await field.first.press("Backspace")
                await field.first.type(query, delay=80, timeout=6000)

                results_ready = await self._wait_for_search_results(level)
                if not results_ready:
                    logger.warning(f"Tarjeta: no cargaron resultados visibles para nivel '{level}'")
                    continue

                await self._log_search_result_candidates(level)
                clicked = await self._click_random_search_result_for_level(level)
                if not clicked:
                    logger.warning(f"No se encontro resultado visible para Tarjeta con nivel '{level}'")
                    continue

                changed = await self._wait_for_url_change(original_url, timeout_ms=20000)
                if changed:
                    if await self._is_cloudflare_blocked():
                        logger.warning("Tarjeta: Cloudflare bloqueo la pagina de producto despues del click")
                        return False
                    logger.info(f"Tarjeta: producto seleccionado y LP abierta: {self.page.url}")
                    return True

                logger.warning("Tarjeta: se hizo click en resultado, pero la URL no cambio")
                continue
            except Exception as e:
                logger.debug(f"Buscador no usable para tarjeta: {e}")

        logger.warning("No se pudo usar el buscador global para flujo Tarjeta")
        return False

    async def _open_program_search_if_needed(self) -> None:
        if await self._visible_program_search_input_exists():
            return

        try:
            opened = await self.page.evaluate(
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
                    const normalize = (value) => String(value || '').toLowerCase();
                    const candidates = Array.from(document.querySelectorAll('button, a, [role=button], svg'))
                        .filter(visible)
                        .map((el) => {
                            const box = el.getBoundingClientRect();
                            const text = normalize(`${el.textContent || ''} ${el.getAttribute('aria-label') || ''} ${el.getAttribute('class') || ''}`);
                            return { el, box, text };
                        })
                        .filter(({ box, text }) => box.top < 190
                            && box.left < 520
                            && (text.includes('search') || text.includes('buscar') || text.includes('lupa')));
                    const target = candidates[0]?.el;
                    if (!target) return false;
                    target.click();
                    return true;
                }
                """
            )
            if opened:
                logger.info("Tarjeta: se intento abrir el buscador desde el icono/lupa")
                await self.page.wait_for_timeout(800)
        except Exception as e:
            logger.debug(f"No se pudo abrir buscador de programa: {e}")

    async def _visible_program_search_input_exists(self) -> bool:
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
                    return Array.from(document.querySelectorAll('input, textarea')).some((el) => {
                        if (!visible(el)) return false;
                        const box = el.getBoundingClientRect();
                        const key = `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
                        if (/email|correo|phone|tel|nombre|name|apellido/.test(key)) return false;
                        return box.top < 220 && box.width >= 90;
                    });
                }
                """
            )
        except Exception:
            return False

    async def _program_search_fields(self) -> list[Locator]:
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

        for selector_index, selector in enumerate(selectors):
            locator = self.page.locator(selector)
            try:
                count = await locator.count()
            except Exception:
                continue

            for i in range(count):
                field = locator.nth(i)
                score = await self._score_program_search_field(field)
                if score > 0:
                    candidates.append((score, selector_index, field))

        candidates.sort(key=lambda item: (-item[0], item[1]))
        fields = [field for _, _, field in candidates]
        logger.info(f"Tarjeta: {len(fields)} candidatos de buscador detectados")
        return fields

    async def _score_program_search_field(self, field: Locator) -> int:
        try:
            return await field.evaluate(
                """
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
                """
            )
        except Exception:
            return 0

    async def _field_debug_info(self, field: Locator) -> dict:
        try:
            return await field.evaluate(
                """
                (el) => {
                    const box = el.getBoundingClientRect();
                    return {
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        aria: el.getAttribute('aria-label') || '',
                        value: el.value || '',
                        top: Math.round(box.top),
                        left: Math.round(box.left),
                        width: Math.round(box.width),
                        height: Math.round(box.height),
                    };
                }
                """
            )
        except Exception:
            return {}

    async def _wait_for_search_results(self, level: str, timeout_ms: int = 20000) -> bool:
        terms = [*self._level_preferences(level), self._program_query(level)]
        attempts = max(int(timeout_ms / 300), 1)
        for _ in range(attempts):
            count = await self._search_result_count_for_level(terms)
            if count > 0:
                logger.info(f"Tarjeta: {count} resultados visibles cargados para nivel '{level}'")
                return True
            await self.page.wait_for_timeout(300)
        return False

    async def _search_result_count_for_level(self, terms: list[str]) -> int:
        try:
            return await self.page.evaluate(
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
                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    const blocked = [
                        'sugerencias',
                        'modalidad',
                        'oferta academica',
                        'aspirantes',
                        'conoce utel',
                        'comunidad',
                        'becas',
                        'campus virtual',
                        'solicitar informacion',
                        'obtener beca',
                        'whatsapp',
                        'inscripciones',
                        'estudiantes',
                    ];
                    const candidateSelectors = [
                        'a[href]',
                        'button',
                        '[role=option]',
                        '[role=menuitem]',
                        'li',
                        'div',
                        'span',
                        'p',
                        '[class*=suggest]',
                        '[class*=Suggest]',
                        '[class*=option]',
                        '[class*=Option]',
                    ].join(',');
                    return Array.from(document.querySelectorAll(candidateSelectors))
                        .filter(visible)
                        .map((el) => {
                            const text = normalize(el.textContent);
                            const box = el.getBoundingClientRect();
                            const clickable = el.closest('a[href], button, [role=option], [role=menuitem], li, [class*=suggest], [class*=Suggest], [class*=option], [class*=Option]') || el;
                            const clickableBox = clickable.getBoundingClientRect();
                            return { text, box, clickableBox };
                        })
                        .filter(({ text, box }) => text
                            && wanted.some((term) => text.includes(term))
                            && !blocked.some((term) => text.includes(term))
                            && box.top > 40
                            && box.left < viewportWidth - 20
                            && box.height >= 18
                            && box.height < 220
                            && box.width >= 70)
                        .length;
                }
                """,
                terms,
            )
        except Exception as e:
            logger.debug(f"No se pudieron contar resultados de tarjeta: {e}")
            return 0

    async def _log_search_result_candidates(self, level: str) -> None:
        terms = self._level_preferences(level)
        try:
            candidates = await self.page.evaluate(
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
                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    return Array.from(document.querySelectorAll('a[href], button, [role], li, div, span, p'))
                        .filter(visible)
                        .map((el) => {
                            const box = el.getBoundingClientRect();
                            const text = String(el.textContent || '').trim().replace(/\\s+/g, ' ');
                            const normalizedText = normalize(text);
                            return {
                                tag: el.tagName,
                                role: el.getAttribute('role') || '',
                                cls: String(el.className || '').slice(0, 120),
                                href: el.href || el.getAttribute('href') || '',
                                text: text.slice(0, 180),
                                matched: wanted.some((term) => normalizedText.includes(term)),
                                top: Math.round(box.top),
                                left: Math.round(box.left),
                                width: Math.round(box.width),
                                height: Math.round(box.height),
                            };
                        })
                        .filter((item) => item.text
                            && item.top > 40
                            && item.left < viewportWidth - 20
                            && item.height > 8
                            && item.height < 260)
                        .slice(0, 40);
                }
                """,
                terms,
            )
            logger.info(f"Tarjeta diagnostico resultados para nivel '{level}': {candidates}")
        except Exception as e:
            logger.debug(f"No se pudo diagnosticar resultados de tarjeta: {e}")

    async def _click_random_search_result_for_level(self, level: str) -> bool:
        terms = [*self._level_preferences(level), self._program_query(level)]
        try:
            result = await self.page.evaluate(
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
                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    const blocked = [
                        'sugerencias',
                        'modalidad',
                        'oferta academica',
                        'aspirantes',
                        'conoce utel',
                        'comunidad',
                        'becas',
                        'campus virtual',
                        'solicitar informacion',
                        'obtener beca',
                        'whatsapp',
                        'inscripciones',
                        'estudiantes',
                    ];
                    const candidateSelectors = [
                        'a[href]',
                        'button',
                        '[role=option]',
                        '[role=menuitem]',
                        'li',
                        'div',
                        'span',
                        'p',
                        '[class*=suggest]',
                        '[class*=Suggest]',
                        '[class*=option]',
                        '[class*=Option]',
                    ].join(',');
                    const scoreItem = (item) => {
                        if (!item.text || !wanted.some((term) => item.text.includes(term))) return 0;
                        if (blocked.some((term) => item.text.includes(term))) return 0;
                        if (item.top < 70 || item.left >= viewportWidth - 20) return 0;
                        if (item.height < 18 || item.height > 170 || item.width < 70) return 0;

                        let score = 1;
                        if (item.href) score += 3;
                        if (item.height <= 120) score += 3;
                        if (/licenciatura|maestria|doctorado|bachillerato|bootcamp|titulacion|ingenieria|administracion|derecho|educacion|psicologia|tecnologia/.test(item.text)) {
                            score += 4;
                        }
                        if (item.text.length >= 18 && item.text.length <= 180) score += 2;
                        return score;
                    };

                    const nodes = Array.from(document.querySelectorAll(candidateSelectors))
                        .filter(visible)
                        .map((el) => {
                            const link = el.matches('a[href]') ? el : el.querySelector?.('a[href]');
                            const clickTarget = link
                                || el.closest('button, [role=option], [role=menuitem], li, [class*=suggest], [class*=Suggest], [class*=option], [class*=Option]')
                                || el;
                            const box = clickTarget.getBoundingClientRect();
                            return {
                                el,
                                text: normalize(el.textContent),
                                href: link ? link.href : '',
                                x: box.left + box.width / 2,
                                y: box.top + box.height / 2,
                                top: box.top,
                                left: box.left,
                                height: box.height,
                                width: box.width,
                            };
                        })
                        .map((item) => ({ ...item, score: scoreItem(item) }))
                        .filter((item) => item.score > 0);

                    if (!nodes.length) return null;
                    nodes.sort((a, b) => {
                        if (b.score !== a.score) return b.score - a.score;
                        if (a.href && !b.href) return -1;
                        if (!a.href && b.href) return 1;
                        return a.top - b.top;
                    });
                    const bestScore = nodes[0].score;
                    const topGroup = nodes.filter((item) => item.score >= bestScore - 1).slice(0, 8);
                    const picked = topGroup[Math.floor(Math.random() * topGroup.length)];
                    return {
                        href: picked.href,
                        x: picked.x,
                        y: picked.y,
                        text: picked.text,
                        score: picked.score,
                    };
                }
                """,
                terms,
            )

            if not result:
                return False

            x = result.get("x")
            y = result.get("y")
            if x is None or y is None:
                return False

            logger.info(f"Resultado aleatorio de tarjeta seleccionado por coordenadas para nivel '{level}': {result.get('text')}")
            await self._human_click_point(float(x), float(y))
            return True
        except Exception as e:
            logger.debug(f"No se pudo seleccionar resultado aleatorio de tarjeta: {e}")
            return False

    async def _human_click_point(self, x: float, y: float) -> None:
        await self.page.mouse.move(x - 18, y - 8, steps=8)
        await self.page.wait_for_timeout(180)
        await self.page.mouse.move(x, y, steps=6)
        await self.page.wait_for_timeout(120)
        await self.page.mouse.down()
        await self.page.wait_for_timeout(90)
        await self.page.mouse.up()

    async def _is_cloudflare_blocked(self) -> bool:
        try:
            return await self.page.evaluate(
                """
                () => {
                    const text = String(document.body?.innerText || '').toLowerCase();
                    return text.includes('why have i been blocked')
                        || text.includes('cloudflare ray id')
                        || text.includes('this website is using a security service');
                }
                """
            )
        except Exception:
            return False

    async def _wait_for_url_change(self, original_url: str, timeout_ms: int = 10000) -> bool:
        attempts = max(int(timeout_ms / 400), 1)
        for _ in range(attempts):
            if self.page.url != original_url:
                return True
            await self.page.wait_for_timeout(400)
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

    async def _wait_for_footer_fields(self, timeout_ms: int = FOOTER_FIELDS_TIMEOUT_MS) -> bool:
        logger.info(f"Footer: esperando hasta {int(timeout_ms / 1000)}s a que carguen los campos")
        attempts = max(int(timeout_ms / 500), 1)
        for _ in range(attempts):
            if await self._footer_fields_ready():
                logger.info("Footer: campos obligatorios visibles")
                return True
            await self.page.wait_for_timeout(500)

        logger.warning("Footer: no cargaron todos los campos obligatorios dentro del tiempo esperado")
        return False

    async def _footer_fields_ready(self) -> bool:
        try:
            return await self._scope().evaluate(
                """
                (root) => {
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0
                            && !el.disabled
                            && el.type !== 'hidden';
                    };
                    const fields = Array.from(root.querySelectorAll('input, select, textarea'))
                        .filter(visible)
                        .map((el) => `${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.type || ''}`.toLowerCase());
                    return fields.some((x) => x.includes('email') || x.includes('correo'))
                        && fields.some((x) => x.includes('phone') || x.includes('tel') || x.includes('telefono') || x.includes('celular') || x.includes('mobile'))
                        && fields.some((x) => x.includes('name') || x.includes('nombre') || x.includes('first_name'));
                }
                """
            )
        except Exception as e:
            logger.debug(f"Footer: no se pudo validar carga de campos: {e}")
            return False

    async def _find_form_scope(self, form_type: str) -> Optional[Locator]:
        if form_type == "tarjeta" and not self._tarjeta_product_opened:
            logger.warning("Location=Tarjeta, pero no se abrio una LP de producto; no se llenara el formulario inicial")
            return None

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

    async def _find_universidad_mexico_form_scope(self) -> Optional[Locator]:
        if not await self._mark_universidad_mexico_form_scope():
            return None

        scope = self.page.locator("[data-codex-universidad-form-scope='true']")
        try:
            if await scope.count() > 0:
                logger.info("Universidad Mexico: usando formulario visible detectado")
                return scope.first
        except Exception:
            pass
        return None

    async def _mark_universidad_mexico_form_scope(self) -> bool:
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
                    const fieldVisible = (el) => {
                        if (!visible(el) || el.disabled || el.type === 'hidden') return false;
                        const key = `${el.type || ''} ${el.name || ''} ${el.id || ''} ${el.placeholder || ''}`.toLowerCase();
                        return !key.includes('search') && !key.includes('buscar');
                    };
                    const keyFor = (el) =>
                        `${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.type || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase();
                    const hasSubmit = (root) => Array.from(root.querySelectorAll('button, input[type=submit], [role=button]'))
                        .filter(visible)
                        .some((el) => /enviar|solicitar|informaci|beca|comienza|registr/i.test(el.textContent || el.value || ''));
                    const scoreRoot = (root) => {
                        if (!visible(root)) return 0;
                        const fields = Array.from(root.querySelectorAll('input, select, textarea')).filter(fieldVisible);
                        if (fields.length < 2) return 0;
                        const keys = fields.map(keyFor);
                        let score = 0;
                        if (keys.some((x) => x.includes('email') || x.includes('correo'))) score += 6;
                        if (keys.some((x) => x.includes('phone') || x.includes('tel') || x.includes('telefono') || x.includes('celular') || x.includes('mobile'))) score += 5;
                        if (keys.some((x) => x.includes('name') || x.includes('nombre'))) score += 5;
                        if (fields.some((el) => el.tagName === 'SELECT')) score += 2;
                        if (fields.some((el) => el.required)) score += 2;
                        if (hasSubmit(root)) score += 3;
                        score += Math.min(fields.length, 6);
                        return score;
                    };

                    document.querySelectorAll('[data-codex-universidad-form-scope]').forEach((el) => {
                        el.removeAttribute('data-codex-universidad-form-scope');
                    });

                    const candidates = Array.from(document.querySelectorAll('form, section, aside, article, div'))
                        .filter(visible)
                        .map((el) => {
                            const box = el.getBoundingClientRect();
                            return { el, score: scoreRoot(el), area: box.width * box.height };
                        })
                        .filter((item) => item.score >= 8)
                        .sort((a, b) => b.score - a.score || a.area - b.area);

                    if (!candidates.length) return false;
                    candidates[0].el.setAttribute('data-codex-universidad-form-scope', 'true');
                    return true;
                }
                """
            )
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudo marcar formulario visible: {e}")
            return False

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

    async def _fill_form(self, test_email: str, level: str, modality_level: str = "") -> bool:
        logger.info("Llenando formulario en orden dependiente")

        level_preferences = self._level_preferences(level)

        await self._select_field("modality", preferred=self._modality_preferences(modality_level or level))
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

        await self._set_input(
            ["#first_name", "input[name='first_name']", "input[name='name']", "input[name*='nombre' i]", "input[id*='nombre' i]"],
            self.country.fake_name,
            "nombre",
        )
        await self._set_input(
            ["#email", "input[name='email']", "input[type='email']", "input[name*='correo' i]", "input[id*='correo' i]"],
            test_email,
            "email",
        )
        await self._set_input(
            [
                "#phone",
                "input[name='phone']",
                "input[type='tel']",
                "input[name*='telefono' i]",
                "input[id*='telefono' i]",
                "input[name*='celular' i]",
                "input[id*='celular' i]",
                "input[name*='mobile' i]",
            ],
            self.country.fake_phone,
            "telefono",
        )
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

    async def _fill_universidad_mexico_form(self, test_email: str, level: str, raw_level: str) -> bool:
        logger.info("Universidad Mexico: llenando formulario visible con logica CMS y fallback dinamico")

        await self._fill_universidad_mexico_cms_sequence(level=level, raw_level=raw_level)
        await self.page.wait_for_timeout(800)

        await self._fill_universidad_mexico_selects(level=level, raw_level=raw_level)
        await self.page.wait_for_timeout(800)

        program_selected = await self._select_universidad_mexico_custom_program(level)
        if not program_selected:
            logger.warning("Universidad Mexico: no se selecciono programa; no se enviara formulario")
            return False

        await self._fill_universidad_mexico_inputs(test_email=test_email)
        await self._check_privacy()

        state = await self._universidad_mexico_form_state()
        logger.info(f"Universidad Mexico: estado final antes de submit: {state}")

        if state.get("missing_required"):
            logger.warning(f"Universidad Mexico: faltan campos requeridos visibles: {state.get('missing_required')}")
            return False

        if state.get("has_program") and not state.get("program"):
            logger.warning("Universidad Mexico: programa visible sin seleccionar")
            return False

        missing_contact = [
            key for key in ["name", "email", "phone"]
            if state.get(f"has_{key}") and not state.get(key)
        ]
        if missing_contact:
            logger.warning(f"Universidad Mexico: campos de contacto presentes sin completar: {missing_contact}")
            return False

        if state.get("has_checkbox") and not state.get("checkbox_checked"):
            logger.warning("Universidad Mexico: checkbox de privacidad no quedo marcado")
            return False

        return True

    async def _fill_universidad_mexico_cms_sequence(self, level: str, raw_level: str) -> None:
        level_preferences = self._level_preferences(level)
        modality_level = raw_level or level

        logger.info("Universidad Mexico: aplicando secuencia nivel -> programa")

        level_ok = await self._select_universidad_mexico_level_by_context(level)
        if not level_ok:
            logger.info("Universidad Mexico: nivel no resuelto por contexto; probando selectores CMS")
            await self._select_field(
                "modality",
                preferred=self._modality_preferences(modality_level),
            )
        await self.page.wait_for_timeout(3000)

        area_exists = await self._select_exists("area")
        area_ok = await self._select_field(
            "area",
            preferred=level_preferences,
            require_preferred_match=True,
        )
        if area_exists and not area_ok:
            logger.warning(f"Universidad Mexico: no se pudo seleccionar nivel requerido en Area: {level}")
        await self.page.wait_for_timeout(3000)

        program_ok = await self._select_universidad_mexico_program_random()
        if not program_ok:
            logger.info("Universidad Mexico: programa no resuelto con selectores nativos; se usara fallback dinamico")

    async def _fill_universidad_mexico_selects(self, level: str, raw_level: str) -> None:
        payload = {
            "levelPreferences": [*self._level_preferences(level), self._program_query(level)],
            "modalityPreferences": self._modality_preferences(raw_level or level),
        }
        try:
            result = await self._scope().evaluate(
                """
                (root, payload) => {
                    const { levelPreferences, modalityPreferences } = payload;
                    const clean = (value) => String(value || '').trim();
                    const norm = (value) => clean(value).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0
                            && !el.disabled;
                    };
                    const bad = new Set(['', '-', '--', 'seleccionar', 'selecciona', 'select', 'choose', 'modalidad:']);
                    const pickOption = (select, preferences, requireMatch = false) => {
                        const options = Array.from(select.options || [])
                            .map((option, index) => ({
                                index,
                                text: clean(option.textContent),
                                value: clean(option.value),
                                disabled: option.disabled,
                            }))
                            .filter((option) => {
                                const text = norm(option.text);
                                const value = norm(option.value);
                                return option.index > 0 && !option.disabled && !bad.has(text) && !bad.has(value);
                            });
                        if (!options.length) return null;

                        let chosen = null;
                        let matched = false;
                        for (const wantedRaw of preferences || []) {
                            const wanted = norm(wantedRaw);
                            if (!wanted) continue;
                            chosen = options.find((option) => {
                                const text = norm(option.text);
                                const value = norm(option.value);
                                return text === wanted || value === wanted
                                    || text.includes(wanted) || value.includes(wanted)
                                    || wanted.includes(text);
                            });
                            if (chosen) {
                                matched = true;
                                break;
                            }
                        }
                        if (requireMatch && !matched) return null;
                        return { ...(chosen || options[0]), matched };
                    };
                    const labelText = (el) => {
                        const id = el.id ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent || '' : '';
                        const parentLabel = el.closest('label')?.textContent || '';
                        return `${id} ${parentLabel}`;
                    };
                    const changed = [];
                    for (const select of Array.from(root.querySelectorAll('select')).filter(visible)) {
                        const key = norm(`${select.name || ''} ${select.id || ''} ${select.getAttribute('aria-label') || ''} ${labelText(select)} ${Array.from(select.options || []).map((o) => o.textContent).join(' ')}`);
                        const isModality = /modalidad|en linea|online|ejecutiv|hibrid/.test(key);
                        const isLevelOrProgram = /nivel|grado|area|program|carrera|licenciatura|maestria|doctorado|posgrado/.test(key);
                        const current = clean(select.value);
                        let picked = null;
                        if (isModality) picked = pickOption(select, modalityPreferences, true);
                        if (!picked && isLevelOrProgram) picked = pickOption(select, levelPreferences, false);
                        if (!picked && (select.required || !current)) picked = pickOption(select, [], false);
                        if (!picked) continue;

                        select.selectedIndex = picked.index;
                        select.value = picked.value;
                        select.dispatchEvent(new Event('input', { bubbles: true }));
                        select.dispatchEvent(new Event('change', { bubbles: true }));
                        select.dispatchEvent(new Event('blur', { bubbles: true }));
                        changed.push({ name: select.name || '', id: select.id || '', text: picked.text, value: picked.value, matched: picked.matched });
                    }
                    return changed;
                }
                """,
                payload,
            )
            logger.info(f"Universidad Mexico: selects completados: {result}")
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudieron completar selects dinamicos: {e}")

    async def _select_universidad_mexico_level_by_context(self, level: str) -> bool:
        preferences = self._level_preferences(level)
        try:
            result = await self._scope().evaluate(
                """
                (root, preferences) => {
                    const clean = (value) => String(value || '').trim();
                    const norm = (value) => clean(value).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0
                            && !el.disabled;
                    };
                    const bad = /^(|\\-|--|selecciona|seleccione|select|choose)$/;
                    const labelText = (el) => {
                        const idLabel = el.id ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent || '' : '';
                        const parentLabel = el.closest('label')?.textContent || '';
                        return `${idLabel} ${parentLabel}`;
                    };
                    const pickOption = (select) => {
                        const options = Array.from(select.options || [])
                            .map((option, index) => ({
                                index,
                                text: clean(option.textContent),
                                value: clean(option.value),
                                disabled: option.disabled,
                            }))
                            .filter((option) => {
                                const text = norm(option.text);
                                const value = norm(option.value);
                                return option.index > 0 && !option.disabled && !bad.test(text) && !bad.test(value);
                            });
                        for (const wantedRaw of preferences || []) {
                            const wanted = norm(wantedRaw);
                            if (!wanted) continue;
                            const picked = options.find((option) => {
                                const text = norm(option.text);
                                const value = norm(option.value);
                                return text === wanted || value === wanted || text.includes(wanted) || value.includes(wanted) || wanted.includes(text);
                            });
                            if (picked) return picked;
                        }
                        return null;
                    };
                    const candidates = Array.from(root.querySelectorAll('select'))
                        .filter(visible)
                        .map((select) => {
                            const optionText = Array.from(select.options || []).map((option) => option.textContent || '').join(' ');
                            const key = norm(`${select.name || ''} ${select.id || ''} ${select.getAttribute('aria-label') || ''} ${labelText(select)} ${optionText}`);
                            const picked = pickOption(select);
                            let score = 0;
                            if (/nivel|grado|modalidad|programa|carrera|licenciatura|maestria|doctorado|posgrado/.test(key)) score += 8;
                            if (/nombre|correo|email|telefono|celular|pais|estado/.test(key)) score -= 10;
                            if (picked) score += 20;
                            return { select, picked, score };
                        })
                        .filter((item) => item.picked && item.score > 0)
                        .sort((a, b) => b.score - a.score);

                    const target = candidates[0];
                    if (!target) return null;
                    target.select.selectedIndex = target.picked.index;
                    target.select.value = target.picked.value;
                    target.select.dispatchEvent(new Event('input', { bubbles: true }));
                    target.select.dispatchEvent(new Event('change', { bubbles: true }));
                    target.select.dispatchEvent(new Event('blur', { bubbles: true }));
                    return {
                        name: target.select.name || '',
                        id: target.select.id || '',
                        text: target.picked.text,
                        value: target.picked.value,
                    };
                }
                """,
                preferences,
            )

            if result:
                logger.info(f"Universidad Mexico: nivel seleccionado por contexto: {result}")
                await self.page.wait_for_timeout(1500)
                return True
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudo seleccionar nivel por contexto: {e}")

        return False

    async def _select_universidad_mexico_program_random(self) -> bool:
        try:
            result = await self._scope().evaluate(
                """
                (root) => {
                    const clean = (value) => String(value || '').trim();
                    const norm = (value) => clean(value).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0
                            && !el.disabled;
                    };
                    const bad = /^(|\\-|--|selecciona|seleccione|select|choose|programa|selecciona un programa)$/;
                    const labelText = (el) => {
                        const idLabel = el.id ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent || '' : '';
                        const parentLabel = el.closest('label')?.textContent || '';
                        return `${idLabel} ${parentLabel}`;
                    };
                    const programSelects = Array.from(root.querySelectorAll('select'))
                        .filter(visible)
                        .map((select) => {
                            const optionText = Array.from(select.options || []).map((option) => option.textContent || '').join(' ');
                            const key = norm(`${select.name || ''} ${select.id || ''} ${select.getAttribute('aria-label') || ''} ${labelText(select)} ${optionText}`);
                            let score = 0;
                            if (/program|programa|carrera|interes/.test(key)) score += 10;
                            if (/administracion|ingenieria|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria|tecnologias|mercadotecnia/.test(key)) score += 6;
                            if (/modalidad|pais|estado|nombre|correo|email|telefono|celular/.test(key)) score -= 10;
                            return { select, score };
                        })
                        .filter((item) => item.score > 0)
                        .sort((a, b) => b.score - a.score);

                    for (const item of programSelects) {
                        const options = Array.from(item.select.options || [])
                            .map((option, index) => ({
                                index,
                                text: clean(option.textContent),
                                value: clean(option.value),
                                disabled: option.disabled,
                            }))
                            .filter((option) => {
                                const text = norm(option.text);
                                const value = norm(option.value);
                                return option.index > 0
                                    && !option.disabled
                                    && !bad.test(text)
                                    && !bad.test(value);
                            });

                        if (!options.length) continue;
                        const picked = options[Math.floor(Math.random() * options.length)];
                        item.select.selectedIndex = picked.index;
                        item.select.value = picked.value;
                        item.select.dispatchEvent(new Event('input', { bubbles: true }));
                        item.select.dispatchEvent(new Event('change', { bubbles: true }));
                        item.select.dispatchEvent(new Event('blur', { bubbles: true }));
                        return {
                            name: item.select.name || '',
                            id: item.select.id || '',
                            text: picked.text,
                            value: picked.value,
                            options: options.length,
                        };
                    }

                    return null;
                }
                """
            )

            if result:
                logger.info(f"Universidad Mexico: programa nativo seleccionado al azar: {result}")
                await self.page.wait_for_timeout(1500)
                return True
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudo seleccionar programa nativo al azar: {e}")

        return False

    # ------------------------------------------------------------------ #
    #  BLOQUE CORREGIDO: selección de programa custom (Choices.js / etc.) #
    # ------------------------------------------------------------------ #

    async def _fill_choices_select(self, select_name: str, level: str) -> bool:
        """
        Maneja SELECTs nativos envueltos por Choices.js / Tom Select / Select2.

        Estrategia:
        1. Busca el SELECT nativo por name (incluyendo el patrón data[name]).
        2. Lee sus opciones reales y elige una (prefiere coincidir con level).
        3. Aplica el valor en el SELECT nativo y dispara eventos.
        4. Abre el contenedor custom (.choices__inner, [role=combobox], etc.)
           y hace click en la opción correspondiente para sincronizar la UI.
        """
        try:
            result = await self._scope().evaluate(
                """
                (root, payload) => {
                    const { selectName, levelTerms } = payload;
                    const norm = (v) => String(v || '').trim().toLowerCase()
                        .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const b = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden'
                            && b.width > 0 && b.height > 0 && !el.disabled;
                    };
                    const bad = /^(|--|selecciona|selecciona un programa|programa|choose|select)$/;

                    // 1. Encuentra el SELECT nativo (puede estar oculto con display:none)
                    const nativeSelect =
                        root.querySelector(`select[name="${selectName}"]`) ||
                        root.querySelector(`select[name="data[${selectName}]"]`);
                    if (!nativeSelect) return { error: 'native_select_not_found' };

                    // 2. Lee opciones válidas
                    const options = Array.from(nativeSelect.options || [])
                        .map((o, i) => ({
                            index: i,
                            text: String(o.textContent || '').trim(),
                            value: String(o.value || '').trim(),
                            disabled: o.disabled,
                        }))
                        .filter(o => o.index > 0 && !o.disabled
                            && !bad.test(norm(o.text)) && !bad.test(norm(o.value)));

                    if (!options.length) return { error: 'no_valid_options' };

                    // 3. Elige opción: primero intenta matchear level, si no elige al azar
                    let picked = null;
                    for (const term of (levelTerms || [])) {
                        const want = norm(term);
                        if (!want) continue;
                        picked = options.find(o =>
                            norm(o.text).includes(want) || norm(o.value).includes(want)
                        );
                        if (picked) break;
                    }
                    if (!picked) picked = options[Math.floor(Math.random() * options.length)];

                    // 4. Aplica en el SELECT nativo
                    nativeSelect.selectedIndex = picked.index;
                    nativeSelect.value = picked.value;
                    ['input', 'change', 'blur'].forEach(ev =>
                        nativeSelect.dispatchEvent(new Event(ev, { bubbles: true }))
                    );

                    // 5. Busca el wrapper del custom dropdown asociado al SELECT
                    //    Choices.js envuelve el SELECT dentro de .choices o data-type="select-one"
                    const choicesWrapper =
                        nativeSelect.closest('.choices, [data-type="select-one"]') ||
                        nativeSelect.parentElement;

                    let clickedCustom = false;
                    if (choicesWrapper) {
                        // Abre el dropdown
                        const trigger = choicesWrapper.querySelector(
                            '.choices__inner, [class*=control], [class*=placeholder], ' +
                            '[aria-expanded], [role=combobox], [class*=trigger]'
                        );
                        if (trigger) {
                            trigger.click();
                            // Espera mínima síncrona no es posible en evaluate;
                            // busca las opciones que ya deberían estar en el DOM
                            const optionEls = Array.from(choicesWrapper.querySelectorAll(
                                '.choices__item--choice:not(.choices__item--disabled), ' +
                                '[role=option], li[data-value], [class*=option-item]'
                            ));
                            const wantedNorm = norm(picked.text);
                            for (const el of optionEls) {
                                const elText = norm(el.textContent || '');
                                if (elText && (elText.includes(wantedNorm) || wantedNorm.includes(elText))) {
                                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                    clickedCustom = true;
                                    break;
                                }
                            }
                            // Si no encontramos la opción, cerramos el dropdown
                            if (!clickedCustom) trigger.click();
                        }
                    }

                    return {
                        picked: picked.text,
                        value: picked.value,
                        clickedCustom,
                        nativeValue: nativeSelect.value,
                    };
                }
                """,
                {"selectName": select_name, "levelTerms": self._level_preferences(level)},
            )

            if result and not result.get("error"):
                logger.info(f"Choices select '{select_name}': {result}")
                await self.page.wait_for_timeout(600)
                return True

            logger.warning(f"Choices select '{select_name}': {result}")
            return False

        except Exception as e:
            logger.debug(f"_fill_choices_select fallo para '{select_name}': {e}")
            return False

    async def _wait_for_custom_program_options(self, timeout_ms: int = 3000) -> bool:
        """Espera a que el dropdown custom muestre opciones reales y clicables."""
        attempts = max(int(timeout_ms / 300), 1)
        for _ in range(attempts):
            try:
                count = await self.page.evaluate(
                    """
                    () => {
                        const norm = (v) => String(v || '').trim().toLowerCase()
                            .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                        const bad = /selecciona|programa$|choose|select|--/;
                        const visible = (el) => {
                            const s = window.getComputedStyle(el);
                            const b = el.getBoundingClientRect();
                            return s.display !== 'none' && s.visibility !== 'hidden'
                                && b.width > 0 && b.height > 0;
                        };
                        // Selectores para Choices.js, Select2, Tom Select y dropdowns custom genéricos
                        const selectors = [
                            '.choices__list--dropdown .choices__item--choice:not(.choices__item--disabled)',
                            '[role=listbox] [role=option]',
                            '[class*=dropdown][class*=open] li',
                            '[class*=dropdown][class*=Open] li',
                            '[class*=options-list] li',
                            '[class*=optionsList] li',
                            'ul[class*=option] li',
                            '[aria-expanded=true] [role=option]',
                        ];
                        for (const sel of selectors) {
                            const items = Array.from(document.querySelectorAll(sel))
                                .filter(visible)
                                .filter(el => {
                                    const t = norm(el.textContent || '');
                                    return t.length > 3 && !bad.test(t);
                                });
                            if (items.length > 0) return items.length;
                        }
                        return 0;
                    }
                    """
                )
                if count > 0:
                    logger.info(f"Universidad Mexico: {count} opciones custom visibles en dropdown")
                    return True
            except Exception:
                pass
            await self.page.wait_for_timeout(300)
        return False

    async def _sync_native_select_from_custom(self, level: str) -> None:
        """
        Después de que el usuario selecciona en el dropdown custom,
        sincroniza el SELECT nativo con el texto visible del control
        para que los validadores del framework lo detecten como filled.
        """
        try:
            await self._scope().evaluate(
                """
                (root, levelTerms) => {
                    const norm = (v) => String(v || '').trim().toLowerCase()
                        .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const bad = /selecciona|programa$|choose|select|--/;

                    // Texto actualmente mostrado en el control custom
                    const controlSelectors = [
                        '.choices__item--selectable:not(.choices__item--choice)',
                        '.choices [class*=singleValue]',
                        '[aria-selected=true]',
                        '[class*=selected-value]',
                        '[class*=selectedValue]',
                        '[class*=value-container] [class*=single]',
                    ];
                    let displayedText = '';
                    for (const sel of controlSelectors) {
                        const el = root.querySelector(sel);
                        if (el) {
                            const t = String(el.textContent || '').trim();
                            if (t && !bad.test(norm(t))) { displayedText = t; break; }
                        }
                    }

                    const nativeSelect =
                        root.querySelector('select[name="program"]') ||
                        root.querySelector('select[name="data[program]"]');
                    if (!nativeSelect || !displayedText) return;

                    // Busca la opción del SELECT nativo que matchee el texto mostrado
                    const match = Array.from(nativeSelect.options || []).find(o => {
                        const oNorm = norm(o.textContent || '');
                        const dNorm = norm(displayedText);
                        return oNorm.includes(dNorm) || dNorm.includes(oNorm);
                    });
                    if (match) {
                        nativeSelect.selectedIndex = match.index;
                        nativeSelect.value = match.value;
                        ['input', 'change', 'blur'].forEach(ev =>
                            nativeSelect.dispatchEvent(new Event(ev, { bubbles: true }))
                        );
                    }
                }
                """,
                self._level_preferences(level),
            )
        except Exception as e:
            logger.debug(f"_sync_native_select_from_custom fallo: {e}")

    async def _select_universidad_mexico_custom_program(self, level: str) -> bool:
        """
        Selecciona el programa de interés en el formulario Universidad México.

        El formulario tiene un SELECT nativo (data[program]) oculto bajo un
        custom dropdown (Choices.js o similar). El método ataca el problema
        en 4 capas:

        Capa 1: SELECT nativo ya tiene valor válido → retornar True de inmediato.
        Capa 2: _fill_choices_select → llena nativo + intenta sincronizar UI.
        Capa 3: Click en el control visual + selección de opción visible (3 intentos).
        Capa 4: Keyboard fallback (ArrowDown + Enter).
        """
        # Capa 1: ¿Ya está seleccionado?
        if await self._universidad_mexico_program_is_selected():
            logger.info("Universidad Mexico: programa ya seleccionado antes de custom_program")
            return True

        # Capa 2: Choices.js / SELECT nativo envuelto
        filled = await self._fill_choices_select("program", level)
        if filled:
            await self.page.wait_for_timeout(800)
            if await self._universidad_mexico_program_is_selected():
                logger.info("Universidad Mexico: programa seleccionado via Choices.js wrapper")
                return True

        # Capa 3: Click en el control visual y selección de opción
        for attempt in range(1, 4):
            logger.info(f"Universidad Mexico: intento {attempt} de seleccion de programa custom")

            target = await self._universidad_mexico_program_control()
            if not target:
                logger.warning("Universidad Mexico: no se encontro control visual de programa")
                break

            await self._human_click_point(float(target["x"]), float(target["y"]))
            await self.page.wait_for_timeout(700)

            options_visible = await self._wait_for_custom_program_options(timeout_ms=3000)
            if not options_visible:
                logger.warning(f"Universidad Mexico: no aparecieron opciones en intento {attempt}")
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(400)
                continue

            # Intenta click por coincidencia con level
            clicked = await self._click_universidad_mexico_visible_program_option(level)
            if not clicked:
                # Si no hay match por level, toma cualquier opción válida
                option = await self._universidad_mexico_random_program_option(level)
                if option:
                    await self._human_click_point(float(option["x"]), float(option["y"]))
                    clicked = True

            if clicked:
                await self.page.wait_for_timeout(800)
                # Sincroniza SELECT nativo con lo que el custom dropdown muestra
                await self._sync_native_select_from_custom(level)
                if await self._universidad_mexico_program_is_selected():
                    return True

        # Capa 4: Keyboard fallback
        if await self._select_universidad_mexico_program_with_keyboard():
            return True

        logger.error("Universidad Mexico: no se pudo seleccionar programa despues de todos los intentos")
        return False

    async def _click_universidad_mexico_visible_program_option(self, level: str) -> bool:
        terms = [*self._level_preferences(level), self._program_query(level)]
        try:
            result = await self.page.evaluate(
                """
                (terms) => {
                    const norm = (value) => String(value || '').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0;
                    };
                    const wanted = terms.map(norm).filter(Boolean);
                    const blocked = /selecciona|programa de interes|programa$|modalidad|maestria$|licenciatura$|doctorado$|nombre|correo|email|telefono|celular|privacidad|aviso|enviar|whatsapp/;
                    const optionRoot = (el) => el.closest('[role=option], [id*=option], [class*=option], [class*=Option], li') || el;
                    const nodes = Array.from(document.querySelectorAll('[role=option], [id*=option], [class*=option], [class*=Option], li, div'))
                        .filter(visible)
                        .map((el) => {
                            const root = optionRoot(el);
                            if (!visible(root)) return null;
                            const box = root.getBoundingClientRect();
                            const text = String(root.textContent || '').trim();
                            const normalized = norm(text);
                            if (!normalized || normalized.length < 4 || normalized.length > 180) return null;
                            if (blocked.test(normalized)) return null;
                            if (box.width < 140 || box.height < 18 || box.height > 80) return null;
                            let score = 0;
                            if (/licenciatura|maestria|doctorado|ingenieria|administracion|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria|tecnologias|mercadotecnia/.test(normalized)) score += 10;
                            if (wanted.some((term) => normalized.includes(term))) score += 2;
                            if (root.getAttribute('role') === 'option') score += 8;
                            if (/option/.test(norm(root.className || ''))) score += 6;
                            if (score <= 0) return null;
                            return { root, text, score };
                        })
                        .filter(Boolean);

                    if (!nodes.length) return null;
                    nodes.sort((a, b) => b.score - a.score);
                    const bestScore = nodes[0].score;
                    const top = nodes.filter((item) => item.score >= bestScore - 3).slice(0, 12);
                    const picked = top[Math.floor(Math.random() * top.length)];
                    picked.root.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
                    picked.root.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                    picked.root.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                    picked.root.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    return { text: picked.text.slice(0, 140), score: picked.score };
                }
                """,
                terms,
            )

            if result:
                logger.info(f"Universidad Mexico: opcion de programa clickeada por DOM: {result}")
                return True
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudo clickear opcion visible por DOM: {e}")

        return False

    async def _select_universidad_mexico_program_with_keyboard(self) -> bool:
        try:
            await self.page.keyboard.press("ArrowDown")
            await self.page.wait_for_timeout(250)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(1200)
            selected = await self._universidad_mexico_program_is_selected()
            if selected:
                logger.info("Universidad Mexico: programa seleccionado con teclado")
                return True
            await self.page.keyboard.press("Escape")
        except Exception as e:
            logger.debug(f"Universidad Mexico: fallback teclado para programa fallo: {e}")
        return False

    async def _universidad_mexico_program_control(self) -> Optional[dict]:
        try:
            return await self._scope().evaluate(
                """
                (root) => {
                    const norm = (value) => String(value || '').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0
                            && !el.disabled;
                    };
                    const scoreNode = (el) => {
                        if (!visible(el)) return null;
                        const box = el.getBoundingClientRect();
                        if (box.width < 120 || box.height < 24 || box.height > 110) return null;
                        const text = norm(el.textContent || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '');
                        const key = norm(`${el.className || ''} ${el.id || ''} ${el.getAttribute('role') || ''}`);
                        let score = 0;
                        if (text.includes('selecciona un programa')) score += 20;
                        if (text.includes('programa')) score += 8;
                        if (key.includes('select') || key.includes('dropdown') || key.includes('combobox')) score += 5;
                        if (box.width >= 180 && box.width <= 520 && box.height >= 28 && box.height <= 80) score += 4;
                        if (/maestria|licenciatura|doctorado|modalidad/.test(text) && !text.includes('programa')) score -= 8;
                        if (/nombre|correo|email|telefono|celular|privacidad/.test(text)) score -= 20;
                        if (score <= 0) return null;
                        return {
                            el,
                            score,
                            text: (el.textContent || '').trim().slice(0, 120),
                            x: box.left + box.width / 2,
                            y: box.top + box.height / 2,
                        };
                    };

                    const raw = Array.from(root.querySelectorAll('[role=combobox], [aria-haspopup], button, [class*=select], [class*=Select], [class*=dropdown], [class*=Dropdown], div, span'));
                    const candidates = raw
                        .map((el) => {
                            const clickable = el.closest('[role=combobox], [aria-haspopup], button, [class*=control], [class*=Control], [class*=select], [class*=Select], [class*=dropdown], [class*=Dropdown]') || el;
                            return scoreNode(clickable);
                        })
                        .filter(Boolean)
                        .sort((a, b) => b.score - a.score);

                    const best = candidates[0];
                    if (!best) return null;
                    return { x: best.x, y: best.y, text: best.text, score: best.score };
                }
                """
            )
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudo ubicar control custom de programa: {e}")
            return None

    async def _universidad_mexico_random_program_option(self, level: str) -> Optional[dict]:
        terms = [*self._level_preferences(level), self._program_query(level)]
        try:
            return await self.page.evaluate(
                """
                (terms) => {
                    const norm = (value) => String(value || '').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0;
                    };
                    const wanted = terms.map(norm).filter(Boolean);
                    const blocked = /selecciona|programa$|modalidad|maestria$|licenciatura$|doctorado$|nombre|correo|email|telefono|celular|privacidad|aviso|enviar|whatsapp/;
                    const nodes = Array.from(document.querySelectorAll('[role=option], li, button, div, span, p'))
                        .filter(visible)
                        .map((el) => {
                            const box = el.getBoundingClientRect();
                            const text = String(el.textContent || '').trim();
                            const normalized = norm(text);
                            let score = 0;
                            if (!normalized || normalized.length < 4 || normalized.length > 160) return null;
                            if (blocked.test(normalized)) return null;
                            if (box.width < 120 || box.height < 20 || box.height > 90) return null;
                            if (/licenciatura|maestria|doctorado|ingenieria|administracion|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria/.test(normalized)) score += 8;
                            if (wanted.some((term) => normalized.includes(term))) score += 3;
                            if (el.getAttribute('role') === 'option') score += 6;
                            if (/option|item|menu|list/.test(norm(el.className || ''))) score += 3;
                            if (score <= 0) return null;
                            return {
                                text,
                                score,
                                x: box.left + box.width / 2,
                                y: box.top + box.height / 2,
                            };
                        })
                        .filter(Boolean);

                    if (!nodes.length) return null;
                    nodes.sort((a, b) => b.score - a.score);
                    const bestScore = nodes[0].score;
                    const top = nodes.filter((item) => item.score >= bestScore - 2).slice(0, 12);
                    return top[Math.floor(Math.random() * top.length)];
                }
                """,
                terms,
            )
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudo elegir opcion custom de programa: {e}")
            return None

    async def _universidad_mexico_program_is_selected(self) -> bool:
        """
        Verifica si el programa ya está seleccionado en el formulario.

        IMPORTANTE: El SELECT nativo data[program] puede estar oculto con
        display:none por Choices.js. Esta función lo chequea aunque esté oculto,
        ya que es el valor real que se enviará al servidor.
        """
        try:
            return await self._scope().evaluate(
                """
                (root) => {
                    const norm = (v) => String(v || '').trim().toLowerCase()
                        .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const bad = /^(|--|selecciona|selecciona un programa|programa|choose|select)$/;
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const b = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden'
                            && b.width > 0 && b.height > 0 && !el.disabled;
                    };

                    // CHECK 1: SELECT nativo con name="program" o "data[program]"
                    // Aunque esté oculto visualmente (Choices.js lo oculta), si tiene
                    // valor válido → el submit enviará el dato correcto → OK.
                    for (const sel of ['select[name="program"]', 'select[name="data[program]"]']) {
                        const select = root.querySelector(sel);
                        if (select) {
                            const val = norm(select.value || '');
                            const txt = norm(select.options?.[select.selectedIndex]?.textContent || '');
                            if (val && !bad.test(val)) return true;
                            if (txt && !bad.test(txt)) return true;
                        }
                    }

                    // CHECK 2: Cualquier SELECT visible con opciones de programas
                    for (const select of Array.from(root.querySelectorAll('select')).filter(visible)) {
                        const key = norm(`${select.name || ''} ${select.id || ''} ${
                            Array.from(select.options || []).map(o => o.textContent).join(' ')
                        }`);
                        if (!/program|programa|carrera|licenciatura|maestria|doctorado/.test(key)) continue;
                        const val = norm(select.value || '');
                        const txt = norm(select.options?.[select.selectedIndex]?.textContent || '');
                        if ((val || txt) && !bad.test(val) && !bad.test(txt)) return true;
                    }

                    // CHECK 3: Custom dropdown muestra un programa (no placeholder)
                    const programKeywords = /ingenieria|administracion|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria|tecnologias|mercadotecnia|arquitectura|comunicacion|turismo/;
                    const customSelectors = [
                        '.choices__item--selectable:not(.choices__item--choice)',
                        '[aria-selected=true]',
                        '[class*=singleValue]',
                        '[class*=selected-value]',
                        '[class*=selectedValue]',
                    ];
                    for (const sel of customSelectors) {
                        for (const el of Array.from(root.querySelectorAll(sel)).filter(visible)) {
                            const text = norm(el.textContent || '');
                            if (text && !bad.test(text) && programKeywords.test(text)) return true;
                        }
                    }

                    return false;
                }
                """
            )
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudo validar programa seleccionado: {e}")
            return False

    # ------------------------------------------------------------------ #

    async def _fill_universidad_mexico_inputs(self, test_email: str) -> None:
        payload = {
            "name": self.country.fake_name,
            "email": test_email,
            "phone": self.country.fake_phone,
            "lastName": self.country.fake_name.split(" ")[-1] if self.country.fake_name else "Perez",
        }
        try:
            result = await self._scope().evaluate(
                """
                (root, payload) => {
                    const norm = (value) => String(value || '').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0
                            && !el.disabled
                            && el.type !== 'hidden';
                    };
                    const setValue = (el, value) => {
                        const proto = el.tagName === 'TEXTAREA'
                            ? window.HTMLTextAreaElement.prototype
                            : window.HTMLInputElement.prototype;
                        const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                        if (descriptor && descriptor.set) descriptor.set.call(el, value);
                        else el.value = value;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('blur', { bubbles: true }));
                    };
                    const labelText = (el) => {
                        const id = el.id ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent || '' : '';
                        const parentLabel = el.closest('label')?.textContent || '';
                        return `${id} ${parentLabel}`;
                    };
                    const completed = [];
                    for (const el of Array.from(root.querySelectorAll('input, textarea')).filter(visible)) {
                        const type = norm(el.type);
                        if (['checkbox', 'radio', 'submit', 'button', 'file', 'password'].includes(type)) continue;
                        if (String(el.value || '').trim()) continue;
                        const key = norm(`${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''} ${labelText(el)}`);
                        if (/search|buscar|utm|captcha|recaptcha/.test(key)) continue;

                        let value = '';
                        let reason = '';
                        if (type === 'email' || /email|correo/.test(key)) {
                            value = payload.email;
                            reason = 'email';
                        } else if (type === 'tel' || /phone|tel|telefono|celular|mobile|whatsapp/.test(key)) {
                            value = payload.phone;
                            reason = 'phone';
                        } else if (/apellido|last/.test(key)) {
                            value = payload.lastName;
                            reason = 'last_name';
                        } else if (/nombre|name|first/.test(key)) {
                            value = payload.name;
                            reason = 'name';
                        } else if (el.required) {
                            value = type === 'number' ? '1' : 'Prueba';
                            reason = 'required_fallback';
                        }

                        if (!value) continue;
                        setValue(el, value);
                        completed.push({ name: el.name || '', id: el.id || '', placeholder: el.placeholder || '', reason });
                    }
                    return completed;
                }
                """,
                payload,
            )
            logger.info(f"Universidad Mexico: inputs completados: {result}")
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudieron completar inputs dinamicos: {e}")

    async def _universidad_mexico_form_state(self) -> dict:
        try:
            return await self._scope().evaluate(
                """
                (root) => {
                    const norm = (value) => String(value || '').trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0
                            && !el.disabled
                            && el.type !== 'hidden';
                    };
                    const fields = Array.from(root.querySelectorAll('input, select, textarea')).filter(visible);
                    const state = {
                        has_name: false,
                        name: false,
                        has_email: false,
                        email: false,
                        has_phone: false,
                        phone: false,
                        has_program: false,
                        program: false,
                        has_checkbox: false,
                        checkbox_checked: true,
                        missing_required: [],
                    };
                    for (const el of fields) {
                        const type = norm(el.type);
                        const key = norm(`${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.getAttribute('aria-label') || ''}`);
                        const value = String(el.value || '').trim();
                        if (type === 'checkbox') {
                            state.has_checkbox = true;
                            if (/privacidad|politica|aviso|terminos|acepto/.test(key) || el.required) {
                                state.checkbox_checked = Boolean(el.checked);
                            }
                            if (el.required && !el.checked) state.missing_required.push(key || 'checkbox');
                            continue;
                        }
                        if (/email|correo/.test(key) || type === 'email') {
                            state.has_email = true;
                            state.email = Boolean(value);
                        }
                        if (/phone|tel|telefono|celular|mobile|whatsapp/.test(key) || type === 'tel') {
                            state.has_phone = true;
                            state.phone = Boolean(value);
                        }
                        if (/nombre|name|first/.test(key) && !/apellido|last/.test(key)) {
                            state.has_name = true;
                            state.name = Boolean(value);
                        }
                        if (/program|programa|carrera|interes|licenciatura|maestria|doctorado/.test(key)) {
                            state.has_program = true;
                            state.program = Boolean(value) && !/selecciona|select|choose/.test(norm(value));
                        }
                        if (el.required && !value) state.missing_required.push(key || el.tagName.toLowerCase());
                    }

                    // Chequeo adicional: SELECT nativo oculto por Choices.js
                    for (const sel of ['select[name="program"]', 'select[name="data[program]"]']) {
                        const nativeSelect = root.querySelector(sel);
                        if (nativeSelect) {
                            const val = String(nativeSelect.value || '').trim();
                            const bad = /selecciona|select|choose|^$/;
                            if (val && !bad.test(val.toLowerCase())) {
                                state.has_program = true;
                                state.program = true;
                                // Elimina de missing_required si estaba ahí por el SELECT oculto
                                state.missing_required = state.missing_required.filter(
                                    k => !/program|programa/.test(k)
                                );
                            }
                        }
                    }

                    const badProgram = /selecciona un programa|selecciona|programa$|choose|select/;
                    const programTextNodes = Array.from(root.querySelectorAll(
                        '[role=combobox], [aria-haspopup], [class*=select], [class*=Select], ' +
                        '[class*=dropdown], [class*=Dropdown], div, span'
                    ))
                        .filter(visible)
                        .map((el) => norm(el.textContent || el.getAttribute('aria-label') || ''))
                        .filter((text) => text.includes('programa') || badProgram.test(text)
                            || /ingenieria|administracion|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria/.test(text));

                    if (programTextNodes.length && !state.program) {
                        state.has_program = true;
                        state.program = !programTextNodes.some((text) => badProgram.test(text))
                            && programTextNodes.some((text) => /ingenieria|administracion|derecho|psicologia|educacion|marketing|finanzas|software|datos|negocios|salud|criminologia|contaduria/.test(text));
                    }
                    return state;
                }
                """
            )
        except Exception as e:
            logger.debug(f"Universidad Mexico: no se pudo leer estado dinamico: {e}")
            return {}

    async def _validate_universidad_mexico_submission(self, timeout_ms: int = 10000) -> bool:
        attempts = max(int(timeout_ms / 500), 1)
        for _ in range(attempts):
            status = await self._universidad_mexico_submission_status()
            if status.get("success"):
                logger.info(f"Universidad Mexico: envio confirmado en LP: {status}")
                return True
            if status.get("blocking_error"):
                logger.warning(f"Universidad Mexico: error visible despues de enviar: {status}")
                return False
            await self.page.wait_for_timeout(500)

        logger.info("Universidad Mexico: sin error visible despues de enviar; se continuara a InConcert")
        return True

    async def _universidad_mexico_submission_status(self) -> dict:
        try:
            return await self.page.evaluate(
                """
                () => {
                    const text = String(document.body?.innerText || '').toLowerCase();
                    const success = /gracias|thank you|registro exitoso|solicitud recibida|nos pondremos en contacto|datos enviados/.test(text);
                    const blockingError = /campo requerido|campos requeridos|obligatorio|ingresa un|introduce un|correo invalido|teléfono invalido|telefono invalido/.test(text);
                    return { success, blocking_error: blockingError };
                }
                """
            )
        except Exception:
            return {"success": False, "blocking_error": False}

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

        dynamic_select_done = await self._select_program_by_context(level, level_preferences)
        if dynamic_select_done:
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

    async def _select_program_by_context(self, level: str, level_preferences: list[str]) -> bool:
        try:
            result = await self._scope().evaluate(
                """
                (root, payload) => {
                    const { preferred } = payload;
                    const clean = (value) => String(value || '').trim();
                    const norm = (value) => clean(value).toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const box = el.getBoundingClientRect();
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && box.width > 0
                            && box.height > 0
                            && !el.disabled;
                    };
                    const bad = new Set(['', '-', '--', 'seleccionar', 'selecciona', 'select', 'choose']);
                    const labelText = (el) => {
                        const idLabel = el.id ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent || '' : '';
                        const parentLabel = el.closest('label')?.textContent || '';
                        return `${idLabel} ${parentLabel}`;
                    };
                    const optionsFor = (select) => Array.from(select.options || [])
                        .map((option, index) => ({
                            index,
                            text: clean(option.textContent),
                            value: clean(option.value),
                            disabled: option.disabled,
                        }))
                        .filter((option) => {
                            const text = norm(option.text);
                            const value = norm(option.value);
                            return option.index > 0 && !option.disabled && !bad.has(text) && !bad.has(value);
                        });
                    const pickOption = (select) => {
                        const options = optionsFor(select);
                        if (!options.length) return null;

                        for (const wantedRaw of preferred || []) {
                            const wanted = norm(wantedRaw);
                            if (!wanted) continue;
                            const exact = options.find((option) => norm(option.text) === wanted || norm(option.value) === wanted);
                            if (exact) return { ...exact, matched: true };
                            const partial = options.find((option) => {
                                const text = norm(option.text);
                                const value = norm(option.value);
                                return text.includes(wanted) || value.includes(wanted) || wanted.includes(text);
                            });
                            if (partial) return { ...partial, matched: true };
                        }
                        return null;
                    };

                    const candidates = Array.from(root.querySelectorAll('select'))
                        .filter(visible)
                        .map((select) => {
                            const optionText = optionsFor(select).map((option) => option.text).join(' ');
                            const key = norm(`${select.name || ''} ${select.id || ''} ${select.getAttribute('aria-label') || ''} ${labelText(select)} ${optionText}`);
                            const picked = pickOption(select);
                            let score = 0;
                            if (/program|programa|carrera|interes|interes academico|oferta|curso/.test(key)) score += 8;
                            if (/licenciatura|maestria|doctorado|bachillerato|bootcamp|diplomado/.test(key)) score += 5;
                            if (/modalidad|estado|pais|phone|telefono|nombre|correo|email/.test(key)) score -= 6;
                            if (picked?.matched) score += 10;
                            return { select, picked, score };
                        })
                        .filter((item) => item.picked && item.score > 0)
                        .sort((a, b) => b.score - a.score);

                    const target = candidates[0];
                    if (!target) return null;

                    target.select.selectedIndex = target.picked.index;
                    target.select.value = target.picked.value;
                    target.select.dispatchEvent(new Event('input', { bubbles: true }));
                    target.select.dispatchEvent(new Event('change', { bubbles: true }));
                    target.select.dispatchEvent(new Event('blur', { bubbles: true }));
                    return {
                        name: target.select.name || '',
                        id: target.select.id || '',
                        text: target.picked.text,
                        value: target.picked.value,
                        score: target.score,
                    };
                }
                """,
                {"preferred": [*level_preferences, self._program_query(level)]},
            )

            if result:
                logger.info(f"Programa seleccionado por contexto: {result}")
                await self.page.wait_for_timeout(1500)
                return True
        except Exception as e:
            logger.debug(f"No se pudo seleccionar programa por contexto: {e}")

        return False

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
                        first_name: pick("input#first_name, input[name='first_name'], input[name='name'], input[name*='nombre' i], input[id*='nombre' i]"),
                        email: pick("input#email, input[name='email'], input[type='email'], input[name*='correo' i], input[id*='correo' i]"),
                        phone: pick("input#phone, input[name='phone'], input[type='tel'], input[name*='telefono' i], input[id*='telefono' i], input[name*='celular' i], input[id*='celular' i], input[name*='mobile' i]"),
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