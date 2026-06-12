from typing import Protocol, Optional


class IBrowserManager(Protocol):
    async def launch(self) -> None:
        ...

    async def new_page(self, url: str = "about:blank") -> None:
        ...

    async def close(self) -> None:
        ...

    @staticmethod
    async def human_delay(min_ms: int = 500, max_ms: int = 1500) -> None:
        ...
