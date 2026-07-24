"""Orchestrator — coordina el pipeline completo de testing de leads.

Flujo por lead:
1. SheetsReader lee leads del país
2. FormFillerOrchestrator abre LP y llena formulario
3. InConcertClient busca el lead en CRM
4. ScreenshotManager toma captura y sube a Drive
5. SheetsWriter escribe resultado en Sheets
6. EventQueue notifica a la UI
"""

import asyncio
from datetime import datetime
from loguru import logger

from config.settings import settings
from core.fake_data.providers import RandomNameProvider, RandomPhoneProvider
from core.fake_data.service import FakeDataService
from core.models import LeadRow, RunRequest
from core.exceptions import CountryNotFoundError
from core.interfaces.i_event_publisher import IEventPublisher
from config.countries import get_country
from sheets.reader import SheetsReader
from sheets.writer import SheetsWriter
from automation.browser import BrowserManager
from automation.form.form_filler_orch import FormFillerOrchestrator
from automation.inconcert.inconcert_client import InConcertClient
from automation.inconcert.screenshot import ScreenshotManager


class Orchestrator:
   

    # Inyecta las dependencias del pipeline y prepara el estado de ejecución.
    def __init__(
        self,
        sheets_reader: SheetsReader,
        sheets_writer: SheetsWriter,
        screenshot_manager: ScreenshotManager,
        event_queue: IEventPublisher,
    ):
        # Inicializa las dependencias del pipeline.
        self.sheets_reader = sheets_reader
        self.sheets_writer = sheets_writer
        self.screenshot_manager = screenshot_manager
        self.event_queue: IEventPublisher = event_queue

        # Inicializa el servicio de datos ficticios.
        self._fake_data = FakeDataService(
            name_provider=RandomNameProvider(),
            phone_provider=RandomPhoneProvider(),
        )
        # Inicializa el semáforo para limitar el número de workers concurrentes.
        self._semaphore = asyncio.Semaphore(settings.max_workers)

        # Inicializa el estado de cancelación, contador de emails y bloqueo de concurrencia.
        self._cancelled = False
        self._email_counter = 0
        self._counter_lock = asyncio.Lock()
        self._process_tasks: list[asyncio.Task] = []

    # Coordina el pipeline completo: leer leads, filtrar por flujo, lanzar browser, procesar en paralelo y emitir resumen.
    async def run(self, request: RunRequest) -> None:
        start_time = datetime.now()
        self._cancelled = False
        self._email_counter = 0
        browser_manager = None

        logger.info(f"Iniciando proceso | Pais: {request.country}")
        await self._emit("started", {"country": request.country, "message": f"Iniciando proceso para {request.country}..."})

        try:
            country = get_country(request.country)
            if not country:
                raise CountryNotFoundError(f"Pais '{request.country}' no encontrado")

            leads, tab_name = await asyncio.to_thread(
                self.sheets_reader.get_leads,
                country_name=request.country,
                sheet_id=request.sheet_id,
                sheet_tab=request.sheet_tab,
            )

            leads = self._filter_mexico_flow(leads, request)
            if not leads:
                logger.warning(f"No se encontraron leads para {request.country}")
                await self._emit("done", {"message": f"No se encontraron leads para {request.country}", "total": 0})
                return

            logger.info(f"{len(leads)} leads encontrados en hoja {tab_name}")
            await self._emit("leads_loaded", {
                "total": len(leads), "country": request.country, "tab": tab_name,
                "message": f"{len(leads)} leads encontrados en hoja {tab_name}",
            })

            column = await asyncio.to_thread(self.sheets_reader.get_column_for_today)

            browser_manager = BrowserManager()
            await browser_manager.launch()

            tasks = [
                asyncio.create_task(self._process_lead(lead, country, tab_name, column, request.sheet_id or settings.google_sheet_id, i, len(leads), browser_manager))
                for i, lead in enumerate(leads)
            ]
            self._process_tasks = tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            self._process_tasks = []

            elapsed = (datetime.now() - start_time).seconds
            successful = sum(1 for r in results if r is True)
            errors = sum(1 for r in results if r is False or isinstance(r, Exception))

            failed = [
                {"email": leads[i].test_email, "url": leads[i].landing_url, "row": leads[i].row_number}
                for i, r in enumerate(results) if r is False or isinstance(r, Exception)
            ]

            await self._emit("done", {
                "total": len(leads), "successful": successful, "errors": errors,
                "elapsed_minutes": round(elapsed / 60, 1), "country": request.country,
                "tab": tab_name, "failed_leads": failed,
            })

            logger.success(f"Proceso terminado: {successful} exitosos | {errors} errores | {round(elapsed/60, 1)} min")
            return

        except CountryNotFoundError as e:
            logger.error(str(e))
            await self._emit("error", {"message": str(e)})
            return
        except Exception as e:
            logger.error(f"Error critico en Orchestrator: {e}")
            await self._emit("error", {"message": f"Error critico: {str(e)}"})
            raise
        finally:
            if browser_manager:
                await browser_manager.close()
            self.event_queue.mark_finished()

    # Procesa un lead respetando el semáforo de concurrencia. Wrapper de _process_single_lead.
    async def _process_lead(self, lead: LeadRow, country, tab_name: str, 
                            column: str, sheet_id: str, idx: int, total: int,
                            browser_manager: BrowserManager) -> bool:
        async with self._semaphore:
            return await self._process_single_lead(lead, country, tab_name, column, sheet_id, idx, total, browser_manager)

    # Pipeline por lead: email único → FormFiller → InConcert → Screenshot → Sheets. Retorna True si fue exitoso.
    async def _process_single_lead(self, lead: LeadRow, country, tab_name: str,
                                   column: str, sheet_id: str, idx: int, 
                                   total: int, browser_manager: BrowserManager) -> bool:
        if self._cancelled:
            return False

        form_page = None
        inconcert_page = None
        try:
            async with self._counter_lock:
                self._email_counter += 1
                counter = self._email_counter

            date_str = datetime.now().strftime("%d%m%y")
            lead.test_email = f"test{date_str}N{counter:03d}@testingUtel.com"

            logger.info(f"[{idx+1}/{total}] Procesando: {lead.test_email} | LP: {lead.landing_url[:60]}...")
            await self._emit("processing", {
                "email": lead.test_email, "url": lead.landing_url, "row": lead.row_number,
                "index": idx + 1, "total": total, "country": lead.country_name,
            })

            form_page = await browser_manager.new_page()
            form_filler = FormFillerOrchestrator(page=form_page, country=country, fake_data_service=self._fake_data)

            fill_error = await form_filler.fill(lead)
            if fill_error is not None:
                await self._handle_error(lead, sheet_id, tab_name, column, fill_error)
                return False

            inconcert_page = await browser_manager.new_page()
            inconcert = InConcertClient(page=inconcert_page, country=country)

            login_ok = await inconcert.login()
            if not login_ok:
                await self._handle_error(lead, sheet_id, tab_name, column, "Error de login en InConcert")
                return False

            lead_found = await inconcert.search_lead(lead.test_email)
            if not lead_found:
                await self._handle_error(lead, sheet_id, tab_name, column, f"Timeout >{settings.lead_timeout_seconds}s - Lead no llego")
                return False

            error_reason = await inconcert.prepare_screenshot_view()
            if error_reason:
                await self._handle_error(lead, sheet_id, tab_name, column, error_reason)
                return False

            screenshot_link = await self.screenshot_manager.take_and_upload(
                page=inconcert_page, country_name=lead.country_name, test_email=lead.test_email
            )
            if not screenshot_link:
                await self._handle_error(lead, sheet_id, tab_name, column, "error subiendo captura a Drive")
                return False

            if inconcert.missing_contact_area:
                warning = "Captura tomada sin campo area de programa de interes en contacto - inconcert"
                logger.warning(warning)
                await asyncio.to_thread(
                    self.sheets_writer.write_success,
                    sheet_id=sheet_id, tab_name=tab_name, row_number=lead.row_number,
                    column=column, screenshot_link=screenshot_link, test_email=lead.test_email,
                )
                await self._emit("partial_success", {
                    "email": lead.test_email, "url": lead.landing_url, "row": lead.row_number,
                    "link": screenshot_link, "index": idx + 1, "total": total,
                    "country": lead.country_name, "nivel": lead.nivel or "",
                    "warning": warning,
                })
            else:
                await asyncio.to_thread(
                    self.sheets_writer.write_success,
                    sheet_id=sheet_id, tab_name=tab_name, row_number=lead.row_number,
                    column=column, screenshot_link=screenshot_link, test_email=lead.test_email,
                )
                await self._emit("success", {
                    "email": lead.test_email, "url": lead.landing_url, "row": lead.row_number,
                    "link": screenshot_link, "index": idx + 1, "total": total,
                    "country": lead.country_name, "nivel": lead.nivel or "",
                })

            logger.success(f"Lead procesado exitosamente: {lead.test_email}")
            return True

        except Exception as e:
            logger.error(f"Error inesperado procesando {lead.test_email}: {e}")
            await self._handle_error(lead, sheet_id, tab_name, column, f"error: {str(e)}")
            return False
        finally:
            if form_page:
                await form_page.close()
            if inconcert_page:
                await inconcert_page.close()

    # Escribe el error en Sheets y emite el evento lead_error vía SSE. No relanza la excepción.
    async def _handle_error(self, lead: LeadRow, sheet_id: str, tab_name: str, column: str, reason: str) -> None:
        try:
            await asyncio.to_thread(
                self.sheets_writer.write_error,
                sheet_id=sheet_id, tab_name=tab_name, row_number=lead.row_number,
                column=column, test_email=lead.test_email, reason=reason,
            )
        except Exception as e:
            logger.error(f"Error escribiendo en Sheets: {e}")
        await self._emit("lead_error", {
            "email": lead.test_email, "url": lead.landing_url, "row": lead.row_number,
            "reason": reason, "country": lead.country_name,
        })

    # Publica un evento SSE al frontend con el tipo y datos indicados.
    async def _emit(self, event_type: str, data: dict) -> None:
        await self.event_queue.emit(event_type, data)

    # Filtra los leads de México por URL según el flujo seleccionado (universidad o cms). Para otros países retorna todos.
    def _filter_mexico_flow(self, leads: list[LeadRow], request: RunRequest) -> list[LeadRow]:
        if request.country.lower() not in ["mexico", "méxico"]:
            return leads
        flow = (request.mexico_flow or "").strip().lower()
        if not flow:
            return leads
        if flow == "universidad" in flow:
            return [l for l in leads if l.landing_url.lower().startswith("https://universidad.utel.edu.mx")]
        if flow == "cms":
            return [l for l in leads if l.landing_url.lower().startswith("https://utel.edu.mx")]
        return leads

    # Cancela la ejecución en curso: marca la bandera y cancela todas las tareas asíncronas pendientes.
    def cancel(self) -> None:
        self._cancelled = True
        logger.info("Orchestrator: cancelacion solicitada")
        for task in self._process_tasks:
            task.cancel()
