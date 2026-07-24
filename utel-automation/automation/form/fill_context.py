"""FillContext — parametros compartidos que el orquestador pasa a la strategy."""

from dataclasses import dataclass

from playwright.async_api import Locator


@dataclass
class FillContext:
    """Parametros que la strategy necesita para llenar el formulario."""

    form_scope: Locator
    level: str
    raw_level: str
    test_email: str
    fake_name: str
    fake_phone: str
