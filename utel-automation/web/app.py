"""FastAPI application factory.

Centraliza la creación de la app, la inyección de dependencias
y el ciclo de vida (lifespan).
"""

import sys
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from config.settings import settings
from events.queue import EventQueue
from sheets.reader import SheetsReader
from sheets.writer import SheetsWriter
from automation.inconcert.screenshot import ScreenshotManager
from web.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("UTEL Automation iniciado")
    logger.info(f"Interfaz disponible en: http://localhost:{settings.port}")

    app.state.event_queue = EventQueue()
    app.state.sheets_reader = SheetsReader()
    app.state.sheets_writer = SheetsWriter()
    app.state.screenshot_manager = ScreenshotManager()
    app.state.orchestrator = None

    yield

    logger.info("UTEL Automation cerrando...")

    orch = getattr(app.state, "orchestrator", None)
    if orch:
        logger.info("Cancelando proceso activo...")
        orch.cancel()

    thread = getattr(app.state, "orchestrator_thread", None)
    if thread and thread.is_alive():
        logger.info("Esperando a que el hilo de proceso termine...")
        thread.join(timeout=15)
        if thread.is_alive():
            logger.warning("Hilo de proceso no termino a tiempo — forzando cierre")
        else:
            logger.info("Hilo de proceso terminado correctamente")


def create_app() -> FastAPI:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    app = FastAPI(
        title="UTEL Lead Tester",
        description="Sistema de automatización para testing de leads de UTEL",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(router)

    return app
