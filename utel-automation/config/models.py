# ============================================================
# config/models.py
# Modelos de datos que viajan entre las capas del sistema
# Equivalente a los DTOs (Data Transfer Objects) en Java/Spring Boot
# ============================================================

from dataclasses import dataclass, field  # Para crear clases de datos
from typing import Optional               # Para campos que pueden ser None
from enum import Enum                     # Para valores fijos como un enum de Java


class FormType(str, Enum):
    """
    Tipos de formulario que puede tener una landing page.
    Equivalente a un enum de Java.
    El valor viene de la columna E del Google Sheets.
    """
    FORM_LP = "Form Lp"    # Formulario visible directo en la página
    LATERAL = "Lateral"    # Formulario que se despliega con botón lateral
    FOOTER = "Footer"      # Formulario al pie de la página (scroll abajo)
    TARJETA = "Tarjeta"    # Formulario de producto específico (con lupa si es necesario)
    TARGETA = "Targeta"    # Variante de escritura que aparece en el Sheets


class LeadStatus(str, Enum):
    """
    Estados posibles de un lead durante el procesamiento.
    Equivalente a un enum de estado en Java.
    """
    PENDING = "pending"        # Todavía no se ha procesado
    FILLING_FORM = "filling"   # Playwright está llenando el formulario
    WAITING_LEAD = "waiting"   # Esperando que el lead llegue a InConcert
    SUCCESS = "success"        # Lead llegó y captura tomada correctamente
    TIMEOUT = "timeout"        # Pasaron 5 minutos y el lead no llegó
    ERROR = "error"            # Ocurrió un error inesperado


@dataclass
class LeadRow:
    """
    Representa una fila del Google Sheets — un lead a testear.
    Equivalente a un Entity o DTO en Java/Spring.
    Contiene toda la información necesaria para procesar un lead.
    """

    # Número de fila en el Sheets (para saber dónde escribir el resultado)
    row_number: int

    # País del lead (columna B del Sheets)
    country_name: str

    # Nivel académico (columna C del Sheets)
    # Ej: "Licenciatura", "Maestría", "Doctorado", "Filipinas Bachelor"
    nivel: Optional[str]

    # URL de la landing page a testear (columna D del Sheets)
    landing_url: str

    # Tipo de formulario (columna E del Sheets)
    # Ej: "Form Lp", "Lateral", "Footer", "Tarjeta"
    form_type: str

    # Cliente (columna F del Sheets)
    # Ej: "Portal Mexico", "Portales LatAm", "Utel Mex"
    cliente: str

    # Correo de prueba generado para este lead
    # Se asigna antes de procesar (ej: "test190326N001@testUtel.com")
    test_email: str = ""

    # Estado actual del procesamiento
    status: LeadStatus = LeadStatus.PENDING

    # Link de la captura de pantalla en Google Drive
    # Se llena cuando el lead llega correctamente a InConcert
    screenshot_link: Optional[str] = None

    # Mensaje de error si algo salió mal
    error_message: Optional[str] = None


@dataclass
class RunRequest:
    """
    Datos que llegan desde la interfaz web cuando se presiona "Iniciar".
    Equivalente a un @RequestBody en Spring Boot.
    """

    # País a procesar (ej: "Colombia", "Mexico")
    country: str

    # ID del Google Sheets del mes actual
    # Si está vacío, se usa el valor del .env
    sheet_id: Optional[str] = None

    # Hoja del Sheets a usar (ej: "27-30")
    # Si está vacío, el sistema detecta automáticamente la semana actual
    sheet_tab: Optional[str] = None


@dataclass
class RunResult:
    """
    Resultado final que se muestra en la interfaz al terminar.
    Equivalente a un @ResponseBody en Spring Boot.
    """

    # País que se procesó
    country: str

    # Hoja del Sheets que se usó
    sheet_tab: str

    # Total de filas procesadas
    total: int = 0

    # Cuántas llegaron correctamente a InConcert
    successful: int = 0

    # Cuántas no llegaron (timeout o error)
    errors: int = 0

    # Tiempo total en segundos que tardó el proceso
    elapsed_seconds: int = 0

    # Lista de leads con error para revisión manual
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

    # Tipo de evento
    event_type: str

    # Datos del evento (se convierte a JSON para enviarse al browser)
    data: dict
