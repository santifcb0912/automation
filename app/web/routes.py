"""FastAPI routes — separadas de la creación de la app.

Endpoints:
  GET  /              → Interfaz web (index.html)
  POST /api/run       → Iniciar proceso
  GET  /api/stream    → SSE en tiempo real
  POST /api/stop      → Cancelar proceso
  GET  /api/status    → Estado del proceso
  GET  /api/countries → Lista de países disponibles
"""

import sys
import asyncio
import threading
from typing import Optional

from fastapi import APIRouter, Request, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from config.settings import settings
from core.models import RunRequest
from sheets.reader import SheetsReader
from sheets.writer import SheetsWriter
from automation.inconcert.screenshot import ScreenshotManager
from core.interfaces.i_event_publisher import IEventPublisher
from pipeline.orchestrator import Orchestrator
from web.sse_handler import stream_response

router = APIRouter()
templates = Jinja2Templates(directory="templates")

COUNTRY_OPTIONS = [
    "Mexico", "Peru", "Colombia", "Ecuador", "Argentina",
    "Bolivia", "Chile", "USA", "Dominicana", "Paraguay",
    "Guatemala", "El Salvador", "Panama", "Global",
]

# Flujos disponibles por pais (el frontend muestra el dropdown de flujo al elegir pais)
COUNTRY_FLOWS: dict[str, list[str]] = {
    "Mexico": ["cms", "universidad"],
    "Argentina": ["cms", "universidad"],
    "Colombia": ["cms", "universidad"],
    "Peru": ["cms", "universidad"],
    "Ecuador": ["cms", "universidad"],
    "USA": ["cms", "universidad"],
    "Bolivia": ["cms", "universidad"],
    "Chile": ["cms", "universidad"],
    "Paraguay": ["cms"],
    "Dominicana": ["cms", "universidad"],
    "Guatemala": ["cms", "universidad"],
    "Panama": ["cms"],
    "El Salvador": ["cms", "universidad"],
    "Global": ["cms"],
}

# Paises sin optgroup se renderizan como opcion simple (derivado, no se mantiene a mano)
GENERIC_COUNTRIES = [c for c in COUNTRY_OPTIONS if c not in COUNTRY_FLOWS]


def normalize_flow(flow: str = "") -> Optional[str]:
    selected_flow = (flow or "").strip().lower()
    if not selected_flow:
        return None
    if selected_flow == "cms":
        return "cms"
    if selected_flow == "universidad" or "niversidad" in selected_flow:
        return "universidad"
    return selected_flow


def normalize_country_selection(country: str, flow: str = "") -> tuple[str, Optional[str]]:
    selected_country = (country or "").strip()
    selected_flow = normalize_flow(flow)

    if "|" in selected_country:
        base_country, flow_part = selected_country.split("|", 1)
        selected_country = base_country.strip()
        selected_flow = normalize_flow(flow_part) or selected_flow

    if selected_country.lower() in ["mexico", "méxico", "argentina", "colombia", "peru", "ecuador", "usa", "bolivia", "chile", "paraguay", "dominicana", "guatemala", "panama", "el_salvador", "el salvador", "global"] and not selected_flow:
        selected_flow = "cms"

    return selected_country, selected_flow


# Valida los campos del formulario y retorna un JSONResponse de error o None
def _validate_run_input(country: str, sheet_id: str, sheet_tab: str) -> Optional[JSONResponse]:
    if not sheet_id:
        return JSONResponse({"status": "error", "message": "Debe especificar el ID de Google Sheets"}, status_code=400)
    if not sheet_tab:
        return JSONResponse({"status": "error", "message": "Debe seleccionar una hoja concreta"}, status_code=400)
    if not country:
        return JSONResponse({"status": "error", "message": "Debe seleccionar un país"}, status_code=400)
    return None


# Cancela el proceso activo si existe y resetea la cola de eventos
async def _cancel_active_orchestrator(request: Request) -> None:
    active_orchestrator: Optional[Orchestrator] = getattr(request.app.state, "orchestrator", None)
    if active_orchestrator:
        active_orchestrator.cancel()
        await asyncio.sleep(1)
    request.app.state.event_queue.reset()


# Ejecuta el proceso en un hilo con su propio event loop (requerido por Playwright en Windows)
def _start_in_background_thread(orch: Orchestrator, run_request: RunRequest) -> threading.Thread:
    def run_in_new_loop():
        loop = asyncio.new_event_loop()
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(orch.run(run_request))
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_new_loop, daemon=True)
    thread.start()
    return thread


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "country_flows": COUNTRY_FLOWS,
            "generic_countries": GENERIC_COUNTRIES,
            "title": "UTEL Lead Tester",
        },
    )


@router.post("/api/run")
async def run_test(
    request: Request,
    background_tasks: BackgroundTasks,
    country: str = Form(...),
    flow: str = Form(""),
    sheet_id: str = Form(""),
    sheet_tab: str = Form(""),
):
    await _cancel_active_orchestrator(request)

    validation_error = _validate_run_input(country, sheet_id, sheet_tab)
    if validation_error:
        return validation_error

    selected_country, selected_flow = normalize_country_selection(country, flow)
    run_request = RunRequest(country=selected_country, flow=selected_flow, sheet_id=sheet_id, sheet_tab=sheet_tab)

    orch = Orchestrator(
        sheets_reader=request.app.state.sheets_reader,
        sheets_writer=request.app.state.sheets_writer,
        screenshot_manager=request.app.state.screenshot_manager,
        event_queue=request.app.state.event_queue,
    )

    request.app.state.orchestrator = orch
    logger.info(f"Iniciando proceso para {selected_country} | flujo: {selected_flow or 'n/a'}")
    request.app.state.orchestrator_thread = _start_in_background_thread(orch, run_request)

    return JSONResponse({"status": "started", "country": selected_country, "flow": selected_flow,
                         "message": f"Proceso iniciado para {selected_country}"})


@router.get("/api/stream")
async def stream_events(request: Request):
    event_queue: IEventPublisher = request.app.state.event_queue
    if event_queue.is_finished:
        logger.info("SSE rechazado — proceso ya terminado")
        return JSONResponse({"status": "finished"}, status_code=410)
    logger.info("Cliente SSE conectado")
    return stream_response(request, event_queue)


@router.post("/api/stop")
async def stop_process(request: Request):
    active_orchestrator: Optional[Orchestrator] = getattr(request.app.state, "orchestrator", None)

    if active_orchestrator:
        active_orchestrator.cancel()
        logger.info("Proceso cancelado por el usuario")
        return JSONResponse({"status": "stopped", "message": "Proceso cancelado"})

    return JSONResponse({"status": "no_process", "message": "No hay proceso activo"})


@router.get("/api/status")
async def get_status(request: Request):
    event_queue: IEventPublisher = request.app.state.event_queue
    is_running = getattr(request.app.state, "orchestrator", None) is not None and not event_queue.is_finished

    return JSONResponse({
        "running": is_running,
        "message": "Proceso en curso" if is_running else "Sin proceso activo",
    })


@router.get("/api/countries")
async def get_countries():
    return JSONResponse({"countries": COUNTRY_OPTIONS})
