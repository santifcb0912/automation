# ============================================================
# config/countries.py
# Configuración de cada país: URL de InConcert, datos ficticios,
# equivalencias de niveles y mapeo con columnas del Sheets
# Equivalente a un archivo de constantes o @ConfigurationProperties en Spring
# ============================================================

from dataclasses import dataclass, field  # Para crear clases de datos simples
from typing import Optional, Dict, List    # Para tipos de datos


@dataclass
class Country:
    """
    Representa la configuración de un país.
    Un @dataclass en Python es como un POJO/DTO en Java —
    una clase simple que solo guarda datos, sin lógica compleja.
    """

    # Identificador interno del país (ej: "mexico", "colombia")
    id: str

    # Nombre como aparece en la columna B del Sheets
    # Puede haber variantes (ej: "Mexico", "México")
    sheet_names: List[str]

    # URL del CRM InConcert para este país
    inconcert_url: str

    # Nombre ficticio para llenar el formulario
    fake_name: str

    # Teléfono ficticio con formato local del país
    # ⚠️ CRÍTICO: debe ser formato del país o el lead no llega a InConcert
    fake_phone: str

    # Prefijo telefónico del país (ej: "+52" para México)
    phone_prefix: str

    # Fecha de nacimiento ficticia — igual para todos los países
    fake_birthdate: str = "01/01/1990"

    # Equivalencias de niveles académicos para este país
    # Por ejemplo en Chile: Maestría = Magister, Licenciatura = Carrera
    # Si un país no tiene equivalencias especiales, este diccionario está vacío
    level_equivalences: Dict[str, str] = field(default_factory=dict)

    # Provincia/Estado ficticio (algunos formularios lo piden)
    fake_province: Optional[str] = None


# ============================================================
# LISTA DE TODOS LOS PAÍSES CON SU CONFIGURACIÓN
# ============================================================

COUNTRIES = [
    Country(
        id="mexico",
        # El Sheets usa tanto "Mexico" como "México" (con tilde)
        sheet_names=["Mexico", "México"],
        inconcert_url="https://mas-utel.inconcertcc.com/mas/home",
        fake_name="Juan Pérez",
        fake_phone="5512345678",
        phone_prefix="+52",
        fake_province="Ciudad de México",
    ),
    Country(
        id="peru",
        sheet_names=["Peru", "Perú"],
        inconcert_url="https://mas-utel-pe.inconcertcc.com/mas/home",
        fake_name="Carlos López",
        fake_phone="987654321",
        phone_prefix="+51",
        fake_province="Lima",
    ),
    Country(
        id="ecuador",
        sheet_names=["Ecuador"],
        inconcert_url="https://mas-utel-ec.inconcertcc.com/mas/home",
        fake_name="Andrés Torres",
        fake_phone="991234567",
        phone_prefix="+593",
        fake_province="Pichincha",
    ),
    Country(
        id="colombia",
        sheet_names=["Colombia"],
        inconcert_url="https://mas-utel-col.inconcertcc.com/mas/home",
        fake_name="Pedro Rodríguez",
        fake_phone="3001234567",
        phone_prefix="+57",
        fake_province="Bogotá",
    ),
    Country(
        id="dominicana",
        sheet_names=["Dominicana"],
        inconcert_url="https://mas-utel-dom.inconcertcc.com",
        fake_name="Miguel Santos",
        fake_phone="8091234567",
        phone_prefix="+1",
        fake_province="Distrito Nacional",
    ),
    Country(
        id="argentina",
        sheet_names=["Argentina"],
        inconcert_url="https://mas-utel-arg.inconcertcc.com",
        fake_name="Diego García",
        fake_phone="1112345678",
        phone_prefix="+54",
        fake_province="Buenos Aires",
    ),
    Country(
        id="bolivia",
        sheet_names=["Bolivia"],
        inconcert_url="https://mas-utel-bol.inconcertcc.com",
        fake_name="Luis Mamani",
        fake_phone="71234567",
        phone_prefix="+591",
        fake_province="La Paz",
    ),
    # ---- PAÍSES DE EMERGENTES (todos usan la misma URL de InConcert) ----
    Country(
        id="usa",
        sheet_names=["USA"],
        inconcert_url="https://mas-utel-emergentes.inconcertcc.com",
        fake_name="John Smith",
        fake_phone="3051234567",
        phone_prefix="+1",
        fake_province="Florida",
    ),
    Country(
        id="chile",
        sheet_names=["Chile"],
        inconcert_url="https://mas-utel-emergentes.inconcertcc.com",
        fake_name="Rodrigo Muñoz",
        fake_phone="912345678",
        phone_prefix="+56",
        fake_province="Región Metropolitana",
        # ⚠️ En Chile los niveles tienen nombres diferentes:
        # Maestría se llama Magister y Licenciatura se llama Carrera
        level_equivalences={
            "Maestría": "Magister",
            "Maestria": "Magister",
            "Licenciatura": "Carrera",
        },
    ),
    Country(
        id="el_salvador",
        sheet_names=["El Salvador"],
        inconcert_url="https://mas-utel-emergentes.inconcertcc.com",
        fake_name="Roberto Hernández",
        fake_phone="71234567",
        phone_prefix="+503",
    ),
    Country(
        id="honduras",
        sheet_names=["Honduras"],
        inconcert_url="https://mas-utel-emergentes.inconcertcc.com",
        fake_name="Mario Reyes",
        fake_phone="91234567",
        phone_prefix="+504",
    ),
    Country(
        id="panama",
        sheet_names=["Panama", "Panamá"],
        inconcert_url="https://mas-utel-emergentes.inconcertcc.com",
        fake_name="Fernando Díaz",
        fake_phone="61234567",
        phone_prefix="+507",
    ),
    Country(
        id="paraguay",
        sheet_names=["Paraguay"],
        inconcert_url="https://mas-utel-emergentes.inconcertcc.com",
        fake_name="Pablo Gonzalez",
        fake_phone="981123456",
        phone_prefix="+595",
    ),
    Country(
        id="guatemala",
        sheet_names=["Guatemala"],
        inconcert_url="https://mas-utel-emergentes.inconcertcc.com",
        fake_name="José Morales",
        fake_phone="41234567",
        phone_prefix="+502",
    ),
    # ---- GLOBAL (Singapur) — incluye Filipinas, India, Vietnam, Indonesia ----
    Country(
        id="global",
        sheet_names=["Global"],
        inconcert_url="https://mas-utel-singapur.infunnel.inconcert.cloud",
        fake_name="Alex Johnson",
        fake_phone="81234567",
        phone_prefix="+65",
        fake_province="Singapore",
    ),
]

