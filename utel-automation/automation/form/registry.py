"""Registry — selecciona la strategy IFormFiller correcta segun pais y URL.

Funcion unica: get_filler() recibe country, landing_url, page y fake_data.
Retorna SIEMPRE una instancia de IFormFiller (nunca None).
El orquestador llama a get_filler() y ejecuta filler.fill() sin condicionales por pais.
"""

from playwright.async_api import Page

from config.countries import Country
from config.form_configs import CMS_CONFIGS
from automation.form.form_utils import is_mexico_utel_lp, is_mexico_universidad_lp
from automation.form.i_form_filler import IFormFiller
from automation.form.fillers.mexico_cms_filler import MexicoCmsFiller
from automation.form.fillers.fallback_filler import FallbackFiller


def get_filler(
    country: Country,
    landing_url: str,
    page: Page,
    fake_data,
) -> IFormFiller:
    # Universidad Mexico tiene flujo propio (Choices.js) — aun no migrado a strategy
    if is_mexico_universidad_lp(country, landing_url):
        return FallbackFiller(f"Universidad Mexico no implementado como strategy: {country.id}/{landing_url}")

    # Mexico CMS (utel.edu.mx) usa MexicoCmsFiller con su config
    if is_mexico_utel_lp(country, landing_url) and country.id in CMS_CONFIGS:
        return MexicoCmsFiller(CMS_CONFIGS[country.id], page, country, fake_data)

    # Default: pais/tipo sin implementar
    return FallbackFiller(f"Strategy no implementada para pais: {country.id}")
