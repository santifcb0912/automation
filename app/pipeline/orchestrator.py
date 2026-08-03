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
from automation.form.engine.orchestrator import FormFillerOrchestrator
from automation.inconcert.inconcert_client import InConcertClient
from automation.inconcert.screenshot import ScreenshotManager


class Orchestrator:

    # Inyecta las dependencias del pipeline y prepara el estado de ejecucion
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

    # Coordina el pipeline completo: leer leads, filtrar por flujo, lanzar browser, procesar en paralelo y emitir resumen
    async def run(self, request: RunRequest) -> None:
        start_time = datetime.now()
        self._cancelled = False
        self._email_counter = 0
        browser_manager = BrowserManager()

        logger.info(f"Iniciando proceso | Pais: {request.country}")
        await self._emit("started", {"country": request.country, "message": f"Iniciando proceso para {request.country}..."})

        try:
            country = get_country(request.country)
            if not country:
                raise CountryNotFoundError(f"Pais '{request.country}' no encontrado")

            await self._execute_country(request, country, browser_manager, start_time)
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

    # Ejecuta el flujo completo del pais: carga leads, lanza browser, procesa en paralelo y emite resumen
    async def _execute_country(self, request: RunRequest, country, browser_manager: BrowserManager, start_time: datetime) -> None:
        leads, tab_name = await self._load_leads(request)
        leads = self._filter_by_flow(leads, request)
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
        await browser_manager.launch()
        results = await self._run_all(leads, country, tab_name, column, request.sheet_id or settings.google_sheet_id, browser_manager)
        await self._emit_summary(results, leads, start_time, request.country, tab_name)

    # Lee los leads del Sheets en un hilo para no bloquear el event loop
    async def _load_leads(self, request: RunRequest) -> tuple:
        return await asyncio.to_thread(
            self.sheets_reader.get_leads,
            country_name=request.country,
            sheet_id=request.sheet_id,
            sheet_tab=request.sheet_tab,
        )

    # Lanza las tareas de procesamiento en paralelo y espera sus resultados
    async def _run_all(self, leads: list[LeadRow], country, tab_name: str,
                        column: str, sheet_id: str, browser_manager: BrowserManager) -> list:
        tasks = [
            asyncio.create_task(self._process_lead(lead, country, tab_name, column, sheet_id, i, len(leads), browser_manager))
            for i, lead in enumerate(leads)
        ]
        self._process_tasks = tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self._process_tasks = []
        return results

    # Calcula estadisticas del run y emite el evento final "done"
    async def _emit_summary(self, results: list, leads: list[LeadRow], start_time: datetime,
                            country_name: str, tab_name: str) -> None:
        elapsed = (datetime.now() - start_time).seconds
        successful = sum(1 for r in results if r is True)
        errors = sum(1 for r in results if r is False or isinstance(r, Exception))

        failed = [
            {"email": leads[i].test_email, "url": leads[i].landing_url, "row": leads[i].row_number}
            for i, r in enumerate(results) if r is False or isinstance(r, Exception)
        ]

        await self._emit("done", {
            "total": len(leads), "successful": successful, "errors": errors,
            "elapsed_minutes": round(elapsed / 60, 1), "country": country_name,
            "tab": tab_name, "failed_leads": failed,
        })

        logger.success(f"Proceso terminado: {successful} exitosos | {errors} errores | {round(elapsed/60, 1)} min")

    # Procesa un lead respetando el semáforo de concurrencia. Wrapper de _process_single_lead.
    async def _process_lead(self, lead: LeadRow, country, tab_name: str, 
                            column: str, sheet_id: str, idx: int, total: int,
                            browser_manager: BrowserManager) -> bool:
        async with self._semaphore:
            return await self._process_single_lead(lead, country, tab_name, column, sheet_id, idx, total, browser_manager)

    # Pipeline por lead: email unico → FormFiller → InConcert → Screenshot → Sheets. Retorna True si fue exitoso
    async def _process_single_lead(self, lead: LeadRow, country, tab_name: str, column: str,
                                   sheet_id: str, idx: int, total: int, browser_manager: BrowserManager) -> bool:
        if self._cancelled:
            return False

        form_page = None
        inconcert_page = None
        try:
            lead.test_email = self._build_test_email(await self._next_email_counter())

            error, screenshot_link, partial, form_page, inconcert_page = await self._process_lead_steps(browser_manager, country, lead, idx, total)
            if error is not None:
                await self._handle_error(lead, sheet_id, tab_name, column, error)
                return False

            await self._record_success(lead, sheet_id, tab_name, column, screenshot_link, idx, total, partial)
            logger.success(f"Lead procesado exitosamente: {lead.test_email}")
            return True

        except Exception as e:
            logger.error(f"Error inesperado procesando {lead.test_email}: {e}")
            await self._handle_error(lead, sheet_id, tab_name, column, f"error: {str(e)}")
            return False
        finally:
            for page in (form_page, inconcert_page):
                if page:
                    await page.close()

    # Anuncia el lead, llena el formulario y captura en InConcert. Retorna (error, screenshot_link, partial, form_page, inconcert_page)
    async def _process_lead_steps(self, browser_manager: BrowserManager, country, lead: LeadRow,
                                  idx: int, total: int) -> tuple:
        logger.info(f"[{idx+1}/{total}] Procesando: {lead.test_email} | LP: {lead.landing_url[:60]}...")
        await self._emit("processing", {
            "email": lead.test_email, "url": lead.landing_url, "row": lead.row_number,
            "index": idx + 1, "total": total, "country": lead.country_name,
        })
        form_error, form_page = await self._fill_form(browser_manager, country, lead)
        if form_error is not None:
            return form_error, None, False, form_page, None

        inconcert_page = await browser_manager.new_page()
        capture_error, screenshot_link, partial = await self._inconcert_capture(inconcert_page, country, lead)
        return capture_error, screenshot_link, partial, form_page, inconcert_page

    # Llena el formulario del lead en una pestana nueva. Retorna (error, page)
    async def _fill_form(self, browser_manager: BrowserManager, country, lead: LeadRow) -> tuple:
        form_page = await browser_manager.new_page()
        form_filler = FormFillerOrchestrator(page=form_page, country=country, fake_data_service=self._fake_data)
        return await form_filler.fill(lead), form_page

    # Verifica el lead en InConcert y toma la captura. Retorna (error, screenshot_link, missing_contact_area)
    async def _inconcert_capture(self, inconcert_page, country, lead: LeadRow) -> tuple:
        inconcert = InConcertClient(page=inconcert_page, country=country)
        login_ok = await inconcert.login()
        if not login_ok:
            return "Error de login en InConcert", None, False
        lead_found = await inconcert.search_lead(lead.test_email)
        if not lead_found:
            return f"Timeout >{settings.lead_timeout_seconds}s - Lead no llego", None, False
        error_reason = await inconcert.prepare_screenshot_view()
        if error_reason:
            return error_reason, None, False
        screenshot_link = await self.screenshot_manager.take_and_upload(
            page=inconcert_page, country_name=lead.country_name, test_email=lead.test_email
        )
        if not screenshot_link:
            return "error en captura o subida a Drive", None, False
        return None, screenshot_link, inconcert.missing_contact_area

    # Asigna el siguiente contador de email de forma atomica entre workers
    async def _next_email_counter(self) -> int:
        async with self._counter_lock:
            self._email_counter += 1
            return self._email_counter

    # Construye el email de prueba con fecha y contador secuencial
    def _build_test_email(self, counter: int) -> str:
        date_str = datetime.now().strftime("%d%m%y")
        return f"test{date_str}N{counter:03d}@testingUtel.com"

    # Escribe el exito en Sheets y emite el evento success o partial_success segun corresponda
    async def _record_success(self, lead: LeadRow, sheet_id: str, tab_name: str, column: str,
                              screenshot_link: str, idx: int, total: int, partial: bool) -> None:
        await asyncio.to_thread(
            self.sheets_writer.write_success,
            sheet_id=sheet_id, tab_name=tab_name, row_number=lead.row_number,
            column=column, screenshot_link=screenshot_link, test_email=lead.test_email,
        )
        data = {
            "email": lead.test_email, "url": lead.landing_url, "row": lead.row_number,
            "link": screenshot_link, "index": idx + 1, "total": total,
            "country": lead.country_name, "nivel": lead.nivel or "",
        }
        if partial:
            data["warning"] = "Captura tomada sin campo area de programa de interes en contacto - inconcert"
            logger.warning(data["warning"])
            await self._emit("partial_success", data)
        else:
            await self._emit("success", data)

    # Escribe el error en Sheets y emite el evento lead_error via SSE. No relanza la excepcion
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

    # Filtra leads por URL según el flujo (cms o universidad) usando las reglas del Country
    def _filter_by_flow(self, leads: list[LeadRow], request: RunRequest) -> list[LeadRow]:
        flow = (request.flow or "").strip().lower()
        if not flow:
            return leads
        country = get_country(request.country)
        if not country:
            return leads
        prefixes = country.flow_url_prefixes.get(flow)
        if not prefixes:
            return leads
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        return [l for l in leads if any(l.landing_url.lower().startswith(p) for p in prefixes)]

    # Cancela la ejecucion en curso: marca la bandera y cancela las tareas asincronas pendientes
    def cancel(self) -> None:
        self._cancelled = True
        logger.info("Orchestrator: cancelacion solicitada")
        for task in self._process_tasks:
            task.cancel()
