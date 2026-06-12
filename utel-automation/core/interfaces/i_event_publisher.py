from typing import AsyncGenerator, Protocol


class IEventPublisher(Protocol):
    """Interface for publishing events from worker to SSE stream."""

    async def emit(self, event_type: str, data: dict) -> None:
        ...

    def mark_finished(self) -> None:
        ...

    def reset(self) -> None:
        ...

    @property
    def is_finished(self) -> bool:
        ...

    async def consume(self) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted event strings."""
        ...
        yield ""
