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
        Abre el panel de gestión del lead encontrado.
        Hace click en los 3 puntos (⋮) al lado derecho del lead
        y selecciona "Gestionar" del menú desplegable.

        Retorna:
            True si el panel se abrió correctamente
            False si hubo algún error
        """
        try:
            logger.info("📂 Abriendo panel de gestión del lead...")

            # Buscamos el botón de 3 puntos (menú contextual del lead)
            three_dots_selectors = [
                "button.more-options",
                ".dropdown-toggle",
                "button[aria-label='Más opciones']",
                "button[aria-label='opciones']",
                ".contact-row button:last-child",
                "table tbody tr button",
                "[class*='more'] button",
                # Selector por el ícono de 3 puntos
                "button:has(.icon-dots)",
                "button:has([class*='dots'])",
                # Último elemento clickeable en la fila
                "table tbody tr td:last-child button",
            ]

            for selector in three_dots_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await BrowserManager.human_delay(300, 600)
                        await element.click()
                        await BrowserManager.human_delay(500, 1000)
                        logger.info("✅ Click en 3 puntos (menú de opciones)")
                        break
                except Exception:
                    continue

            # Buscamos y hacemos click en "Gestionar" del menú desplegable
            gestionar_selectors = [
                "a:has-text('Gestionar')",
                "button:has-text('Gestionar')",
                "li:has-text('Gestionar')",
                ".dropdown-menu a:has-text('Gestionar')",
                "[role='menuitem']:has-text('Gestionar')",
            ]

            for selector in gestionar_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        logger.info("✅ Click en 'Gestionar'")
                        break
                except Exception:
                    continue

            # Esperamos a que cargue el panel de gestión
            await self.page.wait_for_load_state("domcontentloaded")
            await BrowserManager.human_delay(2000, 3000)

            # Verificamos que el panel se abrió correctamente
            # El panel tiene el título "Gestionar Contacto"
            page_content = await self.page.content()
            if "Gestionar Contacto" in page_content or "Actividad" in page_content:
                logger.info("✅ Panel de gestión abierto correctamente")
                return True
            else:
                logger.warning("⚠️  El panel podría no haberse abierto correctamente")
                return True  # Continuamos igual — intentamos la captura

        except Exception as e:
            logger.error(f"❌ Error abriendo panel de gestión: {e}")
            return False

    async def expand_contact_section(self) -> None:
        """
        En la columna IZQUIERDA del panel de gestión:
        - Hace click en la sección "Contacto" para expandirla
        - Hace scroll hasta el fondo de esa columna
        """
        try:
            logger.info("👆 Expandiendo sección 'Contacto' en columna izquierda...")

            # Buscamos y hacemos click en "Contacto"
            contacto_selectors = [
                "text='Contacto'",
                "[class*='accordion']:has-text('Contacto')",
                ".section-header:has-text('Contacto')",
                "h3:has-text('Contacto')",
                "h4:has-text('Contacto')",
                "button:has-text('Contacto')",
                "[class*='collapse-header']:has-text('Contacto')",
            ]

            for selector in contacto_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        await element.click()
                        await BrowserManager.human_delay(500, 1000)
                        logger.info("✅ Sección 'Contacto' expandida")
                        break
                except Exception:
                    continue

            # Hacemos scroll hasta el fondo de la columna izquierda
            # Buscamos el panel izquierdo del layout de 3 columnas
            left_panel_selectors = [
                ".contact-info-panel",
                ".left-panel",
                ".info-column",
                "[class*='left-column']",
                "[class*='info-panel']",
                ".contact-detail-left",
            ]

            for selector in left_panel_selectors:
                try:
                    panel = await self.page.query_selector(selector)
                    if panel:
                        # Hacemos scroll hasta el final del panel izquierdo
                        await self.page.evaluate(
                            "(el) => el.scrollTop = el.scrollHeight",
                            panel
                        )
                        logger.info("✅ Scroll al fondo de columna izquierda")
                        await BrowserManager.human_delay(500, 800)
                        return
                except Exception:
                    continue

            # Si no encontramos el panel específico, hacemos scroll general
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            logger.debug("ℹ️  Scroll general en página (panel izquierdo no identificado)")

        except Exception as e:
            logger.warning(f"⚠️  Error expandiendo sección Contacto: {e}")

    async def expand_creation_event(self) -> None:
        """
        En la columna CENTRAL (Actividad) del panel de gestión:
        - Hace scroll hacia abajo hasta encontrar el evento "Creación"
        - Hace click en "Creación" para expandirlo
        - Verifica que "Origen Id" sea visible

        La columna DERECHA (Gestión) no se toca.
        """
        try:
            logger.info("📋 Expandiendo evento 'Creación' en columna central...")

            # Buscamos el panel central de actividad
            activity_panel_selectors = [
                ".activity-panel",
                ".timeline-panel",
                ".activity-column",
                "[class*='activity']",
                "[class*='timeline']",
                ".center-panel",
            ]

            activity_panel = None
            for selector in activity_panel_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        activity_panel = element
                        break
                except Exception:
                    continue

            # Hacemos scroll en el panel de actividad para encontrar "Creación"
            if activity_panel:
                # Scrolleamos gradualmente hacia abajo en el panel de actividad
                for _ in range(5):
                    await self.page.evaluate(
                        "(el) => el.scrollTop += 200",
                        activity_panel
                    )
                    await BrowserManager.human_delay(200, 400)
            else:
                # Si no encontramos el panel, hacemos scroll general
                await self.page.evaluate("window.scrollBy(0, 400)")

            await BrowserManager.human_delay(500, 800)

            # Buscamos y hacemos click en el evento "Creación"
            creation_selectors = [
                "text='Creación'",
                "[class*='event']:has-text('Creación')",
                ".timeline-item:has-text('Creación')",
                ".activity-item:has-text('Creación')",
                "[class*='activity-event']:has-text('Creación')",
                "div:has-text('Creación') button",
                ".event-header:has-text('Creación')",
            ]

            for selector in creation_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        # Hacemos scroll al elemento para asegurarnos de que sea visible
                        await element.scroll_into_view_if_needed()
                        await BrowserManager.human_delay(300, 500)

                        # Hacemos click para expandir
                        await element.click()
                        await BrowserManager.human_delay(800, 1200)
                        logger.info("✅ Evento 'Creación' expandido")
                        break
                except Exception:
                    continue

            # Verificamos que "Origen Id" sea visible
            await BrowserManager.human_delay(500, 800)

            # Hacemos scroll un poco más para que "Origen Id" quede visible
            try:
                origen_id_element = await self.page.query_selector(
                    "text='Origen Id'"
                )
                if origen_id_element:
                    await origen_id_element.scroll_into_view_if_needed()
                    logger.info("✅ 'Origen Id' visible en pantalla")
                else:
                    # Si no lo encontramos por texto, scrolleamos un poco más
                    if activity_panel:
                        await self.page.evaluate(
                            "(el) => el.scrollTop += 150",
                            activity_panel
                        )
            except Exception:
                pass

            logger.info("✅ Panel listo para captura de pantalla")

        except Exception as e:
            logger.warning(f"⚠️  Error expandiendo evento Creación: {e}")

    def cancel(self) -> None:
        """
        Cancela el proceso de búsqueda.
        Se llama cuando el usuario presiona "Detener" en la interfaz.
        """
        self._cancelled = True
        logger.info("🛑 InConcertScraper: cancelación solicitada")
