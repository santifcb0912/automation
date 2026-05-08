# ============================================================
# events/queue.py
# Cola de eventos thread-safe para comunicación entre
# el thread de Playwright y el event loop de FastAPI (SSE)
# ============================================================

import queue                          # queue.Queue es thread-safe — funciona entre threads
import json                           # Para convertir datos a JSON
import asyncio                        # Para el generador async de SSE
from loguru import logger             # Para logs


class EventQueue:
    """
    Cola de eventos que conecta el orchestrator (thread de Playwright)
    con la interfaz web (event loop de FastAPI via SSE).

    Usamos queue.Queue (thread-safe) en vez de asyncio.Queue
    porque el orchestrator corre en un thread diferente al de FastAPI.

    Es como un buzón compartido:
    - El orchestrator pone cartas (eventos) en el buzón desde su thread
    - FastAPI saca las cartas y las envía al browser via SSE
    """

    def __init__(self):
        # queue.Queue es thread-safe — puede usarse desde múltiples threads
        # sin riesgo de corrupción de datos
        self._queue: queue.Queue = queue.Queue()

        # Flag para saber si el proceso terminó
        self._finished: bool = False

        # El event loop de FastAPI — lo guardamos para poder
        # notificar al loop principal desde el thread de Playwright
        self._main_loop: asyncio.AbstractEventLoop = None

        logger.debug("📬 EventQueue thread-safe inicializada")

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Guarda la referencia al event loop principal de FastAPI.
        Se llama desde el endpoint /api/run antes de iniciar el thread.
        """
        self._main_loop = loop

    def emit_sync(self, event_type: str, data: dict) -> None:
        """
        Pone un evento en la cola desde el thread de Playwright.
        Versión SÍNCRONA — se llama desde el thread separado.

        Parámetros:
            event_type: tipo de evento (success, error, progress, etc.)
            data: datos del evento
        """
        event = {
            "type": event_type,
            "data": data
        }
        # put() es thread-safe — podemos llamarlo desde cualquier thread
        self._queue.put(event)
        logger.debug(f"📤 Evento emitido: {event_type}")

    async def emit(self, event_type: str, data: dict) -> None:
        """
        Versión ASYNC de emit — compatible con el código del orchestrator.
        Internamente llama a emit_sync.
        """
        self.emit_sync(event_type, data)

    async def consume(self):
        """
        Generador async que lee eventos de la cola y los formatea como SSE.
        Corre en el event loop de FastAPI.

        Lee la queue.Queue thread-safe usando asyncio para no bloquear FastAPI.
        """
        while not self._finished or not self._queue.empty():
            try:
                # Intentamos sacar un evento sin bloquear
                # get_nowait() lanza queue.Empty si no hay eventos
                event = self._queue.get_nowait()

                # Convertimos a JSON y formateamos como SSE
                event_json = json.dumps(event, ensure_ascii=False)
                yield f"data: {event_json}\n\n"

            except queue.Empty:
                # No hay eventos — esperamos 100ms y volvemos a intentar
                # Usamos asyncio.sleep para no bloquear el event loop de FastAPI
                await asyncio.sleep(0.1)

                # Enviamos heartbeat cada ~3 segundos para mantener la conexión viva
                yield "data: {\"type\": \"heartbeat\"}\n\n"

        # Proceso terminado — cerramos el stream
        yield "data: {\"type\": \"stream_end\"}\n\n"
        logger.debug("🔚 Stream SSE cerrado")

    def mark_finished(self) -> None:
        """Marca el proceso como terminado."""
        self._finished = True
        logger.debug("🏁 EventQueue marcada como terminada")

    def reset(self) -> None:
        """Resetea la cola para una nueva ejecución."""
        # Vaciamos la queue existente
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._finished = False
        logger.debug("🔄 EventQueue reseteada")