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
from config.models import RunRequest
from sheets.reader import SheetsReader
from sheets.writer import SheetsWriter
from automation.screenshot import ScreenshotManager
from core.interfaces.i_event_publisher import IEventPublisher
from orchestrator import Orchestrator
from web.validators import RunRequestValidator
from web.sse_handler import stream_response

router = APIRouter()
templates = Jinja2Templates(directory="templates")

COUNTRY_OPTIONS = [
    "Mexico", "Peru", "Colombia", "Ecuador", "Argentina",
    "Bolivia", "Chile", "USA", "Dominicana", "Paraguay",
    "Guatemala", "El Salvador", "Honduras", "Panama", "Global",
]


def normalize_mexico_flow(flow: str = "") -> Optional[str]:
    selected_flow = (flow or "").strip().lower()
    if not selected_flow:
        return None
    if selected_flow == "cms":
        return "cms"
    if selected_flow == "universidad" or "niversidad" in selected_flow:
        return "universidad"
    return selected_flow


def normalize_country_selection(country: str, mexico_flow: str = "") -> tuple[str, Optional[str]]:
    selected_country = (country or "").strip()
    selected_flow = normalize_mexico_flow(mexico_flow)

    if "|" in selected_country:
        base_country, flow = selected_country.split("|", 1)
        selected_country = base_country.strip()
        selected_flow = normalize_mexico_flow(flow) or selected_flow

    if selected_country.lower() == "mexico" and not selected_flow:
        selected_flow = "cms"

    return selected_country, selected_flow


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "countries": COUNTRY_OPTIONS, "title": "UTEL Lead Tester"},
    )


@router.post("/api/run")
async def run_test(
    request: Request,
    background_tasks: BackgroundTasks,
    country: str = Form(...),
    mexico_flow: str = Form(""),
    sheet_id: str = Form(""),
    sheet_tab: str = Form(""),
):
    active_orchestrator: Optional[Orchestrator] = getattr(request.app.state, "orchestrator", None)
    event_queue: IEventPublisher = request.app.state.event_queue

    if active_orchestrator:
        active_orchestrator.cancel()
        await asyncio.sleep(1)

    event_queue.reset()

    selected_country, selected_mexico_flow = normalize_country_selection(country, mexico_flow)

    run_request = RunRequest(
        country=selected_country,
        mexico_flow=selected_mexico_flow,
        sheet_id=sheet_id if sheet_id else None,
        sheet_tab=sheet_tab if sheet_tab else None,
    )

    orch = Orchestrator(
        sheets_reader=request.app.state.sheets_reader,
        sheets_writer=request.app.state.sheets_writer,
        screenshot_manager=request.app.state.screenshot_manager,
        event_queue=event_queue,
    )

    request.app.state.orchestrator = orch

    logger.info(f"Iniciando proceso para {selected_country} | flujo Mexico: {selected_mexico_flow or 'n/a'}")

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

    return JSONResponse({
        "status": "started",
        "country": selected_country,
        "mexico_flow": selected_mexico_flow,
        "message": f"Proceso iniciado para {selected_country}",
    })


@router.get("/api/stream")
async def stream_events(request: Request):
    event_queue: IEventPublisher = request.app.state.event_queue
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
