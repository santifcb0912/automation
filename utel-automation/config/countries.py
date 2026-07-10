"""Configuracion especifica por pais.

Cada Country define URL de InConcert y datos ficticios locales.
Los generadores de datos aleatorios (nombres, telefonos) viven en core/fake_data/.
Esto sigue SRP: Country solo almacena configuracion, no contiene logica de generacion.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from loguru import logger


@dataclass
class Country:
    id: str
    sheet_names: List[str]
    inconcert_url: str
    level_equivalences: Dict[str, str] = field(default_factory=dict)


COUNTRIES = [
    Country(id="mexico", sheet_names=["Mexico", "México"], inconcert_url="https://mas-utel.inconcertcc.com/mas/home"),
    Country(id="peru", sheet_names=["Peru", "Perú"], inconcert_url="https://mas-utel-pe.inconcertcc.com/mas/home"),
    Country(id="ecuador", sheet_names=["Ecuador"], inconcert_url="https://mas-utel-ec.inconcertcc.com/mas/home"),
    Country(id="colombia", sheet_names=["Colombia"], inconcert_url="https://mas-utel-col.inconcertcc.com/mas/home"),
    Country(id="dominicana", sheet_names=["Dominicana"], inconcert_url="https://mas-utel-dom.inconcertcc.com"),
    Country(id="argentina", sheet_names=["Argentina"], inconcert_url="https://mas-utel-arg.inconcertcc.com"),
    Country(id="bolivia", sheet_names=["Bolivia"], inconcert_url="https://mas-utel-bol.inconcertcc.com"),
    Country(id="usa", sheet_names=["USA"], inconcert_url="https://mas-utel-emergentes.inconcertcc.com"),
    Country(
        id="chile", sheet_names=["Chile"], inconcert_url="https://mas-utel-emergentes.inconcertcc.com",
        level_equivalences={"Maestría": "Magister", "Maestria": "Magister", "Licenciatura": "Carrera"},
    ),
    Country(id="el_salvador", sheet_names=["El Salvador"], inconcert_url="https://mas-utel-emergentes.inconcertcc.com"),
    Country(id="honduras", sheet_names=["Honduras"], inconcert_url="https://mas-utel-emergentes.inconcertcc.com"),
    Country(id="panama", sheet_names=["Panama", "Panamá"], inconcert_url="https://mas-utel-emergentes.inconcertcc.com"),
    Country(id="paraguay", sheet_names=["Paraguay"], inconcert_url="https://mas-utel-emergentes.inconcertcc.com"),
    Country(id="guatemala", sheet_names=["Guatemala"], inconcert_url="https://mas-utel-emergentes.inconcertcc.com"),
    Country(id="global", sheet_names=["Global"], inconcert_url="https://mas-utel-singapur.infunnel.inconcert.cloud"),
]


# Busca el país por nombre de la hoja en Sheets. Retorna None si no lo encuentra.
def get_country(sheet_name: str) -> Optional[Country]:
    name_clean = sheet_name.strip()
    for country in COUNTRIES:
        if name_clean in country.sheet_names:
            return country
    logger.warning(f"País no encontrado en configuración: '{sheet_name}'")
    return None


# Traduce el nivel académico según el país (ej. Chile "Maestría" → "Magister").
def get_level_name(country: Country, level: str) -> str:
    if not level:
        return ""
    return country.level_equivalences.get(level, level)



