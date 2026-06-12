from typing import Protocol, Optional
from core.models import LeadRow


class IFormFiller(Protocol):
    async def fill(self, lead: LeadRow) -> bool:
        ...

    async def detect_form(self, page, lead: LeadRow) -> Optional[str]:
        ...
