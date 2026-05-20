"""Punto de entrada FastAPI de UTEL Automation.

Mapa mental si vienes de Spring Boot:
- Este archivo equivale a una clase @SpringBootApplication junto con un @RestController.
- Las instancias globales funcionan como beans singleton creados al iniciar la app.
- /api/run dispara el proceso en background para no bloquear la respuesta HTTP.
- /api/stream expone eventos SSE para actualizar la interfaz en tiempo real, parecido al uso simple de un WebSocket de progreso.
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from config.settings import settings
from config.models import RunRequest
from sheets.reader import SheetsReader
from sheets.writer import SheetsWriter
from automation.screenshot import ScreenshotManager
from events.queue import EventQueue
from orchestrator import Orchestrator



event_queue = EventQueue()

sheets_reader = SheetsReader()
sheets_writer = SheetsWriter()
screenshot_manager = ScreenshotManager()

active_orchestrator: Optional[Orchestrator] = None



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Define qué hacer al iniciar y al cerrar la aplicación.
    El código antes del 'yield' se ejecuta al arrancar.
    El código después del 'yield' se ejecuta al cerrar.
    """
    logger.info("🚀 UTEL Automation iniciado")
    logger.info(f"🌐 Interfaz disponible en: http://localhost:{settings.port}")

    yield

    logger.info("🔒 UTEL Automation cerrando...")



app = FastAPI(
    title="UTEL Lead Tester",
    description="Sistema de automatización para testing de leads de UTEL",
    version="1.0.0",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")



@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Ruta principal — muestra la interfaz web.
    Equivalente a un @GetMapping("/") en Spring Boot.

    Renderiza el archivo templates/index.html con los países disponibles.
    """
    countries = [
        "Mexico", "Peru", "Colombia", "Ecuador", "Argentina",
        "Bolivia", "Chile", "USA", "Dominicana", "Paraguay",
        "Guatemala", "El Salvador", "Honduras", "Panama", "Global"
    ]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "countries": countries,
            "title": "UTEL Lead Tester"
        }
    )


@app.post("/api/run")
async def run_test(
    background_tasks: BackgroundTasks,
    country: str = Form(...),
    sheet_id: str = Form(""),
    sheet_tab: str = Form(""),
):
    """
    Inicia el proceso de testing para un país.
    Equivalente a un @PostMapping("/api/run") en Spring Boot.

    El proceso corre en background para no bloquear la respuesta HTTP.
    La UI recibe actualizaciones en tiempo real via SSE (/api/stream).
    """
    global active_orchestrator, event_queue

    if active_orchestrator:
        active_orchestrator.cancel()
        await asyncio.sleep(1)

    event_queue.reset()

    request = RunRequest(
        country=country,
        sheet_id=sheet_id if sheet_id else None,
        sheet_tab=sheet_tab if sheet_tab else None
    )

    active_orchestrator = Orchestrator(
        sheets_reader=sheets_reader,
        sheets_writer=sheets_writer,
        screenshot_manager=screenshot_manager,
        event_queue=event_queue
    )

    logger.info(f"▶️  Iniciando proceso para {country}")

    import concurrent.futures
    import threading

    def run_in_new_loop():
        """Crea un event loop nuevo en un thread separado y corre el orchestrator"""
        loop = asyncio.new_event_loop()
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(active_orchestrator.run(request))
        finally:
            loop.close()

    thread = threading.Thread(target=run_in_new_loop, daemon=True)
    thread.start()

    return JSONResponse({
        "status": "started",
        "country": country,
        "message": f"Proceso iniciado para {country}"
    })


@app.get("/api/stream")
async def stream_events(request: Request):
    """
    Endpoint de Server-Sent Events (SSE).
    Mantiene una conexión abierta y envía eventos al browser en tiempo real.
    Equivalente a un WebSocket endpoint en Spring Boot.

    HTMX en el browser escucha este endpoint con hx-sse
    y actualiza la UI automáticamente cada vez que llega un evento.
    """
    logger.info("📡 Cliente SSE conectado")

    async def event_generator():
        """
        Generador que lee eventos de la cola y los envía al browser.
        Se ejecuta hasta que el proceso termina o el cliente se desconecta.
        """
        async for event in event_queue.consume():
            if await request.is_disconnected():
                logger.info("📡 Cliente SSE desconectado")
                break
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/stop")
async def stop_process():
    """
    Cancela el proceso en curso.
    Se llama cuando el usuario presiona el botón "Detener" en la UI.
    Equivalente a un @PostMapping("/api/stop") en Spring Boot.
    """
    global active_orchestrator

    if active_orchestrator:
        active_orchestrator.cancel()
        logger.info("🛑 Proceso cancelado por el usuario")
        return JSONResponse({
            "status": "stopped",
            "message": "Proceso cancelado"
        })

    return JSONResponse({
        "status": "no_process",
        "message": "No hay proceso activo"
    })


@app.get("/api/status")
async def get_status():
    """
    Retorna el estado actual del sistema.
    Útil para verificar si hay un proceso corriendo.
    Equivalente a un @GetMapping("/api/status") en Spring Boot.
    """
    is_running = active_orchestrator is not None and not event_queue._finished

    return JSONResponse({
        "running": is_running,
        "message": "Proceso en curso" if is_running else "Sin proceso activo"
    })


@app.get("/api/countries")
async def get_countries():
    """
    Retorna la lista de países disponibles en formato JSON.
    Útil si se quiere consumir desde Postman o desde otra aplicación.
    """
    countries = [
        "Mexico", "Peru", "Colombia", "Ecuador", "Argentina",
        "Bolivia", "Chile", "USA", "Dominicana", "Paraguay",
        "Guatemala", "El Salvador", "Honduras", "Panama", "Global"
    ]
    return JSONResponse({"countries": countries})



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level="info"
    )
