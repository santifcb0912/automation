from dataclasses import dataclass, field
from typing import Optional
from core.enums import LeadStatus


@dataclass
class LeadRow:
    row_number: int
    country_name: str
    nivel: Optional[str]
    landing_url: str
    form_type: str
    cliente: str
    test_email: str = ""
    status: LeadStatus = LeadStatus.PENDING
    screenshot_link: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RunRequest:
    country: str
    sheet_id: Optional[str] = None
    sheet_tab: Optional[str] = None
    mexico_flow: Optional[str] = None


@dataclass
class RunResult:
    country: str
    sheet_tab: str
    total: int = 0
    successful: int = 0
    errors: int = 0
    elapsed_seconds: int = 0
    failed_leads: list = field(default_factory=list)


@dataclass
class SSEEvent:
    event_type: str
    data: dict
