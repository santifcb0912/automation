"""Tests para ScriptLoader."""

from automation.common.script_loader import ScriptLoader


def test_load_common_js():
    js = ScriptLoader.load("common.js")
    assert "CODEX_COMMON" in js
    assert "norm" in js
    assert "visible" in js


def test_load_form_detection_js():
    js = ScriptLoader.load("form_detection.js")
    assert "findFormScope" in js
    assert "scoreForm" in js


def test_load_nonexistent_raises():
    import pytest
    with pytest.raises(FileNotFoundError):
        ScriptLoader.load("nonexistent.js")


def test_cache_works():
    js1 = ScriptLoader.load("common.js")
    js2 = ScriptLoader.load("common.js")
    assert js1 is js2
