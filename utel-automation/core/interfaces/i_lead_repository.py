from typing import Protocol, List, Optional
from core.models import LeadRow


class ILeadRepository(Protocol):
    async def get_leads(self, country_name: str, sheet_id: Optional[str] = None, sheet_tab: Optional[str] = None) -> List[LeadRow]:
        ...

    async def write_result(self, row_number: int, country_name: str, data: dict) -> None:
        ...
