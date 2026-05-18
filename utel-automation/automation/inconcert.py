# ============================================================
# automation/inconcert.py
# Automatiza el flujo completo dentro del CRM InConcert:
# 1. Login con credenciales
# 2. Búsqueda del lead por correo con reintentos
# 3. Apertura del panel de gestión
# 4. Expansión de secciones para la captura
# Equivalente a un @Service complejo en Spring Boot
# ============================================================

import asyncio                                          # Para esperas asíncronas
from typing import Optional                             # Para tipos opcionales
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from loguru import logger                               # Para logs

from config.settings import settings                    # Configuración del sistema
from config.countries import Country                    # Datos del país
from automation.browser import BrowserManager           # Para delays humanos


class InConcertScraper:
    """
    Automatiza el flujo dentro del CRM InConcert.
    Equivalente a un @Service en Spring Boot que contiene
    la lógica de negocio para interactuar con el CRM.

    Recibe inyectadas la página de Playwright y el país.
    """

    def __init__(self, page: Page, country: Country):
        """
        Constructor con inyección de dependencias.
        Equivalente a @Autowired en Spring Boot.

        Parámetros:
            page: pestaña del navegador para InConcert
            country: configuración del país (URL de InConcert)
        """
        # La pestaña del navegador donde operamos InConcert
        self.page = page

        # Configuración del país — tiene la URL del CRM
        self.country = country

        # Flag para cancelar el proceso si el usuario presiona "Detener"
        self._cancelled = False

        logger.debug(f"🔧 InConcertScraper creado para {country.id}")

    async def login(self) -> bool:
        """
        Navega a InConcert y hace login con las credenciales del .env.
        Las mismas credenciales sirven para todos los países.

        Retorna:
            True si el login fue exitoso
            False si hubo algún problema
        """
        try:
            # Construimos la URL de contactos directamente
            # Así llegamos directo a la sección de búsqueda
            # Construimos la URL correcta de contactos
            # inconcert_url termina en /mas/home
            # La URL de contactos es /mas/contact/people
            base = self.country.inconcert_url.rstrip("/")
            if base.endswith("/home"):
                base = base[:-5]  # Quitamos "/home"
            contacts_url = base + "/contact/people"

            logger.info(f"🔐 Navegando a InConcert: {contacts_url}")

            # Navegamos a la URL del CRM
            await self.page.goto(
                contacts_url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            # Pausa humana después de cargar
            await BrowserManager.human_delay(1500, 2500)

            # Verificamos si ya estamos logueados (puede haber sesión activa)
            # Si vemos el título "Contactos", ya estamos dentro
            if await self._is_logged_in():
                logger.info("✅ Sesión activa detectada — ya estamos dentro")
                return True

            # Si no estamos logueados, buscamos el formulario de login
            logger.info("🔑 Realizando login...")

            # Selectores posibles para el campo de usuario
            user_selectors = [
                "input[type='email']",
                "input[name='username']",
                "input[name='email']",
                "input[name='user']",
                "input[placeholder*='usuario']",
                "input[placeholder*='email']",
                "input[id*='user']",
                "input[id*='email']",
            ]

            # Llenamos el campo de usuario
            for selector in user_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        await self.page.keyboard.type(
                            settings.inconcert_user,
                            delay=80
                        )
                        logger.info("✅ Usuario ingresado")
                        break
                except Exception:
                    continue

            await BrowserManager.human_delay(300, 600)

            # Selectores posibles para el campo de contraseña
            password_selectors = [
                "input[type='password']",
                "input[name='password']",
                "input[name='pass']",
                "input[id*='password']",
                "input[id*='pass']",
            ]

            # Llenamos el campo de contraseña
            for selector in password_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        await self.page.keyboard.type(
                            settings.inconcert_password,
                            delay=80
                        )
                        logger.info("✅ Contraseña ingresada")
                        break
                except Exception:
                    continue

            await BrowserManager.human_delay(500, 1000)

            # Hacemos click en el botón de login
            login_button_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Ingresar')",
                "button:has-text('Login')",
                "button:has-text('Entrar')",
                "button:has-text('Iniciar sesión')",
                ".btn-login",
                ".login-btn",
            ]

            for selector in login_button_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        logger.info("✅ Click en botón de login")
                        break
                except Exception:
                    continue

            # Esperamos a que cargue el dashboard después del login
            await self.page.wait_for_load_state("networkidle", timeout=15000)
            await BrowserManager.human_delay(2000, 3000)

            # Verificamos si el login fue exitoso
            if await self._is_logged_in():
                logger.info("✅ Login exitoso en InConcert")
                return True
            else:
                logger.error("❌ Login fallido — verifica credenciales en .env")
                return False

        except Exception as e:
            logger.error(f"❌ Error en login de InConcert: {e}")
            return False

    async def _is_logged_in(self) -> bool:
        """
        Verifica si ya estamos logueados en InConcert.
        Busca elementos que solo existen cuando estamos dentro del CRM.
        """
        try:
            # Buscamos elementos del dashboard de InConcert
            # Estos solo aparecen cuando el usuario está autenticado
            dashboard_indicators = [
                ".mas-sidebar",           # Barra lateral del CRM
                "[class*='sidebar']",     # Cualquier sidebar
                ".contact-list",          # Lista de contactos
                "h1:has-text('Contactos')",  # Título de la sección
                "[data-testid='contacts']",
            ]

            for selector in dashboard_indicators:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        return True
                except Exception:
                    continue

            return False

        except Exception:
            return False

    async def search_lead(self, email: str) -> bool:
        """
        Busca el lead por correo electrónico en InConcert.
        Reintenta cada 30 segundos hasta encontrarlo o agotar el tiempo.

        Sistema de reintentos:
        - Máximo 10 intentos
        - 30 segundos entre cada intento
        - Total: hasta 5 minutos de espera

        Parámetros:
            email: correo de prueba a buscar (ej: test190326N001@testUtel.com)

        Retorna:
            True si el lead apareció
            False si pasaron 5 minutos sin aparecer (timeout)
        """
        # Calculamos el número máximo de intentos
        max_attempts = settings.lead_timeout_seconds // settings.lead_retry_interval_seconds
        # Nos aseguramos de tener al menos 1 intento
        max_attempts = max(max_attempts, 1)

        logger.info(f"🔍 Buscando lead: {email}")
        logger.info(f"⏱️  Máximo {max_attempts} intentos cada {settings.lead_retry_interval_seconds}s")

        for attempt in range(1, max_attempts + 1):

            # Si el usuario canceló el proceso, salimos
            if self._cancelled:
                logger.info("🛑 Búsqueda cancelada por el usuario")
                return False

            logger.info(f"🔄 Intento {attempt}/{max_attempts} buscando: {email}")

            # Intentamos la búsqueda en este intento
            found = await self._perform_search(email)

            if found:
                logger.success(f"✅ Lead encontrado en intento {attempt}: {email}")
                return True

            # Si no encontramos el lead y no es el último intento, esperamos
            if attempt < max_attempts:
                logger.info(f"⏳ Lead no encontrado — esperando {settings.lead_retry_interval_seconds}s...")
                await asyncio.sleep(settings.lead_retry_interval_seconds)

        # Si llegamos aquí, se agotaron los intentos
        logger.warning(f"❌ TIMEOUT — Lead no llegó en {settings.lead_timeout_seconds}s: {email}")
        return False

    async def _perform_search(self, email: str) -> bool:
        """
        Ejecuta una búsqueda del lead en la sección de Contactos.
        Se llama en cada reintento de search_lead().

        Proceso:
        1. Asegurarse de estar en la sección Contactos
        2. Seleccionar filtro "Email"
        3. Escribir el correo
        4. Hacer click en la lupa
        5. Verificar si apareció un resultado

        Retorna:
            True si encontró el lead
            False si no apareció
        """
        try:
            # Verificamos que estemos en la sección correcta de contactos
            current_url = self.page.url
            if "contact/people" not in current_url:
                # Construimos la URL correcta quitando /home y agregando /contact/people
                base = self.country.inconcert_url.rstrip("/")
                if base.endswith("/home"):
                    base = base[:-5]  # Quitamos "/home"
                contacts_url = base + "/contact/people"
                await self.page.goto(contacts_url, wait_until="domcontentloaded")
                await BrowserManager.human_delay(1500, 2000)

            # Recargamos la página para limpiar resultados anteriores
            await self.page.reload(wait_until="domcontentloaded")
            await BrowserManager.human_delay(1000, 1500)

            filter_ok = await self._select_email_filter()
            if not filter_ok:
                logger.warning("⚠️  No se pudo confirmar filtro Email; se intentará buscar de todas formas")

            search_input = await self._find_search_input()
            if not search_input:
                logger.warning("⚠️  No se encontró campo de búsqueda")
                return False

            # Limpiamos el campo y escribimos el email
            await search_input.click()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Delete")
            await self.page.keyboard.type(email, delay=80)

            await BrowserManager.human_delay(300, 600)

            # Enter suele ejecutar la busqueda en este componente.
            await self.page.keyboard.press("Enter")
            logger.debug("✅ Enter ejecutado en campo de búsqueda")
            await BrowserManager.human_delay(1200, 1600)

            # Fallback: click en lupa/boton asociado al mismo bloque del input.
            await self._click_search_button_near_input(search_input)

            # Esperamos a que carguen los resultados
            await BrowserManager.human_delay(2000, 3000)

            # Verificamos si apareció algún resultado
            return await self._has_results()

        except Exception as e:
            logger.error(f"❌ Error en búsqueda: {e}")
            return False

    async def _select_email_filter(self) -> bool:
        """Selecciona el filtro Email en InConcert, evitando dejar Nombre activo."""
        # Flujo real del UI: el filtro es un dropdown custom que muestra "Nombre".
        # Hay que abrirlo y elegir "Email" antes de escribir el lead.
        try:
            opened = await self._open_basic_search_filter_dropdown()
            if opened:
                email_option = self.page.get_by_text("Email", exact=True)
                if await email_option.count() > 0:
                    await email_option.first.click(force=True)
                    await BrowserManager.human_delay(500, 800)
                    if await self._basic_filter_shows_email():
                        logger.debug("✅ Filtro Email seleccionado desde dropdown Nombre")
                        return True
        except Exception as e:
            logger.debug(f"No se pudo seleccionar Email desde dropdown Nombre: {e}")

        try:
            selected = await self.page.evaluate(
                """
                () => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 0
                            && r.height > 0
                            && !el.disabled;
                    };

                    const selects = Array.from(document.querySelectorAll('select')).filter(visible);
                    for (const select of selects) {
                        const options = Array.from(select.options || []);
                        const emailOption = options.find((option) =>
                            String(option.textContent || option.value || '').trim().toLowerCase() === 'email'
                        );
                        if (!emailOption) continue;

                        select.value = emailOption.value;
                        select.dispatchEvent(new Event('input', { bubbles: true }));
                        select.dispatchEvent(new Event('change', { bubbles: true }));
                        select.dispatchEvent(new Event('blur', { bubbles: true }));
                        return true;
                    }
                    return false;
                }
                """
            )
            if selected:
                logger.debug("✅ Filtro Email seleccionado por select nativo")
                await BrowserManager.human_delay(500, 800)
                return True
        except Exception:
            pass

        # Fallback para dropdown custom: abrir combobox y elegir texto Email.
        try:
            combo_candidates = self.page.locator(
                "[role='combobox']:visible, [class*='select']:visible, [class*='dropdown']:visible"
            )
            count = await combo_candidates.count()
            for i in range(count):
                combo = combo_candidates.nth(i)
                try:
                    text = (await combo.inner_text(timeout=1000)).lower()
                    if "nombre" in text or "email" in text or "correo" in text:
                        await combo.click(force=True)
                        await BrowserManager.human_delay(300, 500)
                        option = self.page.get_by_text("Email", exact=True)
                        if await option.count() > 0:
                            await option.first.click(force=True)
                            logger.debug("✅ Filtro Email seleccionado por dropdown custom")
                            return True
                except Exception:
                    continue
        except Exception:
            pass

        return False

    async def _open_basic_search_filter_dropdown(self) -> bool:
        """Abre el dropdown de Busqueda Basica que por defecto muestra Nombre."""
        candidates = [
            self.page.locator(".busqueda-basica button:has-text('Nombre')"),
            self.page.locator("button:has-text('Nombre')"),
            self.page.get_by_text("Nombre", exact=True),
        ]

        for candidate in candidates:
            count = await candidate.count()
            for i in range(count):
                item = candidate.nth(i)
                try:
                    if await item.is_visible():
                        await item.click(force=True)
                        await BrowserManager.human_delay(300, 500)
                        if await self.page.get_by_text("Email", exact=True).count() > 0:
                            logger.debug("✅ Dropdown de filtro basico abierto desde Nombre")
                            return True
                except Exception:
                    continue

        # Fallback por DOM: click al elemento visible cuyo texto sea exactamente Nombre.
        try:
            clicked = await self.page.evaluate(
                """
                () => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 0
                            && r.height > 0
                            && !el.disabled;
                    };

                    const items = Array.from(document.querySelectorAll('button, [role=button], span, div'))
                        .filter((el) => visible(el) && String(el.textContent || '').trim() === 'Nombre');

                    if (items[0]) {
                        items[0].click();
                        return true;
                    }
                    return false;
                }
                """
            )
            if clicked:
                await BrowserManager.human_delay(300, 500)
                return await self.page.get_by_text("Email", exact=True).count() > 0
        except Exception:
            pass

        return False

    async def _basic_filter_shows_email(self) -> bool:
        """Confirma que el filtro visible de busqueda basica quedo en Email."""
        try:
            return await self.page.evaluate(
                """
                () => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 0
                            && r.height > 0;
                    };

                    const buttons = Array.from(document.querySelectorAll('button, [role=button]'))
                        .filter(visible)
                        .map((el) => String(el.textContent || '').trim());

                    return buttons.some((text) => text === 'Email');
                }
                """
            )
        except Exception:
            return False

    async def _find_search_input(self):
        """Encuentra el input visible donde se escribe el correo a buscar."""
        search_input_selectors = [
            "input.search-input",
            ".busqueda-basica input[type='text']",
            "input[placeholder*='buscar' i]",
            ".search-field input",
            "[class*='search'] input[type='text']",
            "input[type='text']:visible",
        ]

        for selector in search_input_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    if await element.is_visible():
                        return element
            except Exception:
                continue
        return None

    async def _click_search_button_near_input(self, search_input) -> None:
        """Hace click en la lupa asociada al input; si no la encuentra, no falla."""
        try:
            clicked = await search_input.evaluate(
                """
                (input) => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 0
                            && r.height > 0
                            && !el.disabled;
                    };

                    const root = input.closest('form, .busqueda-basica, [class*=search], [class*=Search]')
                        || input.parentElement
                        || document;

                    const buttons = Array.from(root.querySelectorAll(
                        "button, [role='button'], .icon-search, [class*='search']"
                    )).filter((el) => el !== input && visible(el));

                    const inputBox = input.getBoundingClientRect();
                    buttons.sort((a, b) => {
                        const ar = a.getBoundingClientRect();
                        const br = b.getBoundingClientRect();
                        const ad = Math.abs(ar.left - inputBox.right) + Math.abs(ar.top - inputBox.top);
                        const bd = Math.abs(br.left - inputBox.right) + Math.abs(br.top - inputBox.top);
                        return ad - bd;
                    });

                    if (buttons[0]) {
                        buttons[0].click();
                        return true;
                    }
                    return false;
                }
                """
            )
            if clicked:
                logger.debug("✅ Click en lupa/botón cercano al campo de búsqueda")
        except Exception as e:
            logger.debug(f"No se pudo hacer click en lupa cercana: {e}")

    async def _has_results(self) -> bool:
        """
        Verifica si la búsqueda retornó algún resultado.
        InConcert muestra "De 0 resultados totales" cuando no hay resultados
        y "De 1 resultados totales" cuando sí hay.

        Retorna:
            True si hay al menos 1 resultado
            False si no hay resultados
        """
        try:
            # Buscamos el texto que indica el número de resultados
            page_content = await self.page.content()

            # Si el texto dice "0 resultados", no hay lead todavía
            if "De 0 resultados" in page_content or "0 resultados totales" in page_content:
                logger.debug("📭 0 resultados — lead aún no llegó")
                return False

            # Si hay una fila en la tabla de resultados, el lead llegó
            result_row_selectors = [
                "table tbody tr",
                ".contact-row",
                ".result-row",
                "[class*='contact-item']",
            ]

            for selector in result_row_selectors:
                try:
                    rows = await self.page.query_selector_all(selector)
                    if rows and len(rows) > 0:
                        logger.debug(f"📬 {len(rows)} resultado(s) encontrado(s)")
                        return True
                except Exception:
                    continue

            return False

        except Exception as e:
            logger.error(f"❌ Error verificando resultados: {e}")
            return False

    async def open_lead_detail(self) -> bool:
        """
        Abre el panel de gestion del lead encontrado.
        Hace click en los 3 puntos al lado derecho del lead y selecciona Gestionar.
        """
        try:
            logger.info("Abriendo panel de gestion del lead...")

            menu_opened = await self._open_result_row_actions_menu()
            if not menu_opened:
                logger.error("No se pudo abrir el menu de 3 puntos del lead")
                return False

            gestionar_clicked = await self._click_gestionar_option()
            if not gestionar_clicked:
                logger.error("No se encontro la opcion 'Gestionar' en el menu")
                return False

            await self.page.wait_for_load_state("domcontentloaded")
            await BrowserManager.human_delay(2000, 3000)

            page_content = await self.page.content()
            if "Gestionar Contacto" in page_content or "Actividad" in page_content:
                logger.info("Panel de gestion abierto correctamente")
                return True

            logger.warning("El panel podria no haberse abierto correctamente; se continua con la captura")
            return True

        except Exception as e:
            logger.error(f"Error abriendo panel de gestion: {e}")
            return False

    async def _open_result_row_actions_menu(self) -> bool:
        """Abre el menu de tres puntos de la primera fila visible de resultados."""
        result_row_selectors = [
            "table tbody tr",
            ".contact-row",
            ".result-row",
            "[class*='contact-item']",
            "[role='row']",
        ]

        for row_selector in result_row_selectors:
            rows = self.page.locator(row_selector)
            try:
                count = await rows.count()
            except Exception:
                continue

            for i in range(count):
                row = rows.nth(i)
                try:
                    if await row.is_visible() and await self._click_actions_button_inside_row(row):
                        logger.info("Menu de 3 puntos abierto desde la fila del lead")
                        return True
                except Exception as e:
                    logger.debug(f"No se pudo abrir menu en fila {i}: {e}")

        return await self._click_actions_button_by_position()

    async def _click_actions_button_inside_row(self, row) -> bool:
        """Hace click en el control mas a la derecha dentro de una fila."""
        action_selectors = [
            "button[aria-haspopup='menu']",
            "button[aria-label*='opciones' i]",
            "button[aria-label*='acciones' i]",
            "button[title*='opciones' i]",
            "button[title*='acciones' i]",
            "button:has(svg)",
            "button",
            "[role='button']",
        ]

        for selector in action_selectors:
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

            for _, item in sorted(candidates, key=lambda value: value[0], reverse=True):
                try:
                    await item.scroll_into_view_if_needed(timeout=3000)
                    await BrowserManager.human_delay(250, 500)
                    await item.click(force=True, timeout=4000)
                    await BrowserManager.human_delay(700, 1000)
                    if await self._gestion_menu_is_visible():
                        return True
                except Exception:
                    continue

        try:
            box = await row.bounding_box()
            if box:
                await self.page.mouse.click(box["x"] + box["width"] - 18, box["y"] + box["height"] / 2)
                await BrowserManager.human_delay(700, 1000)
                return await self._gestion_menu_is_visible()
        except Exception:
            pass

        return False

    async def _click_actions_button_by_position(self) -> bool:
        """Fallback: hace click cerca del extremo derecho de la primera fila."""
        try:
            clicked = await self.page.evaluate(
                """
                () => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 0
                            && r.height > 0;
                    };

                    const rows = Array.from(document.querySelectorAll(
                        'table tbody tr, .contact-row, .result-row, [class*=contact-item], [role=row]'
                    )).filter(visible);

                    const row = rows.find((item) => item.getBoundingClientRect().height > 20);
                    if (!row) return false;

                    const box = row.getBoundingClientRect();
                    const target = document.elementFromPoint(box.right - 18, box.top + box.height / 2);
                    if (!target) return false;

                    target.dispatchEvent(new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }));
                    return true;
                }
                """
            )
            if clicked:
                await BrowserManager.human_delay(700, 1000)
                return await self._gestion_menu_is_visible()
        except Exception as e:
            logger.debug(f"Fallback por posicion fallo: {e}")

        return False

    async def _gestion_menu_is_visible(self) -> bool:
        """Confirma que el desplegable contiene la opcion Gestionar."""
        try:
            gestionar = self.page.get_by_text("Gestionar", exact=True)
            count = await gestionar.count()
            for i in range(count):
                if await gestionar.nth(i).is_visible():
                    return True
        except Exception:
            pass
        return False

    async def _click_gestionar_option(self) -> bool:
        """Selecciona la opcion Gestionar del menu abierto."""
        gestionar_selectors = [
            "[role='menuitem']:has-text('Gestionar')",
            ".dropdown-menu a:has-text('Gestionar')",
            ".dropdown-menu button:has-text('Gestionar')",
            "a:has-text('Gestionar')",
            "button:has-text('Gestionar')",
            "li:has-text('Gestionar')",
            "div:has-text('Gestionar')",
            "span:has-text('Gestionar')",
        ]

        for selector in gestionar_selectors:
            option = self.page.locator(selector)
            try:
                count = await option.count()
            except Exception:
                continue

            for i in range(count):
                item = option.nth(i)
                try:
                    if await item.is_visible():
                        await item.click(force=True, timeout=4000)
                        logger.info("Click en 'Gestionar'")
                        return True
                except Exception:
                    continue

        return False

    async def expand_contact_section(self) -> None:
        """
        En la columna izquierda abre Contacto y deja visible Nivel de programa.
        """
        try:
            logger.info("Preparando panel izquierdo: Contacto / Nivel de programa...")

            left_panel = await self._find_left_contact_panel()

            clicked = await self._click_left_contact_header(left_panel)
            if clicked:
                await BrowserManager.human_delay(900, 1300)
                logger.info("Seccion Contacto abierta en el panel izquierdo")
            else:
                logger.warning("No se pudo abrir Contacto en el panel izquierdo; se intentara scroll igualmente")

            found_area = await self._scroll_left_column_until_text(
                text="Nivel de programa",
                max_steps=45,
                step=150,
            )
            if found_area:
                logger.info("Nivel de programa visible en el panel izquierdo")
            else:
                logger.warning("No se encontro Nivel de programa en el panel izquierdo")

        except Exception as e:
            logger.warning(f"Error preparando Contacto / Nivel de programa: {e}")

    async def _scroll_left_column_until_text(self, text: str, max_steps: int = 35, step: int = 150) -> bool:
        """Busca un texto visible real en la columna izquierda y scrollea hasta encontrarlo."""
        for attempt in range(max_steps):
            try:
                found = await self.page.evaluate(
                    """
                    ({ text, step }) => {
                        const normalize = (value) => String(value || '')
                            .normalize('NFD')
                            .replace(/[\u0300-\u036f]/g, '')
                            .toLowerCase()
                            .trim();

                        const ownText = (el) => Array.from(el.childNodes || [])
                            .filter((node) => node.nodeType === Node.TEXT_NODE)
                            .map((node) => node.textContent || '')
                            .join(' ');

                        const visible = (el) => {
                            const s = window.getComputedStyle(el);
                            const r = el.getBoundingClientRect();
                            return s.display !== 'none'
                                && s.visibility !== 'hidden'
                                && r.width > 0
                                && r.height > 0;
                        };

                        const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                        const wanted = normalize(text);
                        const matches = Array.from(document.querySelectorAll('div, span, label, p, strong'))
                            .map((el) => ({ el, label: normalize(ownText(el) || el.getAttribute('aria-label') || '') }))
                            .filter(({ el, label }) => {
                                if (!label || label.length > 80) return false;
                                if (!visible(el)) return false;
                                const box = el.getBoundingClientRect();
                                return box.left < viewportWidth * 0.36
                                    && box.top > 0
                                    && box.bottom < window.innerHeight
                                    && (label === wanted || label.includes(wanted));
                            })
                            .sort((a, b) => a.label.length - b.label.length);

                        if (matches[0]) {
                            matches[0].el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
                            return true;
                        }

                        const scrollables = Array.from(document.querySelectorAll('aside, section, main, div'))
                            .filter((el) => {
                                if (!visible(el)) return false;
                                const box = el.getBoundingClientRect();
                                return box.left < viewportWidth * 0.36
                                    && box.right < viewportWidth * 0.42
                                    && box.width > 180
                                    && box.height > 180
                                    && el.scrollHeight > el.clientHeight + 20;
                            })
                            .sort((a, b) => {
                                const ar = a.getBoundingClientRect();
                                const br = b.getBoundingClientRect();
                                const aOverflow = a.scrollHeight - a.clientHeight;
                                const bOverflow = b.scrollHeight - b.clientHeight;
                                if (aOverflow !== bOverflow) return bOverflow - aOverflow;
                                return (br.height * br.width) - (ar.height * ar.width);
                            });

                        if (scrollables.length) {
                            const el = scrollables[0];
                            el.scrollTop += step;
                            el.dispatchEvent(new Event('scroll', { bubbles: true }));
                            return false;
                        }

                        window.scrollBy(0, step);
                        return false;
                    }
                    """,
                    {"text": text, "step": step},
                )

                if found:
                    logger.info(f"{text} visible en la columna izquierda")
                    await BrowserManager.human_delay(350, 650)
                    return True

                await self.page.mouse.move(180, 430)
                await self.page.mouse.wheel(0, step)
                await BrowserManager.human_delay(180, 320)

            except Exception as e:
                logger.debug(f"Scroll visual buscando '{text}' fallo en intento {attempt + 1}: {e}")
                break

        return False

    async def _find_open_contact_fields_panel(self):
        """Ubica el contenedor scrolleable de campos dentro de Contacto ya abierto."""
        try:
            handle = await self.page.evaluate_handle(
                """
                () => {
                    const normalize = (value) => String(value || '')
                        .normalize('NFD')
                        .replace(/[\u0300-\u036f]/g, '')
                        .toLowerCase();

                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 180
                            && r.height > 120;
                    };

                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    const candidates = Array.from(document.querySelectorAll('aside, section, main, div'))
                        .filter(visible)
                        .map((el) => ({ el, box: el.getBoundingClientRect(), text: normalize(el.textContent || '') }))
                        .filter(({ box }) => box.left < viewportWidth * 0.36 && box.width < viewportWidth * 0.45)
                        .filter(({ text }) =>
                            text.includes('contacto') && (
                                text.includes('nivel de programa')
                                || text.includes('programa de interes')
                                || text.includes('tipo de programa')
                                || text.includes('zona regional')
                                || text.includes('nivel de programa')
                                || text.includes('area de interes')
                                || text.includes('telefono')
                                || text.includes('correo')
                            )
                        )
                        .sort((a, b) => {
                            const aScrollable = a.el.scrollHeight > a.el.clientHeight + 20 ? 0 : 1;
                            const bScrollable = b.el.scrollHeight > b.el.clientHeight + 20 ? 0 : 1;
                            if (aScrollable !== bScrollable) return aScrollable - bScrollable;
                            return (b.box.height * b.box.width) - (a.box.height * a.box.width);
                        });

                    return candidates[0]?.el || document.elementFromPoint(180, window.innerHeight / 2) || document.body;
                }
                """
            )
            element = handle.as_element()
            return element or await self.page.query_selector("body")
        except Exception as e:
            logger.debug(f"No se pudo ubicar subpanel de Contacto abierto: {e}")
            return await self._find_left_contact_panel()

    async def _find_left_contact_panel(self):
        """Ubica la columna izquierda del detalle, evitando textos Contacto del panel central."""
        try:
            handle = await self.page.evaluate_handle(
                """
                () => {
                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 180
                            && r.height > 180;
                    };

                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    const panels = Array.from(document.querySelectorAll('aside, section, main, div'))
                        .filter(visible)
                        .map((el) => ({ el, box: el.getBoundingClientRect() }))
                        .filter(({ box }) => box.left < viewportWidth * 0.36 && box.width < viewportWidth * 0.45)
                        .filter(({ el }) => /informacion|contacto|campos siu|historial/i.test(el.textContent || ''))
                        .sort((a, b) => {
                            const aScrollable = a.el.scrollHeight > a.el.clientHeight + 20 ? 0 : 1;
                            const bScrollable = b.el.scrollHeight > b.el.clientHeight + 20 ? 0 : 1;
                            if (aScrollable !== bScrollable) return aScrollable - bScrollable;
                            return (b.box.height * b.box.width) - (a.box.height * a.box.width);
                        });

                    return panels[0]?.el || document.elementFromPoint(160, window.innerHeight / 2) || document.body;
                }
                """
            )
            element = handle.as_element()
            return element or await self.page.query_selector("body")
        except Exception as e:
            logger.debug(f"No se pudo ubicar panel izquierdo: {e}")
            return await self.page.query_selector("body")

    async def _click_left_contact_header(self, panel) -> bool:
        """Abre el acordeon Contacto con clicks reales sobre la fila visible."""
        try:
            points = await self.page.evaluate(
                """
                () => {
                    const normalize = (value) => String(value || '')
                        .normalize('NFD')
                        .replace(/[\u0300-\u036f]/g, '')
                        .toLowerCase()
                        .trim();

                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 0
                            && r.height > 0;
                    };

                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    const labels = Array.from(document.querySelectorAll('button, [role=button], h1, h2, h3, h4, div, span'))
                        .filter((el) => {
                            if (!visible(el)) return false;
                            const box = el.getBoundingClientRect();
                            return box.left < viewportWidth * 0.36 && normalize(el.textContent) === 'contacto';
                        })
                        .sort((a, b) => {
                            const ar = a.getBoundingClientRect();
                            const br = b.getBoundingClientRect();
                            return ar.top - br.top || ar.left - br.left;
                        });

                    const label = labels[0];
                    if (!label) return [];

                    const labelBox = label.getBoundingClientRect();
                    const panel = label.closest('aside, section, main, [class*=card], [class*=panel]')
                        || label.parentElement
                        || document.body;
                    const panelBox = panel.getBoundingClientRect();
                    const y = labelBox.top + labelBox.height / 2;

                    return [
                        { x: panelBox.right - 22, y },
                        { x: panelBox.right - 44, y },
                        { x: labelBox.left + 18, y },
                    ];
                }
                """
            )

            if not points:
                logger.warning("No se encontro visualmente el texto Contacto en el panel izquierdo")
                return False

            for index, point in enumerate(points, start=1):
                logger.info(f"Intento {index}: click en Contacto x={point['x']} y={point['y']}")
                await self.page.mouse.move(point["x"], point["y"])
                await BrowserManager.human_delay(150, 250)
                await self.page.mouse.click(point["x"], point["y"])
                await BrowserManager.human_delay(900, 1200)

                fresh_panel = await self._find_left_contact_panel()
                if await self._left_contact_section_is_open(fresh_panel):
                    logger.info("Contacto quedo abierto")
                    return True

            return False

        except Exception as e:
            logger.debug(f"Click en Contacto izquierdo fallo: {e}")
            return False

    async def _left_contact_section_is_open(self, panel) -> bool:
        """Detecta si Contacto ya desplego sus campos en la columna izquierda."""
        try:
            return await self.page.evaluate(
                """
                (panel) => {
                    const normalize = (value) => String(value || '')
                        .normalize('NFD')
                        .replace(/[\u0300-\u036f]/g, '')
                        .toLowerCase();
                    const root = panel || document;
                    const text = normalize(root.textContent || '');
                    return text.includes('nivel de programa')
                                || text.includes('area de interes')
                        || text.includes('nivel de programa')
                                || text.includes('programa de interes')
                        || text.includes('tipo de programa')
                        || text.includes('zona regional')
                        || text.includes('telefono')
                        || text.includes('correo');
                }
                """,
                panel,
            )
        except Exception:
            return False

    async def _find_activity_panel(self):
        """Ubica la columna central Actividad y su contenedor scrolleable."""
        try:
            handle = await self.page.evaluate_handle(
                """
                () => {
                    const normalize = (value) => String(value || '')
                        .normalize('NFD')
                        .replace(/[\u0300-\u036f]/g, '')
                        .toLowerCase()
                        .trim();

                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 220
                            && r.height > 220;
                    };

                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
                    const panels = Array.from(document.querySelectorAll('aside, section, main, div'))
                        .filter(visible)
                        .map((el) => ({ el, box: el.getBoundingClientRect(), text: normalize(el.textContent) }))
                        .filter(({ box }) => box.left > viewportWidth * 0.22 && box.left < viewportWidth * 0.72)
                        .filter(({ text }) => text.includes('actividad') || text.includes('creacion') || text.includes('automatizacion'))
                        .sort((a, b) => {
                            const aScrollable = a.el.scrollHeight > a.el.clientHeight + 20 ? 0 : 1;
                            const bScrollable = b.el.scrollHeight > b.el.clientHeight + 20 ? 0 : 1;
                            if (aScrollable !== bScrollable) return aScrollable - bScrollable;
                            const aCenter = Math.abs((a.box.left + a.box.width / 2) - viewportWidth / 2);
                            const bCenter = Math.abs((b.box.left + b.box.width / 2) - viewportWidth / 2);
                            if (aCenter !== bCenter) return aCenter - bCenter;
                            return (b.box.height * b.box.width) - (a.box.height * a.box.width);
                        });

                    const panel = panels[0]?.el;
                    if (!panel) return document.elementFromPoint(viewportWidth / 2, window.innerHeight / 2) || document.body;

                    const scrollableChild = Array.from(panel.querySelectorAll('*'))
                        .filter(visible)
                        .find((el) => el.scrollHeight > el.clientHeight + 20 && normalize(el.textContent).includes('actividad'));

                    return scrollableChild || panel;
                }
                """
            )
            element = handle.as_element()
            return element or await self.page.query_selector("body")
        except Exception as e:
            logger.debug(f"No se pudo ubicar panel Actividad: {e}")
            return await self.page.query_selector("body")

    async def expand_creation_event(self) -> None:
        """
        En la columna central baja hasta Creacion, la expande y deja visible Origen Id.
        """
        try:
            logger.info("Preparando panel central: Creacion / Origen Id...")

            activity_panel = await self._find_activity_panel()

            found_creation = await self._scroll_panel_until_text(
                panel=activity_panel,
                text="Creacion",
                max_steps=35,
                step=240,
                center=True,
            )

            if not found_creation:
                logger.warning("No se encontro Creacion en Actividad")
                return

            clicked = await self._click_text_in_panel(activity_panel, "Creacion")
            if clicked:
                await BrowserManager.human_delay(900, 1300)
                logger.info("Evento Creacion expandido")
            else:
                logger.warning("Creacion se encontro, pero no se pudo hacer click")

            found_origin = await self._scroll_panel_until_text(
                panel=activity_panel,
                text="Origen Id",
                max_steps=18,
                step=120,
                center=True,
            )

            if not found_origin:
                logger.info("No aparecio Origen Id; buscando Origen (ID) de evento")
                found_origin = await self._scroll_panel_until_text(
                    panel=activity_panel,
                    text="Origen (ID) de evento",
                    max_steps=18,
                    step=120,
                    center=True,
                )

            if found_origin:
                logger.info("Campo de origen visible en el panel central")
            else:
                logger.warning("No se encontro Origen Id ni Origen (ID) de evento despues de expandir Creacion")

        except Exception as e:
            logger.warning(f"Error preparando Creacion / Origen Id: {e}")

    async def _find_panel_by_heading(self, heading: str, side: str = "center"):
        """Encuentra el contenedor scrolleable mas cercano a un titulo de panel."""
        try:
            handle = await self.page.evaluate_handle(
                """
                ({ heading, side }) => {
                    const normalize = (value) => String(value || '')
                        .normalize('NFD')
                        .replace(/[\u0300-\u036f]/g, '')
                        .toLowerCase()
                        .trim();

                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 0
                            && r.height > 0;
                    };

                    const wanted = normalize(heading);
                    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;

                    const candidates = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,button,div,span'))
                        .filter((el) => visible(el) && normalize(el.textContent).includes(wanted));

                    const sideScore = (el) => {
                        const r = el.getBoundingClientRect();
                        const center = r.left + r.width / 2;
                        if (side === 'left') return center;
                        if (side === 'right') return Math.abs(viewportWidth - center);
                        return Math.abs(center - viewportWidth / 2);
                    };

                    candidates.sort((a, b) => sideScore(a) - sideScore(b));

                    for (const label of candidates) {
                        let node = label;
                        let best = null;
                        for (let i = 0; node && i < 9; i += 1, node = node.parentElement) {
                            if (!visible(node)) continue;
                            const r = node.getBoundingClientRect();
                            const scrollable = node.scrollHeight > node.clientHeight + 30;
                            const panelSized = r.height > 220 && r.width > 220;
                            if (scrollable && panelSized) return node;
                            if (!best && panelSized) best = node;
                        }
                        if (best) {
                            const scrollableChild = Array.from(best.querySelectorAll('*'))
                                .find((el) => visible(el) && el.scrollHeight > el.clientHeight + 30);
                            return scrollableChild || best;
                        }
                    }

                    return document.scrollingElement || document.documentElement;
                }
                """,
                {"heading": heading, "side": side},
            )
            element = handle.as_element()
            return element or await self.page.query_selector("body")
        except Exception as e:
            logger.debug(f"No se pudo ubicar panel '{heading}': {e}")
            return await self.page.query_selector("body")

    async def _scroll_panel_until_text(self, panel, text: str, max_steps: int = 20, step: int = 200, center: bool = True) -> bool:
        """Hace scroll dentro de un panel hasta encontrar un texto visible."""
        for _ in range(max_steps):
            try:
                found = await self.page.evaluate(
                    """
                    ({ panel, text, step, center }) => {
                        const normalize = (value) => String(value || '')
                            .normalize('NFD')
                            .replace(/[\u0300-\u036f]/g, '')
                            .toLowerCase()
                            .trim();

                        const visible = (el) => {
                            const s = window.getComputedStyle(el);
                            const r = el.getBoundingClientRect();
                            return s.display !== 'none'
                                && s.visibility !== 'hidden'
                                && r.width > 0
                                && r.height > 0;
                        };

                        const wanted = normalize(text);
                        const root = panel || document.scrollingElement || document.documentElement;
                        const nodes = Array.from(root.querySelectorAll('*'))
                            .filter((el) => visible(el) && normalize(el.textContent).includes(wanted))
                            .sort((a, b) => normalize(a.textContent).length - normalize(b.textContent).length);

                        if (nodes[0]) {
                            nodes[0].scrollIntoView({
                                block: center ? 'center' : 'nearest',
                                inline: 'nearest',
                                behavior: 'instant'
                            });
                            return true;
                        }

                        root.scrollTop += step;
                        return false;
                    }
                    """,
                    {"panel": panel, "text": text, "step": step, "center": center},
                )
                if found:
                    await BrowserManager.human_delay(350, 650)
                    return True
                await BrowserManager.human_delay(180, 320)
            except Exception as e:
                logger.debug(f"Scroll buscando '{text}' fallo: {e}")
                break

        return False

    async def _click_text_in_panel(self, panel, text: str) -> bool:
        """Hace click sobre un texto dentro de un panel, normalizando tildes."""
        try:
            clicked = await self.page.evaluate(
                """
                ({ panel, text }) => {
                    const normalize = (value) => String(value || '')
                        .normalize('NFD')
                        .replace(/[\u0300-\u036f]/g, '')
                        .toLowerCase()
                        .trim();

                    const visible = (el) => {
                        const s = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        return s.display !== 'none'
                            && s.visibility !== 'hidden'
                            && r.width > 0
                            && r.height > 0;
                    };

                    const wanted = normalize(text);
                    const root = panel || document;
                    const items = Array.from(root.querySelectorAll('button, [role=button], h1, h2, h3, h4, h5, div, span'))
                        .filter((el) => visible(el) && normalize(el.textContent).includes(wanted));

                    if (!items[0]) return false;
                    const target = items
                        .sort((a, b) => normalize(a.textContent).length - normalize(b.textContent).length)[0];

                    target.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
                    target.dispatchEvent(new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }));
                    return true;
                }
                """,
                {"panel": panel, "text": text},
            )
            return bool(clicked)
        except Exception as e:
            logger.debug(f"Click en texto '{text}' fallo: {e}")
            return False

    def cancel(self) -> None:
        """
        Cancela el proceso de búsqueda.
        Se llama cuando el usuario presiona "Detener" en la interfaz.
        """
        self._cancelled = True
        logger.info("🛑 InConcertScraper: cancelación solicitada")
