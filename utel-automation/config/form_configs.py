"""Configuraciones de formularios CMS por pais.

Cada CmsConfig define los selectores y parametros que MexicoCmsFiller usa para llenar
formularios CMS de un pais especifico. Cuando un pais nuevo necesita su propia
configuracion, se agrega una entrada al dict CMS_CONFIGS.
"""

from dataclasses import dataclass, field


@dataclass
class CmsConfig:
    """Selectores y parametros para el flujo CMS de un pais."""

    # Botones de submit (selectores CSS o pseudo-selectores de Playwright)
    submit_buttons: list[str] = field(default_factory=list)

    # Nombres de campos <select> (usados por SelectHandler para construir CSS)
    field_modality: str = "modality"
    field_area: str = "area"
    field_program: str = "program"


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
    field_modality="modality",
    field_area="area",
    field_program="program",
)

# Registry de configs CMS por pais_id.
# Para agregar un pais nuevo: agregar entrada aqui y crear su CmsConfig.
# Selectores para inspeccion de estado del formulario (read_form_state).
# Cada entrada es un string CSS compativle con querySelector (comma-separated).
FORM_STATE_SELECTORS: dict[str, str] = {
    "modality": "select[name='modality'], select#modality",
    "area": "select[name='area'], select#area",
    "program": "select[name='program'], select#program, input[name='program'], input#program",
    "first_name": "#first_name, input[name='first_name'], input[name='name'], input[name*='nombre' i], input[id*='nombre' i]",
    "email": "#email, input[name='email'], input[type='email'], input[name*='correo' i], input[id*='correo' i]",
    "phone": "#phone, input[name='phone'], input[type='tel'], input[name*='telefono' i], input[id*='telefono' i], input[name*='celular' i], input[id*='celular' i], input[name*='mobile' i]",
}

CMS_CONFIGS: dict[str, CmsConfig] = {
    "mexico": MEXICO_CMS_CONFIG,
}
