# ============================================================
# automation/form_filler.py
# Llena formularios de UTEL detectando campos dinámicamente
# El sitio usa React/Next.js — los campos se renderizan en el cliente
# Por eso usamos espera activa y selectores por texto visible
# ============================================================

import asyncio
import random
from typing import Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from loguru import logger

from config.models import LeadRow
from config.countries import Country, get_level_name, infer_level_from_url


class FormFiller:
    """
    Llena el formulario de una landing page de UTEL.
    Usa estrategia de detección dinámica porque el sitio es React/Next.js
    — los campos aparecen después de que la página termina de renderizar.
    """

    def __init__(self, page: Page, country: Country):
        self.page = page
        self.country = country
        logger.debug(f"📝 FormFiller creado para {country.id}")

    async def fill(self, lead: LeadRow) -> bool:
        """Método principal — abre la LP, detecta el tipo de form y lo llena."""
        try:
            logger.info(f"🌐 Abriendo LP: {lead.landing_url}")

            # Navegamos y esperamos que React termine de renderizar
            await self.page.goto(lead.landing_url, wait_until="networkidle", timeout=45000)
            await self.page.wait_for_timeout(3000)

            form_type = lead.form_type.strip().lower()
            logger.info(f"📋 Tipo: {form_type}")

            if form_type == "lateral":
                await self._handle_lateral()
            elif form_type == "footer":
                await self._handle_footer()
            elif form_type in ["tarjeta", "targeta"]:
                await self._handle_tarjeta(lead)
            else:
                logger.info("📋 Form LP — formulario directo")

            # Nivel correcto según país
            level = get_level_name(self.country, lead.nivel or "")
            if not level:
                level = infer_level_from_url(lead.landing_url) or ""
            logger.info(f"🎓 Nivel: '{level}'")

            return await self._fill_all_fields(lead.test_email, level)

        except PlaywrightTimeoutError:
            logger.error(f"❌ Timeout: {lead.landing_url}")
            return False
        except Exception as e:
            logger.error(f"❌ Error en fill(): {e}")
            return False

    async def _handle_lateral(self) -> None:
        """Tipo Lateral: click en botón 'Solicitar información' para desplegar form."""
        logger.info("🔲 Buscando botón lateral...")
        try:
            for name in ["Solicitar información", "Solicitar info", "Contáctanos", "Más información"]:
                btn = self.page.get_by_role("button", name=name)
                if await btn.count() == 0:
                    btn = self.page.get_by_role("link", name=name)
                if await btn.count() > 0:
                    await btn.first.click()
                    logger.info(f"✅ Botón lateral '{name}' clickeado")
                    await self.page.wait_for_timeout(2000)
                    return
            logger.warning("⚠️ Botón lateral no encontrado")
        except Exception as e:
            logger.warning(f"⚠️ Error lateral: {e}")

    async def _handle_footer(self) -> None:
        """Tipo Footer: scroll hasta el formulario al pie de la página."""
        logger.info("⬇️ Scroll hacia footer...")
        for _ in range(8):
            await self.page.evaluate("window.scrollBy(0, 400)")
            await self.page.wait_for_timeout(400)
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await self.page.wait_for_timeout(2000)
        logger.info("✅ Footer alcanzado")

    async def _handle_tarjeta(self, lead: LeadRow) -> None:
        """Tipo Tarjeta: URL específica → form visible. URL genérica → usar lupa."""
        url = lead.landing_url.lower()
        specific = [
            "diplomado-en-", "maestria-en-", "maestría-en-", "licenciatura-en-",
            "doctorado-en-", "ingenieria-en-", "ingeniería-en-", "criminologia",
            "ciberseguridad", "administracion", "derecho", "psicologia",
            "project-management", "gestion", "gestión", "contaduria",
        ]
        if any(s in url for s in specific):
            logger.info("✅ Tarjeta A: URL específica")
        else:
            logger.info("🔍 Tarjeta B: URL genérica — usando lupa")
            await self._search_with_magnifier(lead)

    async def _search_with_magnifier(self, lead: LeadRow) -> None:
        """Busca programa con la lupa y selecciona el primer resultado."""
        level = get_level_name(self.country, lead.nivel or "Licenciatura")
        words = {
            "Maestría": "maestria", "Magister": "magister",
            "Licenciatura": "licenciatura", "Carrera": "carrera",
            "Doctorado": "doctorado", "Bachelor": "bachelor",
            "Bootcamp": "bootcamp", "Diplomado": "diplomado",
        }
        word = words.get(level, level.lower() if level else "licenciatura")
        try:
            # Click en lupa
            for name in ["Buscar", "Search", "buscar"]:
                btn = self.page.get_by_role("button", name=name)
                if await btn.count() > 0:
                    await btn.first.click()
                    await self.page.wait_for_timeout(1000)
                    break

            # Input de búsqueda
            inp = self.page.get_by_placeholder("Buscar programa")
            if await inp.count() == 0:
                inp = self.page.get_by_role("searchbox")
            if await inp.count() == 0:
                inp = self.page.locator("input[type='search']:visible, input[type='text']:visible").first

            await inp.click()
            await inp.type(word, delay=100)
            await self.page.wait_for_timeout(2000)

            # Primer resultado
            results = self.page.locator("ul li a, [class*='result'] a, [class*='suggestion'] a")
            if await results.count() > 0:
                idx = random.randint(0, min(await results.count() - 1, 2))
                text = await results.nth(idx).inner_text()
                logger.info(f"✅ Seleccionado: '{text.strip()}'")
                await results.nth(idx).click()
                await self.page.wait_for_load_state("networkidle")
                await self.page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"⚠️ Error lupa: {e}")

    async def _fill_all_fields(self, test_email: str, level: str) -> bool:
        """Detecta y llena todos los campos del formulario visible."""
        logger.info(f"✍️ Llenando campos | nivel='{level}' | email='{test_email}'")

        # Esperamos inputs visibles
        try:
            await self.page.wait_for_selector("input:visible, select:visible", timeout=15000)
        except Exception:
            logger.warning("⚠️ No se detectaron inputs en 15s")

        await self._try_select_level(level)
        await self.page.wait_for_timeout(800)
        await self._try_select_program()
        await self.page.wait_for_timeout(800)
        await self._try_fill_name()
        await self.page.wait_for_timeout(500)
        await self._try_fill_email(test_email)
        await self.page.wait_for_timeout(500)
        await self._try_fill_phone()
        await self.page.wait_for_timeout(500)
        await self._try_select_province()
        await self._try_fill_birthdate()
        await self._try_check_privacy()
        await self.page.wait_for_timeout(500)
        return await self._try_submit()

    async def _try_select_level(self, level: str) -> None:
        """Selecciona el nivel en el primer select del formulario."""
        if not level:
            return
        try:
            selects = self.page.locator("select:visible")
            count = await selects.count()
            logger.debug(f"🔎 Selects visibles: {count}")

            for i in range(count):
                sel = selects.nth(i)
                options = await sel.locator("option").all_inner_texts()
                logger.debug(f"   Select {i} opciones: {options[:8]}")
                for opt in options:
                    if level.lower() in opt.lower() or opt.lower() in level.lower():
                        await sel.select_option(label=opt)
                        logger.info(f"✅ Nivel '{opt}' en select {i}")
                        await self.page.wait_for_timeout(800)
                        return
        except Exception as e:
            logger.debug(f"ℹ️ select nivel: {e}")

    async def _try_select_program(self) -> None:
        """Selecciona cualquier programa en el segundo select."""
        try:
            selects = self.page.locator("select:visible")
            count = await selects.count()
            for i in range(count):
                sel = selects.nth(i)
                options = await sel.locator("option").all_inner_texts()
                real = [o for o in options if o.strip() and o.strip() not in ["-", "--", "Seleccionar", "Selecciona"]]
                if len(real) > 1:
                    chosen = random.choice(real[:5])
                    try:
                        await sel.select_option(label=chosen)
                        logger.info(f"✅ Programa '{chosen}'")
                        await self.page.wait_for_timeout(800)
                        return
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"ℹ️ select programa: {e}")

    async def _try_fill_name(self) -> None:
        """Llena el campo de nombre."""
        for ph in ["Nombre", "nombre", "Name", "Tu nombre", "Nombres"]:
            inp = self.page.get_by_placeholder(ph)
            if await inp.count() > 0:
                await inp.first.click()
                await inp.first.clear()
                await inp.first.type(self.country.fake_name, delay=80)
                logger.info(f"✅ Nombre: '{self.country.fake_name}'")
                return
        logger.debug("ℹ️ Campo nombre no encontrado")

    async def _try_fill_email(self, test_email: str) -> None:
        """Llena el campo de correo electrónico."""
        for ph in ["Correo electrónico", "correo electrónico", "Correo", "Email", "email", "tu@correo.com"]:
            inp = self.page.get_by_placeholder(ph)
            if await inp.count() > 0:
                await inp.first.click()
                await inp.first.clear()
                await inp.first.type(test_email, delay=80)
                logger.info(f"✅ Correo: '{test_email}'")
                return
        # Por type email
        inp = self.page.locator("input[type='email']:visible")
        if await inp.count() > 0:
            await inp.first.click()
            await inp.first.clear()
            await inp.first.type(test_email, delay=80)
            logger.info(f"✅ Correo (type=email): '{test_email}'")
            return
        logger.debug("ℹ️ Campo correo no encontrado")

    async def _try_fill_phone(self) -> None:
        """Llena el campo de teléfono."""
        for ph in ["Teléfono", "teléfono", "Phone", "Celular", "celular", "Móvil", "móvil"]:
            inp = self.page.get_by_placeholder(ph)
            if await inp.count() > 0:
                await inp.first.click()
                await inp.first.clear()
                await inp.first.type(self.country.fake_phone, delay=80)
                logger.info(f"✅ Teléfono: '{self.country.fake_phone}'")
                return
        inp = self.page.locator("input[type='tel']:visible")
        if await inp.count() > 0:
            await inp.first.click()
            await inp.first.clear()
            await inp.first.type(self.country.fake_phone, delay=80)
            logger.info(f"✅ Teléfono (type=tel): '{self.country.fake_phone}'")
            return
        logger.debug("ℹ️ Campo teléfono no encontrado")

    async def _try_select_province(self) -> None:
        """Selecciona la provincia si existe."""
        if not self.country.fake_province:
            return
        try:
            for ph in ["Selecciona una provincia", "Provincia", "Estado", "Region", "Región"]:
                sel = self.page.get_by_role("combobox", name=ph)
                if await sel.count() == 0:
                    sel = self.page.get_by_placeholder(ph)
                if await sel.count() > 0:
                    options = await sel.locator("option").all_inner_texts()
                    real = [o for o in options if o.strip() and o.strip() not in ["-", "--"]]
                    if real:
                        await sel.select_option(label=real[0])
                        logger.info(f"✅ Provincia: '{real[0]}'")
                        return
        except Exception as e:
            logger.debug(f"ℹ️ provincia: {e}")

    async def _try_fill_birthdate(self) -> None:
        """Llena fecha de nacimiento si existe."""
        try:
            inp = self.page.locator("input[type='date']:visible")
            if await inp.count() > 0:
                await inp.first.fill("1990-01-01")
                logger.info("✅ Fecha nacimiento: 01/01/1990")
                return
            for ph in ["Fecha de nacimiento", "fecha", "Nacimiento"]:
                inp = self.page.get_by_placeholder(ph)
                if await inp.count() > 0:
                    await inp.first.type("01/01/1990", delay=80)
                    logger.info("✅ Fecha nacimiento por placeholder")
                    return
        except Exception as e:
            logger.debug(f"ℹ️ birthdate: {e}")

    async def _try_check_privacy(self) -> None:
        """Marca el checkbox de política de privacidad."""
        try:
            checkboxes = self.page.locator("input[type='checkbox']:visible")
            count = await checkboxes.count()
            for i in range(count):
                cb = checkboxes.nth(i)
                if not await cb.is_checked():
                    await cb.click()
                    logger.info(f"✅ Checkbox privacidad marcado")
                    return
        except Exception as e:
            logger.debug(f"ℹ️ checkbox: {e}")

    async def _try_submit(self) -> bool:
        """Click en botón de envío."""
        logger.info("📤 Enviando formulario...")
        try:
            for text in ["Calcula tu beca", "Enviar información", "Solicitar información",
                         "Enviar", "Registrarme", "Continuar", "Más información", "Enviar"]:
                btn = self.page.get_by_role("button", name=text)
                if await btn.count() > 0:
                    await self.page.wait_for_timeout(500)
                    await btn.first.click()
                    await self.page.wait_for_timeout(3000)
                    logger.info(f"✅ Submit con botón: '{text}'")
                    return True

            sub = self.page.locator("button[type='submit']:visible")
            if await sub.count() > 0:
                await sub.first.click()
                await self.page.wait_for_timeout(3000)
                logger.info("✅ Submit por type=submit")
                return True

            logger.warning("⚠️ Botón submit no encontrado")
            return False
        except Exception as e:
            logger.error(f"❌ Submit error: {e}")
            return False