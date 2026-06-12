"""Tests for pure utility functions in automation.form.form_utils."""

import pytest
from dataclasses import dataclass, field
from typing import Dict
from typing import Optional, Dict, List

from automation.form.form_utils import (
    normalize_text,
    canonical_level,
    level_preferences,
    modality_preferences,
    program_query,
    normalize_form_type,
    is_mexico_utel_lp,
    is_mexico_universidad_lp,
    resolve_level,
    get_form_id,
)


# ── Text normalisation ──────────────────────────────────────────────

class TestNormalizeText:
    def test_lower_and_strip(self):
        assert normalize_text("  Hello WORLD  ") == "hello world"

    def test_removes_accents(self):
        assert normalize_text("Maestría") == "maestria"

    def test_removes_special_chars(self):
        assert normalize_text("¡Hola! ¿Cómo estás?") == "hola como estas"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_none_becomes_empty(self):
        assert normalize_text(None) == ""


# ── Canonical level ─────────────────────────────────────────────────

class TestCanonicalLevel:
    def test_licenciatura_variants(self):
        for variant in ["Licenciatura", "Licenciaturas", "Licenciatura ejecutiva"]:
            assert canonical_level(variant) == "Licenciatura"

    def test_maestria_variants(self):
        for variant in ["Maestria", "Maestría", "Master", "Máster"]:
            assert canonical_level(variant) == "Maestria"

    def test_unmapped_level_preserved(self):
        assert canonical_level("Curso") == "Curso"

    def test_empty_level(self):
        assert canonical_level("") == ""


# ── Level preferences ───────────────────────────────────────────────

class TestLevelPreferences:
    def test_maestria_includes_all_aliases(self):
        prefs = level_preferences("Maestría")
        for alias in ["Maestria", "Maestrias", "Master"]:
            assert alias in prefs

    def test_no_duplicates(self):
        prefs = level_preferences("Maestría")
        assert len(prefs) == len(set(prefs))

    def test_unknown_level_returns_just_input(self):
        prefs = level_preferences("Curso")
        assert "Curso" in prefs
        assert len(set(prefs)) == len(prefs)


# ── Modality preferences ────────────────────────────────────────────

class TestModalityPreferences:
    def test_hibrida_detected(self):
        prefs = modality_preferences("Licenciatura Hibrida")
        assert "Hibrida" in prefs

    def test_ejecutiva_detected(self):
        prefs = modality_preferences("Maestria Ejecutiva")
        assert "Ejecutiva" in prefs

    def test_online_default(self):
        prefs = modality_preferences("Licenciatura")
        assert "En linea" in prefs


# ── Program query ───────────────────────────────────────────────────

class TestProgramQuery:
    def test_licenciatura_maps(self):
        assert program_query("Licenciatura") == "Licenciatura"

    def test_maestria_maps(self):
        assert program_query("Maestría") == "Maestria"

    def test_unmapped_returns_input(self):
        assert program_query("Curso") == "Curso"

    def test_none_falls_back_to_licenciatura(self):
        assert program_query(None) == "Licenciatura"


# ── Form type normalisation ─────────────────────────────────────────

class TestNormalizeFormType:
    def test_formlp_variants(self):
        assert normalize_form_type("Form Lp") == "formlp"
        assert normalize_form_type("FormLP") == "formlp"

    def test_tarjeta_variants(self):
        assert normalize_form_type("Tarjeta") == "tarjeta"
        assert normalize_form_type("Targeta") == "tarjeta"

    def test_lateral_preserved(self):
        assert normalize_form_type("Lateral") == "lateral"

    def test_footer_preserved(self):
        assert normalize_form_type("Footer") == "footer"


# ── Mexico detection ────────────────────────────────────────────────

@dataclass
class _FakeCountry:
    id: str
    level_equivalences: Dict[str, str] = field(default_factory=dict)


class TestMexicoDetection:
    def test_utel_lp_mexico(self):
        c = _FakeCountry(id="mexico")
        assert is_mexico_utel_lp(c, "https://utel.edu.mx/some-page") is True

    def test_utel_lp_not_mexico(self):
        c = _FakeCountry(id="peru")
        assert is_mexico_utel_lp(c, "https://utel.edu.mx") is False

    def test_universidad_lp_mexico(self):
        c = _FakeCountry(id="mexico")
        assert is_mexico_universidad_lp(c, "https://universidad.utel.edu.mx") is True


# ── Resolve level ───────────────────────────────────────────────────

class TestResolveLevel:
    def test_uses_level_name_from_country(self):
        c = _FakeCountry(id="peru")
        level = resolve_level(c, "Licenciatura", "")
        assert level == "Licenciatura"

    def test_infers_from_url_when_no_lead_level(self):
        c = _FakeCountry(id="mexico")
        level = resolve_level(c, "", "https://utel.edu.mx/maestrias-online")
        assert level == "Maestria"

    def test_fallback_to_raw_level(self):
        c = _FakeCountry(id="mexico")
        level = resolve_level(c, "Curso raro", "")
        assert level == "Curso raro"


# ── Form ID mapping ─────────────────────────────────────────────────

class TestGetFormId:
    def test_mapped_ids(self):
        assert get_form_id("tarjeta") == "TarjetaBLC"
        assert get_form_id("footer") == "FooterBLC"
        assert get_form_id("lateral") == "LateralBLC"

    def test_unmapped_returns_none(self):
        assert get_form_id("nonexistent") is None
