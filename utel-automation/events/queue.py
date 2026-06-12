"""Puente thread-safe entre el worker de Playwright y el stream SSE de FastAPI.

El Orchestrator corre fuera del event loop principal de FastAPI. queue.
Queue permite publicar progreso desde ese worker mientras /api/stream consume eventos asincronicamente para el navegador.
"""

import queue
import json
import asyncio
from loguru import logger

from core.interfaces.i_event_publisher import IEventPublisher


class EventQueue(IEventPublisher):
    """
    Cola de eventos thread-safe que conecta el worker de Playwright
    con el stream SSE de FastAPI.

    Usamos queue.Queue (thread-safe) en vez de asyncio.Queue
    porque el orchestrator corre en un thread diferente al de FastAPI.
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._finished: bool = False
        self._main_loop: asyncio.AbstractEventLoop = None
        logger.debug("EventQueue thread-safe inicializada")

    @property
    def is_finished(self) -> bool:
        return self._finished

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._main_loop = loop

    def emit_sync(self, event_type: str, data: dict) -> None:
        self._queue.put({"type": event_type, "data": data})
        logger.debug(f"Evento emitido: {event_type}")

    async def emit(self, event_type: str, data: dict) -> None:
        self.emit_sync(event_type, data)

    async def consume(self):
        while not self._finished or not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                event_json = json.dumps(event, ensure_ascii=False)
                yield f"data: {event_json}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.1)
                yield "data: {\"type\": \"heartbeat\"}\n\n"
        yield "data: {\"type\": \"stream_end\"}\n\n"
        logger.debug("Stream SSE cerrado")

    def mark_finished(self) -> None:
        self._finished = True
        logger.debug("EventQueue marcada como terminada")

    def reset(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._finished = False
        logger.debug("EventQueue reseteada")
