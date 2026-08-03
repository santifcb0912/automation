"""Configuraciones de formularios CMS por pais.

Cada CmsConfig define los selectores y parametros que CmsFiller usa para llenar
formularios CMS de un pais especifico. Cuando un pais nuevo necesita su propia
configuracion, se agrega una entrada al dict CMS_CONFIGS.
"""

from dataclasses import dataclass, field


@dataclass
class CmsConfig:
    """Selectores y parametros para el flujo CMS de un pais."""

    # Botones de submit (selectores CSS o pseudo-selectores de Playwright)
    submit_buttons: list[str] = field(default_factory=list)

    # Textos de CTA para abrir panel lateral
    cta_texts: list[str] = field(default_factory=list)

    # Nombres de campos <select> (usados por SelectHandler para construir CSS)
    field_modality: str = "modality"
    field_area: str = "area"
    field_program: str = "program"
    field_provincia: str = ""
    field_ciudad: str = ""
    field_eres_bachiller: str = ""
    field_canal_preferido: str = ""
    field_pais: str = ""
    # Prefijos de nivel del sheets -> valor de opcion del select de pais
    pais_value_map: dict[str, str] = field(default_factory=dict)


# Configuracion CMS para Mexico (utel.edu.mx)
# Los selectores se migraran a valores semanticos estables en una iteracion posterior.
# Por ahora se usan los mismos que tenia FormSubmitter originalmente.
MEXICO_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Calcula tu beca')",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Continua por Whatsapp')",
        "button:has-text('Continúa por Whatsapp')",
        "button:has-text('Solicitar información')",
        "button:has-text('Solicitar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
    field_modality="modality",
    field_area="area",
    field_program="program",
)

# Configuracion CMS para Argentina (utel.edu.mx/argentina/)
ARGENTINA_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Calcula tu beca')",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Continua por Whatsapp')",
        "button:has-text('Continúa por Whatsapp')",
        "button:has-text('Solicitar información')",
        "button:has-text('Solicitar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Contáctanos", "Contactanos"],
    field_modality="modality",
    field_area="area",
    field_program="program",
    field_provincia="provincia",
)

# Configuracion CMS para Colombia (utel.edu.mx/colombia/)
COLOMBIA_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
    field_modality="modality",
    field_area="area",
    field_program="program",
    field_eres_bachiller="eresBachiller",
    field_canal_preferido="Canal_Preferido",
)

# Configuracion CMS para Peru (utlenlinea.com/)
PERU_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
    field_ciudad="ciudad",
)

# Configuracion CMS para Ecuador (utel.edu.mx/ecuador/)
ECUADOR_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
    field_eres_bachiller="eresBachiller",
)

# Configuracion CMS para USA (utel.edu.mx/usa/)
USA_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
)

# Configuracion CMS para Bolivia (utel.edu.mx/bolivia/)
BOLIVIA_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
    field_ciudad="ciudad",
)

# Configuracion CMS para Chile (utel.edu.mx/chile/)
CHILE_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
)

# Configuracion CMS para Paraguay (utel.edu.mx/paraguay/)
PARAGUAY_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
)

# Configuracion CMS para Dominicana (utel.edu.mx/dominicana/)
DOMINICANA_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
)

# Configuracion CMS para Guatemala (utel.edu.mx/guatemala/)
GUATEMALA_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
)

# Configuracion CMS para Panama (utel.edu.mx/panama/)
PANAMA_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
)

# Configuracion CMS para El Salvador (utel.edu.mx/elsalvador/)
EL_SALVADOR_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Enviar información')",
        "button:has-text('Enviar informacion')",
        "button:has-text('Enviar')",
    ],
    cta_texts=["Solicitar información", "Solicitar informacion"],
)

# Configuracion CMS para Global (utel.edu.mx/global/)
# El pais se selecciona en el select paisesPIVI segun el nivel del sheets (Filipinas Bachelor, etc.)
GLOBAL_CMS_CONFIG = CmsConfig(
    submit_buttons=[
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Send data')",
        "button:has-text('Request information')",
    ],
    cta_texts=["Request information"],
    field_pais="paisesPIVI",
    pais_value_map={"Filipinas": "PH", "India": "IN", "Vietnam": "VN", "Indonesia": "ID"},
)

# Registry de configs CMS por pais_id.
# Para agregar un pais nuevo: agregar entrada aqui y crear su CmsConfig.
# Selectores para inspeccion de estado del formulario (read_form_state).
# Cada entrada es un string CSS compativle con querySelector (comma-separated).
FORM_STATE_SELECTORS: dict[str, str] = {
    "modality": "select[name='modality'], select#modality",
    "area": "select[name='area'], select#area",
    "program": "select[name='program'], select#program, input[name='program'], input#program",
    "first_name": "#first_name, input[name='first_name'], input[name='firstname'], input[name='name'], input[name*='nombre' i], input[id*='nombre' i]",
    "email": "#email, input[name='email'], input[type='email'], input[name*='correo' i], input[id*='correo' i]",
    "phone": "#phone, input[name='phone'], input[type='tel'], input[name*='telefono' i], input[id*='telefono' i], input[name*='celular' i], input[id*='celular' i], input[name*='mobile' i]",
}

CMS_CONFIGS: dict[str, CmsConfig] = {
    "mexico": MEXICO_CMS_CONFIG,
    "argentina": ARGENTINA_CMS_CONFIG,
    "colombia": COLOMBIA_CMS_CONFIG,
    "peru": PERU_CMS_CONFIG,
    "ecuador": ECUADOR_CMS_CONFIG,
    "usa": USA_CMS_CONFIG,
    "bolivia": BOLIVIA_CMS_CONFIG,
    "chile": CHILE_CMS_CONFIG,
    "paraguay": PARAGUAY_CMS_CONFIG,
    "dominicana": DOMINICANA_CMS_CONFIG,
    "guatemala": GUATEMALA_CMS_CONFIG,
    "panama": PANAMA_CMS_CONFIG,
    "el_salvador": EL_SALVADOR_CMS_CONFIG,
    "global": GLOBAL_CMS_CONFIG,
}
