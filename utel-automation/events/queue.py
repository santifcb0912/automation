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
    """
    Cola thread-safe que conecta el worker de Playwright con el stream SSE.

    Usamos queue.Queue en vez de asyncio.Queue porque el orchestrator
    corre en un thread diferente al de FastAPI.
    """

    def __init__(self):
        # Queue thread-safe para cruzar del hilo del orchestrator al stream SSE.
        self._queue: queue.Queue = queue.Queue()
        # Bandera que el orchestrator activa al terminar para cerrar el stream.
        self._finished: bool = False
        logger.debug("EventQueue thread-safe inicializada")

    @property
    def is_finished(self) -> bool:
        return self._finished

    async def emit(self, event_type: str, data: dict) -> None:
        # Operacion sincrona envuelta en async para cumplir el Protocol.
        self._queue.put({"type": event_type, "data": data})
        logger.debug(f"Evento emitido: {event_type}")

    async def consume(self):
        # Mientras el proceso no haya terminado o haya eventos pendientes, se sigue yield.
        while not self._finished or not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                event_json = json.dumps(event, ensure_ascii=False)
                yield f"data: {event_json}\n\n"
            except queue.Empty:
                # Heartbeat cada 0.1s para mantener viva la conexion SSE.
                await asyncio.sleep(0.1)
                yield "data: {\"type\": \"heartbeat\"}\n\n"
        yield "data: {\"type\": \"stream_end\"}\n\n"
        logger.debug("Stream SSE cerrado")


    def mark_finished(self) -> None:
        # El orchestrador llama esto al terminar (exito o error) para cerrar el stream.
        self._finished = True
        logger.debug("EventQueue marcada como terminada")


    def reset(self) -> None:
        # Drena la cola y reinicia la bandera para un nuevo proceso sin reiniciar el server.
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._finished = False
        logger.debug("EventQueue reseteada")
