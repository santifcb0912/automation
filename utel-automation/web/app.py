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
from automation.screenshot import ScreenshotManager
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
