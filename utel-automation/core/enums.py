from enum import Enum


class FormType(str, Enum):
    FORM_LP = "FormLP"
    LATERAL = "Lateral"
    FOOTER = "Footer"
    TARJETA = "Tarjeta"


class LeadStatus(str, Enum):
    PENDING = "pending"
    FILLING_FORM = "filling"
    WAITING_LEAD = "waiting"
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"


class EventType(str, Enum):
    STARTED = "started"
    LEADS_LOADED = "leads_loaded"
    PROCESSING = "processing"
    SUCCESS = "success"
    LEAD_ERROR = "lead_error"
    DONE = "done"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    STREAM_END = "stream_end"