# ============================================================
# FUNCIÓN AUXILIAR PARA BUSCAR UN PAÍS POR SU NOMBRE
# ============================================================

def get_country(sheet_name: str) -> Optional[Country]:
    """
    Busca y retorna la configuración de un país por su nombre del Sheets.
    Equivalente a un método de búsqueda en un @Repository de Spring.

    Por ejemplo:
        get_country("México") → retorna el objeto Country de México
        get_country("Chile")  → retorna el objeto Country de Chile

    Retorna None si el país no se encuentra en la lista.
    """
    # Normalizamos el nombre: quitamos espacios extra y ponemos en minúsculas
    # para que la búsqueda no falle por mayúsculas o espacios
    name_clean = sheet_name.strip()

    # Recorremos todos los países y buscamos cuál tiene ese nombre
    for country in COUNTRIES:
        # Verificamos si el nombre está en la lista de nombres del país
        if name_clean in country.sheet_names:
            return country

    # Si no encontramos el país, mostramos una advertencia
    from loguru import logger
    logger.warning(f"⚠️  País no encontrado en configuración: '{sheet_name}'")
    return None


def get_level_name(country: Country, level: str) -> str:
    """
    Retorna el nombre correcto del nivel para un país específico.
    Por ejemplo:
        En Chile: get_level_name(chile, "Maestría") → "Magister"
        En México: get_level_name(mexico, "Maestría") → "Maestría" (sin cambio)
    """
    if not level:
        # Si no hay nivel especificado, retornamos cadena vacía
        return ""

    # Buscamos si hay equivalencia para este nivel en este país
    # Si no hay equivalencia, usamos el nombre original
    return country.level_equivalences.get(level, level)


def infer_level_from_url(url: str) -> Optional[str]:
    """
    Intenta deducir el nivel académico a partir de la URL.
    Útil para Form LP donde la URL ya indica el tipo de producto.

    Por ejemplo:
        ".../maestrias-online" → "Maestría"
        ".../licenciaturas-executive" → "Licenciatura"
        ".../doctorados" → "Doctorado"
    """
    # Convertimos la URL a minúsculas para comparar sin problemas
    url_lower = url.lower()

    # Revisamos qué palabra clave contiene la URL
    if "maestria" in url_lower or "maestrias" in url_lower or "posgrado" in url_lower:
        return "Maestría"
    elif "licenciatura" in url_lower or "carrera" in url_lower:
        return "Licenciatura"
    elif "doctorado" in url_lower or "doctorados" in url_lower:
        return "Doctorado"
    elif "bachillerato" in url_lower:
        return "Bachillerato"
    elif "bootcamp" in url_lower:
        return "Bootcamp"
    elif "diplomado" in url_lower:
        return "Diplomado"
    elif "bachelor" in url_lower:
        return "Bachelor"
    elif "master" in url_lower or "magister" in url_lower:
        return "Master"

    # Si no encontramos nada en la URL, retornamos None
    return None
