from typing import AsyncGenerator, Protocol


class IEventPublisher(Protocol):
    """Interface for publishing events from worker to SSE stream."""

    # Publica un evento SSE con tipo y datos para que el frontend lo reciba en tiempo real.
    async def emit(self, event_type: str, data: dict) -> None:
        ...

    # Marca el evento como finalizado.
    def mark_finished(self) -> None:
        ...

    # Reinicia el estado del evento.
    def reset(self) -> None:
        ...

    # Verifica si el evento ha finalizado.
    @property
    def is_finished(self) -> bool:
        ...

    # Genera un generador de eventos SSE.
    async def consume(self) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted event strings."""
        ...
        yield ""
