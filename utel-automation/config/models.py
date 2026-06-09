"""Modelos de datos compartidos entre capas.

Mapa mental si vienes de Spring Boot: estas dataclasses y enums cumplen el rol de DTOs y value objects.
Representan solicitudes, filas de Sheets, resultados de ejecucion y eventos SSE.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class FormType(str, Enum):
    """
    Tipos de formulario que puede tener una landing page.
    Equivalente a un enum de Java.
    El valor viene de la columna E del Google Sheets.
    """
    FORM_LP = "Form Lp"
    LATERAL = "Lateral"
    FOOTER = "Footer"
    TARJETA = "Tarjeta"
    TARGETA = "Targeta"


class LeadStatus(str, Enum):
    """
    Estados posibles de un lead durante el procesamiento.
    Equivalente a un enum de estado en Java.
    """
    PENDING = "pending"
    FILLING_FORM = "filling"
    WAITING_LEAD = "waiting"
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class LeadRow:
    """
    Representa una fila del Google Sheets — un lead a testear.
    Equivalente a un Entity o DTO en Java/Spring.
    Contiene toda la información necesaria para procesar un lead.
    """

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
    """
    Datos que llegan desde la interfaz web cuando se presiona "Iniciar".
    Equivalente a un @RequestBody en Spring Boot.
    """

    country: str

    sheet_id: Optional[str] = None

    sheet_tab: Optional[str] = None

    mexico_flow: Optional[str] = None


@dataclass
class RunResult:
    """
    Resultado final que se muestra en la interfaz al terminar.
    Equivalente a un @ResponseBody en Spring Boot.
    """

    country: str

    sheet_tab: str

    total: int = 0

    successful: int = 0

    errors: int = 0

    elapsed_seconds: int = 0

    failed_leads: list = field(default_factory=list)


@dataclass
class SSEEvent:
    """
    Evento que se envía desde el servidor al browser en tiempo real.
    Equivalente a un mensaje WebSocket en Java.
    Tipos posibles:
        - "progress": avance general (X de Y leads)
        - "success": un lead llegó correctamente
        - "error": un lead no llegó (timeout)
        - "processing": el sistema está procesando este lead ahora
        - "done": terminó el proceso completo
    """

    event_type: str

    data: dict
