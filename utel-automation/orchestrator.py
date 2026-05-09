# ============================================================
# orchestrator.py
# Coordinador central del sistema — conecta todos los módulos
# Maneja el loop de leads con 3 workers paralelos (Semaphore)
# Equivalente a un @Service principal en Spring Boot que
# coordina múltiples @Services y @Repositories
# ============================================================

import asyncio                              # Para programación asíncrona y Semaphore
from datetime import datetime               # Para generar el correo de prueba con fecha
from typing import Optional                 # Para tipos opcionales
from loguru import logger                   # Para logs

from config.settings import settings        # Configuración del sistema
from config.models import LeadRow, LeadStatus, RunRequest, RunResult, SSEEvent
from config.countries import get_country    # Para obtener configuración del país
from sheets.reader import SheetsReader      # Para leer los leads del Sheets
from sheets.writer import SheetsWriter      # Para escribir resultados en Sheets
from automation.browser import BrowserManager      # Para manejar el navegador
from automation.form_filler import FormFiller      # Para llenar formularios
from automation.inconcert import InConcertScraper  # Para verificar en InConcert
from automation.screenshot import ScreenshotManager  # Para capturas y Drive
from events.queue import EventQueue         # Para enviar eventos a la UI


class Orchestrator:
    """
    Coordinador central que conecta todos los módulos del sistema.
    Equivalente al @Service principal en Spring Boot que orquesta
    múltiples servicios y repositorios.

    Flujo por cada lead:
    1. SheetsReader lee las filas del país solicitado
    2. Para cada fila, genera el correo de prueba
    3. FormFiller abre la LP y llena el formulario
    4. InConcertScraper verifica si el lead llegó (máx 5 min)
    5. ScreenshotManager toma captura y sube a Drive
    6. SheetsWriter escribe el link en Sheets
    7. EventQueue notifica a la UI del resultado
    """

    def __init__(
        self,
        sheets_reader: SheetsReader,    # Inyectado — lee el Sheets
        sheets_writer: SheetsWriter,    # Inyectado — escribe en el Sheets
        screenshot_manager: ScreenshotManager,  # Inyectado — capturas y Drive
        event_queue: EventQueue         # Inyectado — eventos para la UI
    ):
        """
        Constructor con inyección de dependencias.
        En Java/Spring sería @Autowired — aquí lo recibimos como parámetros.
        """
        # Repositorios de Sheets (lectura y escritura)
        self.sheets_reader = sheets_reader
        self.sheets_writer = sheets_writer

        # Servicio de capturas de pantalla
        self.screenshot_manager = screenshot_manager

        # Cola de eventos para actualizar la UI en tiempo real
        self.event_queue = event_queue

        # Semáforo para limitar workers paralelos a 3
        # Equivalente a un ThreadPoolExecutor(maxThreads=3) en Java
        self._semaphore = asyncio.Semaphore(settings.max_workers)

        # Flag para cancelar el proceso desde la UI
        self._cancelled = False

        # Contador de correos de prueba — empieza en 1 y sube por cada lead
        # Se reinicia en cada ejecución nueva
        self._email_counter = 0
        self._counter_lock = asyncio.Lock()  # Lock para evitar condiciones de carrera

        logger.info("🎭 Orchestrator inicializado")

    async def run(self, request: RunRequest) -> RunResult:
        """
        Método principal — ejecuta el proceso completo de testing.
        Se llama desde FastAPI cuando el usuario presiona "Iniciar".

        Parámetros:
            request: datos de la solicitud (país, sheet_id, sheet_tab)

        Retorna:
            RunResult con el resumen de la ejecución
        """
        # Registramos el tiempo de inicio para calcular duración total
        start_time = datetime.now()

        # Reseteamos el flag de cancelación para esta ejecución
        self._cancelled = False

        # Reseteamos el contador de correos
        self._email_counter = 0

        logger.info(f"🚀 Iniciando proceso | País: {request.country}")

        # Notificamos a la UI que el proceso empezó
        await self.event_queue.emit("started", {
            "country": request.country,
            "message": f"Iniciando proceso para {request.country}..."
        })

        try:
            # PASO 1: Obtenemos la configuración del país
            country = get_country(request.country)
            if not country:
                error_msg = f"País '{request.country}' no encontrado en la configuración"
                logger.error(f"❌ {error_msg}")
                await self.event_queue.emit("error", {"message": error_msg})
                return RunResult(country=request.country, sheet_tab="")

            # PASO 2: Leemos los leads del Sheets
            logger.info(f"📖 Leyendo leads de Google Sheets para {request.country}...")
            leads, tab_name = self.sheets_reader.get_leads(
                country_name=request.country,
                sheet_id=request.sheet_id,
                sheet_tab=request.sheet_tab
            )

            if not leads:
                logger.warning(f"⚠️  No se encontraron leads para {request.country}")
                await self.event_queue.emit("done", {
                    "message": f"No se encontraron leads para {request.country}",
                    "total": 0
                })
                return RunResult(country=request.country, sheet_tab=tab_name)

            logger.info(f"✅ {len(leads)} leads encontrados en hoja {tab_name}")

            # Notificamos a la UI cuántos leads hay
            await self.event_queue.emit("leads_loaded", {
                "total": len(leads),
                "country": request.country,
                "tab": tab_name,
                "message": f"{len(leads)} leads encontrados en hoja {tab_name}"
            })

            # PASO 3: Detectamos la columna del día actual
            column = self.sheets_reader.get_column_for_today()

            # PASO 4: Procesamos todos los leads con máximo 3 en paralelo
            # asyncio.gather ejecuta todas las corrutinas "al mismo tiempo"
            # pero el Semaphore garantiza que máximo 3 corren simultáneamente
            tasks = [
                self._process_lead_with_semaphore(
                    lead=lead,
                    country=country,
                    tab_name=tab_name,
                    column=column,
                    sheet_id=request.sheet_id or settings.google_sheet_id,
                    lead_index=i,
                    total_leads=len(leads)
                )
                for i, lead in enumerate(leads)
            ]

            # Ejecutamos todos los tasks y esperamos a que terminen
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # PASO 5: Calculamos el resumen final
            elapsed = (datetime.now() - start_time).seconds
            successful = sum(1 for r in results if r is True)
            errors = sum(1 for r in results if r is False or isinstance(r, Exception))

            # Leads con error para mostrar en la UI
            failed_leads = [
                leads[i] for i, r in enumerate(results)
                if r is False or isinstance(r, Exception)
            ]

            final_result = RunResult(
                country=request.country,
                sheet_tab=tab_name,
                total=len(leads),
                successful=successful,
                errors=errors,
                elapsed_seconds=elapsed,
                failed_leads=[
                    {"email": l.test_email, "url": l.landing_url, "row": l.row_number}
                    for l in failed_leads
                ]
            )

            # Notificamos a la UI que terminó con el resumen completo
            await self.event_queue.emit("done", {
                "total": len(leads),
                "successful": successful,
                "errors": errors,
                "elapsed_minutes": round(elapsed / 60, 1),
                "country": request.country,
                "tab": tab_name,
                "failed_leads": final_result.failed_leads
            })

            logger.success(
                f"✅ Proceso terminado | "
                f"{successful} exitosos | {errors} errores | "
                f"{round(elapsed/60, 1)} min"
            )

            return final_result

        except Exception as e:
            logger.error(f"❌ Error crítico en Orchestrator: {e}")
            await self.event_queue.emit("error", {
                "message": f"Error crítico: {str(e)}"
            })
            raise

        finally:
            # Marcamos la cola de eventos como terminada
            # Esto cierra el stream SSE en la UI
            self.event_queue.mark_finished()

    async def _process_lead_with_semaphore(
        self,
        lead: LeadRow,
        country,
        tab_name: str,
        column: str,
        sheet_id: str,
        lead_index: int,
        total_leads: int
    ) -> bool:
        """
        Wrapper que aplica el Semaphore antes de procesar un lead.

        El Semaphore garantiza que máximo 3 leads se procesen al mismo tiempo.
        Si ya hay 3 corriendo, este lead espera hasta que uno termine.

        Equivalente a un ThreadPoolExecutor en Java donde se limita
        el número de hilos activos simultáneamente.
        """
        # "async with semaphore" es como un synchronized en Java
        # Pero en vez de bloquear un thread, libera el event loop de asyncio
        async with self._semaphore:
            return await self._process_single_lead(
                lead=lead,
                country=country,
                tab_name=tab_name,
                column=column,
                sheet_id=sheet_id,
                lead_index=lead_index,
                total_leads=total_leads
            )

    async def _process_single_lead(
        self,
        lead: LeadRow,
        country,
        tab_name: str,
        column: str,
        sheet_id: str,
        lead_index: int,
        total_leads: int
    ) -> bool:
        """
        Procesa un solo lead de principio a fin.

        Flujo completo:
        1. Genera el correo de prueba con contador
        2. Abre browser y llena el formulario de la LP
        3. Abre InConcert y espera el lead (máx 5 min)
        4. Si llegó: toma captura → sube a Drive → escribe link en Sheets
        5. Si no llegó: escribe "ERROR" en Sheets
        6. Notifica a la UI del resultado

        Retorna:
            True si el lead se procesó exitosamente
            False si hubo timeout o error
        """
        # Si el usuario canceló, saltamos este lead
        if self._cancelled:
            return False

        browser_manager = None

        try:
            # PASO 1: Generamos el correo de prueba único para este lead
            # Usamos un Lock para evitar que dos workers generen el mismo número
            async with self._counter_lock:
                self._email_counter += 1
                counter = self._email_counter

            # Formato: test190326N001@testingUtel.com
            date_str = datetime.now().strftime("%d%m%y")  # Ej: 190326
            lead.test_email = f"test{date_str}N{counter:03d}@testingUtel.com"

            logger.info(
                f"[{lead_index + 1}/{total_leads}] "
                f"Procesando: {lead.test_email} | "
                f"LP: {lead.landing_url[:60]}..."
            )

            # Notificamos a la UI que empezamos a procesar este lead
            await self.event_queue.emit("processing", {
                "email": lead.test_email,
                "url": lead.landing_url,
                "row": lead.row_number,
                "index": lead_index + 1,
                "total": total_leads,
                "country": lead.country_name
            })

            # PASO 2: Abrimos el navegador para este lead
            # Cada lead tiene su propio BrowserManager — su propia instancia del browser
            browser_manager = BrowserManager()
            await browser_manager.launch()

            # ---- FASE A: Llenar el formulario de la LP ----
            form_page = await browser_manager.new_page()
            form_filler = FormFiller(page=form_page, country=country)

            form_submitted = await form_filler.fill(lead)

            if not form_submitted:
                logger.warning(
                    f"⚠️  Formulario no enviado para {lead.test_email}; "
                    "no se verificará en InConcert"
                )
                await self._handle_error(
                    lead=lead,
                    sheet_id=sheet_id,
                    tab_name=tab_name,
                    column=column,
                    reason="formulario no enviado o campos obligatorios incompletos"
                )
                return False

            # ---- FASE B: Verificar en InConcert ----
            inconcert_page = await browser_manager.new_page()
            scraper = InConcertScraper(page=inconcert_page, country=country)

            # Hacemos login en InConcert
            login_ok = await scraper.login()
            if not login_ok:
                logger.error(f"❌ No se pudo hacer login en InConcert para {lead.test_email}")
                await self._handle_error(
                    lead=lead,
                    sheet_id=sheet_id,
                    tab_name=tab_name,
                    column=column,
                    reason="Error de login en InConcert"
                )
                return False

            # Buscamos el lead con reintentos cada 30s, máximo 5 min
            lead_found = await scraper.search_lead(lead.test_email)

            if not lead_found:
                # El lead no llegó en 5 minutos — registramos el error
                await self._handle_error(
                    lead=lead,
                    sheet_id=sheet_id,
                    tab_name=tab_name,
                    column=column,
                    reason="timeout 5 min"
                )
                return False

            # ---- FASE C: Preparar pantalla para la captura ----
            # Abrimos el panel de gestión del lead
            await scraper.open_lead_detail()

            # Expandimos la sección "Contacto" en columna izquierda
            await scraper.expand_contact_section()

            # Expandimos el evento "Creación" en columna central
            await scraper.expand_creation_event()

            # La columna derecha (Gestión) se deja intacta — no se toca

            # ---- FASE D: Captura y subida a Drive ----
            screenshot_link = await self.screenshot_manager.take_and_upload(
                page=inconcert_page,
                country_name=lead.country_name,
                test_email=lead.test_email
            )

            if not screenshot_link:
                logger.error(f"❌ Error subiendo captura para {lead.test_email}")
                await self._handle_error(
                    lead=lead,
                    sheet_id=sheet_id,
                    tab_name=tab_name,
                    column=column,
                    reason="error subiendo captura a Drive"
                )
                return False

            # ---- FASE E: Escribir link en Google Sheets ----
            self.sheets_writer.write_success(
                sheet_id=sheet_id,
                tab_name=tab_name,
                row_number=lead.row_number,
                column=column,
                screenshot_link=screenshot_link,
                test_email=lead.test_email
            )

            # ---- FASE F: Notificar éxito a la UI ----
            await self.event_queue.emit("success", {
                "email": lead.test_email,
                "url": lead.landing_url,
                "row": lead.row_number,
                "link": screenshot_link,
                "index": lead_index + 1,
                "total": total_leads,
                "country": lead.country_name,
                "nivel": lead.nivel or ""
            })

            lead.status = LeadStatus.SUCCESS
            logger.success(f"✅ Lead procesado exitosamente: {lead.test_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Error inesperado procesando {lead.test_email}: {e}")
            await self._handle_error(
                lead=lead,
                sheet_id=sheet_id,
                tab_name=tab_name,
                column=column,
                reason=f"error inesperado: {str(e)}"
            )
            return False

        finally:
            # Cerramos el browser siempre — aunque haya error
            # "finally" en Python es como "finally" en Java
            if browser_manager:
                await browser_manager.close()

    async def _handle_error(
        self,
        lead: LeadRow,
        sheet_id: str,
        tab_name: str,
        column: str,
        reason: str
    ) -> None:
        """
        Maneja un error en el procesamiento de un lead.
        Escribe el error en Sheets y notifica a la UI.

        Se llama tanto para timeouts como para errores inesperados.
        """
        lead.status = LeadStatus.ERROR if "error" in reason else LeadStatus.TIMEOUT
        lead.error_message = reason

        # Escribimos el error en el Sheets
        try:
            self.sheets_writer.write_error(
                sheet_id=sheet_id,
                tab_name=tab_name,
                row_number=lead.row_number,
                column=column,
                test_email=lead.test_email,
                reason=reason
            )
        except Exception as e:
            logger.error(f"❌ Error escribiendo error en Sheets: {e}")

        # Notificamos a la UI del error
        await self.event_queue.emit("lead_error", {
            "email": lead.test_email,
            "url": lead.landing_url,
            "row": lead.row_number,
            "reason": reason,
            "country": lead.country_name
        })

    def cancel(self) -> None:
        """
        Cancela el proceso en curso.
        Se llama desde FastAPI cuando el usuario presiona "Detener".
        """
        self._cancelled = True
        logger.info("🛑 Orchestrator: cancelación solicitada")
