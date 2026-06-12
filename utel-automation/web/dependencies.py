"""FastAPI dependency injection container.

Reemplaza las variables globales mutable (active_orchestrator, event_queue)
por dependencias gestionadas por FastAPI con ciclo de vida controlado.
"""

from typing import Optional
from fastapi import Request
from loguru import logger

from core.interfaces.i_event_publisher import IEventPublisher
from sheets.reader import SheetsReader
from sheets.writer import SheetsWriter
from automation.screenshot import ScreenshotManager
from orchestrator import Orchestrator


def get_event_queue(request: Request) -> IEventPublisher:
    return request.app.state.event_queue


def get_sheets_reader(request: Request) -> SheetsReader:
    return request.app.state.sheets_reader


def get_sheets_writer(request: Request) -> SheetsWriter:
    return request.app.state.sheets_writer


def get_screenshot_manager(request: Request) -> ScreenshotManager:
    return request.app.state.screenshot_manager


def get_orchestrator(request: Request) -> Optional[Orchestrator]:
    return getattr(request.app.state, "orchestrator", None)


def set_orchestrator(request: Request, orch: Orchestrator) -> None:
    request.app.state.orchestrator = orch
    logger.debug("Orchestrator asignado al estado de la app")
