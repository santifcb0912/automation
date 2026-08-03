"""Puente thread-safe entre el worker de Playwright y el stream SSE de FastAPI.

El Orchestrator corre fuera del event loop principal de FastAPI.
queue.Queue permite publicar progreso desde ese worker mientras
/api/stream consume eventos asincronicamente para el navegador.
"""

import queue
import json
import asyncio
from loguru import logger

from core.interfaces.i_event_publisher import IEventPublisher


class EventQueue(IEventPublisher):
    """Cola thread-safe que conecta el worker de Playwright con el stream SSE."""

    # Inicializa la cola y la bandera de fin de proceso
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._finished: bool = False
        logger.debug("EventQueue thread-safe inicializada")

    # Retorna True si el proceso ya termino y el stream debe cerrarse
    @property
    def is_finished(self) -> bool:
        return self._finished

    # Publica un evento en la cola para que el stream SSE lo envie al navegador
    async def emit(self, event_type: str, data: dict) -> None:
        self._queue.put({"type": event_type, "data": data})
        logger.debug(f"Evento emitido: {event_type}")

    # Consume la cola y emite eventos SSE con heartbeat cada 0.1s mientras haya proceso activo
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

    # Marca la cola como terminada para que el stream se cierre
    def mark_finished(self) -> None:
        self._finished = True
        logger.debug("EventQueue marcada como terminada")

    # Drena la cola y reinicia la bandera para un nuevo proceso sin reiniciar el server
    def reset(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._finished = False
        logger.debug("EventQueue reseteada")
