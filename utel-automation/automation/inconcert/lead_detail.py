"""LeadDetailOpener — abre el panel de gestión de un lead en InConcert."""

import re
from playwright.async_api import Page
from loguru import logger
from automation.browser import BrowserManager


class LeadDetailOpener:
    """Abre el detalle de gestión de un lead encontrado (menú 3 puntos → Gestionar)."""

    def __init__(self, page: Page):
        self.page = page

    async def open(self) -> bool:
        try:
            logger.info("Abriendo panel de gestion del lead...")

            menu_opened = await self._open_actions_menu()
            if not menu_opened:
                logger.error("No se pudo abrir menu de 3 puntos")
                return False

            gestionar_clicked = await self._click_gestionar()
            if not gestionar_clicked:
                logger.error("No se encontro opcion 'Gestionar'")
                return False

            await self.page.wait_for_load_state("domcontentloaded")

            try:
                await self.page.get_by_text(
                    re.compile("Gestionar Contacto|Actividad", re.IGNORECASE)
                ).wait_for(state="visible", timeout=10000)
                logger.info("Panel de gestion abierto")
            except Exception:
                logger.warning("Panel podria no haberse abierto; se continua con captura")

            await BrowserManager.human_delay(1500, 2500)
            return True

        except Exception as e:
            logger.error(f"Error abriendo detalle: {e}")
            return False

    async def _open_actions_menu(self) -> bool:
        """Busca fila de resultado y abre menú de 3 puntos."""
        for row_selector in ["table tbody tr", ".contact-row", ".result-row", "[class*='contact-item']", "[role='row']"]:
            rows = self.page.locator(row_selector)
            try:
                count = await rows.count()
            except Exception:
                continue
            for i in range(count):
                row = rows.nth(i)
                try:
                    if await row.is_visible() and await self._click_actions_in_row(row):
                        return True
                except Exception:
                    continue
        return await self._click_actions_by_position()

    async def _click_actions_in_row(self, row) -> bool:
        for selector in [
            "button[aria-haspopup='menu']", "button[aria-label*='opciones' i]",
            "button[aria-label*='acciones' i]", "button[title*='opciones' i]",
            "button[title*='acciones' i]", "button:has(svg)", "button", "[role='button']",
        ]:
            items = row.locator(selector)
            try:
                count = await items.count()
            except Exception:
                continue
            candidates = []
            for i in range(count):
                item = items.nth(i)
                try:
                    if not await item.is_visible():
                        continue
                    box = await item.bounding_box()
                    if box:
                        candidates.append((box["x"], item))
                except Exception:
                    continue

            for _, item in sorted(candidates, key=lambda v: v[0], reverse=True):
                try:
                    await item.scroll_into_view_if_needed(timeout=3000)
                    await BrowserManager.human_delay(250, 500)
                    await item.click(force=True, timeout=4000)
                    await BrowserManager.human_delay(700, 1000)
                    if await self._gestion_menu_visible():
                        return True
                except Exception:
                    continue

        try:
            box = await row.bounding_box()
            if box:
                await self.page.mouse.click(box["x"] + box["width"] - 18, box["y"] + box["height"] / 2)
                await BrowserManager.human_delay(700, 1000)
                return await self._gestion_menu_visible()
        except Exception:
            pass
        return False

    async def _click_actions_by_position(self) -> bool:
        try:
            result = await self.page.evaluate("""
                () => {
                    const visible = (el) => { const s=window.getComputedStyle(el); const r=el.getBoundingClientRect(); return s.display!=='none' && s.visibility!=='hidden' && r.width>0 && r.height>0; };
                    const rows = Array.from(document.querySelectorAll('table tbody tr,.contact-row,.result-row,[class*=contact-item],[role=row]')).filter(visible);
                    const row = rows.find(r => r.getBoundingClientRect().height > 20);
                    if (!row) return false;
                    const box = row.getBoundingClientRect();
                    const target = document.elementFromPoint(box.right - 18, box.top + box.height / 2);
                    if (target) { target.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window})); return true; }
                    return false;
                }
            """)
            if result:
                await BrowserManager.human_delay(700, 1000)
                return await self._gestion_menu_visible()
        except Exception:
            pass
        return False

    async def _gestion_menu_visible(self) -> bool:
        try:
            g = self.page.get_by_text("Gestionar", exact=True)
            count = await g.count()
            for i in range(count):
                if await g.nth(i).is_visible():
                    return True
        except Exception:
            pass
        return False

    async def _click_gestionar(self) -> bool:
        for selector in [
            "[role='menuitem']:has-text('Gestionar')", ".dropdown-menu a:has-text('Gestionar')",
            ".dropdown-menu button:has-text('Gestionar')", "a:has-text('Gestionar')",
            "button:has-text('Gestionar')", "li:has-text('Gestionar')",
            "div:has-text('Gestionar')", "span:has-text('Gestionar')",
        ]:
            opt = self.page.locator(selector)
            try:
                count = await opt.count()
            except Exception:
                continue
            for i in range(count):
                item = opt.nth(i)
                try:
                    if await item.is_visible():
                        await item.click(force=True, timeout=4000)
                        logger.info("Click en 'Gestionar'")
                        return True
                except Exception:
                    continue
        return False
