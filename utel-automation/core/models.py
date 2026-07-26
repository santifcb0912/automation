from dataclasses import dataclass
from typing import Optional

# Representa un lead del Sheets con los datos necesarios para procesarlo.
# Lo crea SheetsReader.get_leads() y lo consume el Orchestrator en el pipeline completo.
@dataclass
class LeadRow:
    row_number: int
    country_name: str
    nivel: Optional[str]
    landing_url: str
    form_type: str
    cliente: str
    test_email: str = ""


# Agrupa los parámetros del formulario web para pasarlos al Orchestrator.run().
# Lo construye web/routes.py desde los datos del POST /api/run.
@dataclass
class RunRequest:
    country: str
    sheet_id: Optional[str] = None
    sheet_tab: Optional[str] = None
    flow: Optional[str] = None
