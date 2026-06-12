from typing import Protocol, Optional


class IInConcertClient(Protocol):
    async def login(self) -> bool:
        ...

    async def search_lead(self, email: str) -> Optional[dict]:
        ...

    async def open_lead_detail(self, lead_id: str) -> bool:
        ...

    async def expand_section(self, section_name: str) -> bool:
        ...
