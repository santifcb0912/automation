"""Utility functions for form detection and normalization.

Pure functions — no Playwright dependency. Testable standalone.
"""

import unicodedata
from typing import Optional
from config.countries import Country, get_level_name


LEVEL_ALIASES = {
    "Licenciatura": ["Licenciatura", "Licenciaturas", "Licenciatura ejecutiva", "Licenciaturas ejecutivas"],
    "Doctorado": ["Doctorado", "Doctorados"],
    "Maestria": ["Maestria", "Maestrias", "Maestría", "Maestrías", "Master", "Máster"],
    "Maestrias ejecutivas": ["Maestrias ejecutivas", "Maestrías ejecutivas", "Maestria ejecutiva", "Maestría ejecutiva"],
    "Licenciaturas hibridas": ["Licenciaturas hibridas", "Licenciaturas híbridas", "Licenciatura hibrida", "Licenciatura híbrida", "Modalidad Hibrida", "Modalidad Híbrida"],
    "Maestrias hibridas": ["Maestrias hibridas", "Maestrías híbridas", "Maestrias Híbridas", "Maestría Hibrida", "Maestría Híbrida"],
    "Bootcamps": ["Bootcamps", "Bootcamp"],
    "Bachillerato": ["Bachillerato"],
    "Diplomados": ["Diplomados", "Diplomado"],
    "Doble titulacion Mex-USA": ["Doble titulacion Mex-USA", "Doble titulación Mex-USA", "Doble titulacion", "Doble titulación", "Mex-USA"],
}

PROGRAM_SEARCH_BY_LEVEL = {
    "licenciatura": "Licenciatura",
    "licenciaturas": "Licenciatura",
    "licenciatura ejecutiva": "Licenciatura",
    "licenciaturas ejecutivas": "Licenciatura",
    "doctorado": "Doctorado",
    "doctorados": "Doctorado",
    "maestria": "Maestria",
    "maestrias": "Maestria",
    "maestria ejecutiva": "Maestria ejecutiva",
    "maestrias ejecutivas": "Maestria ejecutiva",
    "licenciatura hibrida": "Licenciatura hibrida",
    "licenciaturas hibridas": "Licenciatura hibrida",
    "bootcamp": "Bootcamp",
    "bootcamps": "Bootcamp",
    "bachillerato": "Bachillerato",
    "diplomados": "Diplomado",
    "maestrias hibridas": "Maestria hibrida",
    "doble titulacion mex usa": "Doble titulacion",
    "doble titulacion mexusa": "Doble titulacion",
}

FORM_IDS = {
    "footer": "FooterBLC",
    "lateral": "LateralBLC",
    "tarjeta": "TarjetaBLC",
    "targeta": "TarjetaBLC",
}


def normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace()).strip()


def canonical_level(level: str) -> str:
    raw = (level or "").strip()
    normalized = normalize_text(raw)
    for canonical, aliases in LEVEL_ALIASES.items():
        if normalized in {normalize_text(alias) for alias in aliases}:
            return canonical
    return raw


def level_preferences(level: str) -> list[str]:
    canonical = canonical_level(level)
    preferences = [level, canonical]
    preferences.extend(LEVEL_ALIASES.get(canonical, []))
    return list(dict.fromkeys([item for item in preferences if item]))


def modality_preferences(level: str) -> list[str]:
    normalized = normalize_text(level)
    if "hibrid" in normalized:
        return ["Hibrida", "Híbrida", "Modalidad Hibrida", "Modalidad Híbrida"]
    if "ejecutiv" in normalized:
        return ["Ejecutiva", "Ejecutivo", "Modalidad Ejecutiva"]
    return ["En linea", "En línea", "Online"]


def program_query(level: str) -> str:
    key = normalize_text(level)
    return PROGRAM_SEARCH_BY_LEVEL.get(key, level or "Licenciatura")


def normalize_form_type(form_type: str) -> str:
    raw = normalize_text(form_type).replace(" ", "")
    if raw in ["formlp", "form"]:
        return "formlp"
    if raw in ["targeta", "tarjeta"]:
        return "tarjeta"
    return raw


def is_mexico_utel_lp(country: Country, url: str) -> bool:
    return country.id == "mexico" and (url or "").strip().lower().startswith("https://utel.edu")


def is_mexico_universidad_lp(country: Country, url: str) -> bool:
    return country.id == "mexico" and (url or "").strip().lower().startswith("https://universidad.utel.edu.mx")


def resolve_level(country: Country, lead_nivel: str, landing_url: str) -> str:
    raw_level = lead_nivel or ""
    return canonical_level(get_level_name(country, raw_level) or raw_level)


def get_form_id(form_type: str) -> Optional[str]:
    return FORM_IDS.get(form_type)
