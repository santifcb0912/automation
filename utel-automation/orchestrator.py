"""Servicio principal que coordina el flujo completo de validacion de leads.

Mapa mental si vienes de Spring Boot:
- Orchestrator es el @Service principal.
- SheetsReader y SheetsWriter cumplen el rol de repositories contra Google Sheets.
- FormFiller, InConcertScraper y ScreenshotManager son servicios de dominio.
- EventQueue publica el avance hacia la interfaz web.

Flujo de negocio:
1. Leer leads del pais seleccionado desde Google Sheets.
2. Generar un correo de prueba unico para cada lead.
3. Llenar y enviar la landing page con Playwright.
4. Buscar el lead en InConcert hasta encontrarlo o agotar timeout.
5. Preparar Creacion/Origen Id y Contacto/Nivel de programa.
6. Tomar captura, subirla a Drive y escribir el link en Sheets.
"""

import asyncio
from datetime import datetime
from typing import Optional
from loguru import logger

from config.settings import settings
from config.models import LeadRow, LeadStatus, RunRequest, RunResult, SSEEvent
from config.countries import get_country
from sheets.reader import SheetsReader
from sheets.writer import SheetsWriter
from automation.browser import BrowserManager
from automation.form_filler import FormFiller
from automation.inconcert import InConcertScraper
from automation.screenshot import ScreenshotManager
from events.queue import EventQueue


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
        sheets_reader: SheetsReader,
        sheets_writer: SheetsWriter,
        screenshot_manager: ScreenshotManager,
        event_queue: EventQueue
    ):
        """
        Constructor con inyección de dependencias.
        En Java/Spring sería @Autowired — aquí lo recibimos como parámetros.
        """
        self.sheets_reader = sheets_reader
        self.sheets_writer = sheets_writer

        self.screenshot_manager = screenshot_manager

        self.event_queue = event_queue

        self._semaphore = asyncio.Semaphore(settings.max_workers)

        self._cancelled = False

        self._email_counter = 0
        self._counter_lock = asyncio.Lock()

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
        start_time = datetime.now()

        self._cancelled = False

        self._email_counter = 0

        logger.info(f"🚀 Iniciando proceso | País: {request.country}")

        await self.event_queue.emit("started", {
            "country": request.country,
            "message": f"Iniciando proceso para {request.country}..."
        })

        try:
            country = get_country(request.country)
            if not country:
                error_msg = f"País '{request.country}' no encontrado en la configuración"
                logger.error(f"❌ {error_msg}")
                await self.event_queue.emit("error", {"message": error_msg})
                return RunResult(country=request.country, sheet_tab="")

            logger.info(f"📖 Leyendo leads de Google Sheets para {request.country}...")
            leads, tab_name = self.sheets_reader.get_leads(
                country_name=request.country,
                sheet_id=request.sheet_id,
                sheet_tab=request.sheet_tab,
                mexico_flow=request.mexico_flow
            )

            leads = self._filter_mexico_flow(leads, request)

            if not leads:
                logger.warning(f"⚠️  No se encontraron leads para {request.country}")
                await self.event_queue.emit("done", {
                    "message": f"No se encontraron leads para {request.country}",
                    "total": 0
                })
                return RunResult(country=request.country, sheet_tab=tab_name)

            logger.info(f"✅ {len(leads)} leads encontrados en hoja {tab_name}")

            await self.event_queue.emit("leads_loaded", {
                "total": len(leads),
                "country": request.country,
                "tab": tab_name,
                "message": f"{len(leads)} leads encontrados en hoja {tab_name}"
            })

            column = self.sheets_reader.get_column_for_today()

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

            results = await asyncio.gather(*tasks, return_exceptions=True)

            elapsed = (datetime.now() - start_time).seconds
            successful = sum(1 for r in results if r is True)
            errors = sum(1 for r in results if r is False or isinstance(r, Exception))

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
            self.event_queue.mark_finished()

    def _filter_mexico_flow(self, leads: list[LeadRow], request: RunRequest) -> list[LeadRow]:
        if request.country.lower() not in ["mexico", "mÃ©xico", "méxico"]:
            return leads

        flow = self._normalize_mexico_flow(request.mexico_flow)
        if not flow:
            return leads

        if flow == "universidad":
            filtered = [
                lead for lead in leads
                if lead.landing_url.lower().startswith("https://universidad.utel.edu.mx")
            ]
            logger.info(f"Flujo Mexico Universidad: {len(filtered)}/{len(leads)} leads seleccionados")
            return filtered

        if flow == "cms":
            filtered = [
                lead for lead in leads
                if lead.landing_url.lower().startswith("https://utel.edu.mx")
            ]
            logger.info(f"Flujo Mexico CMS: {len(filtered)}/{len(leads)} leads seleccionados")
            return filtered

        logger.warning(f"Flujo Mexico desconocido '{request.mexico_flow}'; se procesaran todos los leads Mexico")
        return leads

    def _normalize_mexico_flow(self, flow: Optional[str]) -> str:
        normalized = (flow or "").strip().lower()
        if normalized == "cms":
            return "cms"
        if normalized == "universidad" or "niversidad" in normalized:
            return "universidad"
        return normalized

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
        if self._cancelled:
            return False

        browser_manager = None

        try:
            async with self._counter_lock:
                self._email_counter += 1
                counter = self._email_counter

            date_str = datetime.now().strftime("%d%m%y")
            lead.test_email = f"test{date_str}N{counter:03d}@testingUtel.com"

            logger.info(
                f"[{lead_index + 1}/{total_leads}] "
                f"Procesando: {lead.test_email} | "
                f"LP: {lead.landing_url[:60]}..."
            )

            await self.event_queue.emit("processing", {
                "email": lead.test_email,
                "url": lead.landing_url,
                "row": lead.row_number,
                "index": lead_index + 1,
                "total": total_leads,
                "country": lead.country_name
            })

            browser_manager = BrowserManager()
            await browser_manager.launch()

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

            inconcert_page = await browser_manager.new_page()
            scraper = InConcertScraper(page=inconcert_page, country=country)

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

            lead_found = await scraper.search_lead(lead.test_email)

            if not lead_found:
                await self._handle_error(
                    lead=lead,
                    sheet_id=sheet_id,
                    tab_name=tab_name,
                    column=column,
                    reason=f"timeout {settings.lead_timeout_seconds // 60} min"
                )
                return False

            await scraper.open_lead_detail()

            await scraper.expand_creation_event()

            await scraper.expand_contact_section()


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

            self.sheets_writer.write_success(
                sheet_id=sheet_id,
                tab_name=tab_name,
                row_number=lead.row_number,
                column=column,
                screenshot_link=screenshot_link,
                test_email=lead.test_email
            )

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
