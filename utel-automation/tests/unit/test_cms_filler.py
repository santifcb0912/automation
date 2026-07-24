"""Tests unitarios para MexicoCmsFiller.

Validan que fill() llama los metodos correctos en el orden correcto
y que retorna Optional[str] segun el resultado de cada paso.
Usa mocks para SelectHandler, ContactFieldFiller, PrivacyHandler, FormSubmitter y FormDetector.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from config.countries import Country
from config.form_configs import CmsConfig
from automation.form.fill_context import FillContext
from automation.form.fillers.mexico_cms_filler import MexicoCmsFiller


def _make_country() -> Country:
    return Country(id="mexico", sheet_names=["Mexico"], inconcert_url="https://example.com")


def _make_config() -> CmsConfig:
    return CmsConfig(
        submit_buttons=["button[type='submit']"],
        field_modality="modality",
        field_area="area",
        field_program="program",
    )


def _make_ctx(tag: str = "SELECT") -> FillContext:
    form_scope = MagicMock()
    program_field = MagicMock()
    program_field.count = AsyncMock(return_value=1)
    program_field.first = program_field
    program_field.evaluate = AsyncMock(return_value=tag)
    program_field.fill = AsyncMock()
    program_field.press = AsyncMock()
    program_field.scroll_into_view_if_needed = AsyncMock()
    form_scope.locator.return_value = program_field
    return FillContext(
        form_scope=form_scope,
        level="Maestria",
        raw_level="Maestria",
        test_email="test@test.com",
        fake_name="Juan Perez",
        fake_phone="5512345678",
    )


def _make_filler() -> MexicoCmsFiller:
    page = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    return MexicoCmsFiller(_make_config(), page, _make_country(), MagicMock())


@pytest.mark.asyncio
async def test_fill_returns_none_on_success():
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=True)

    mock_privacy = AsyncMock()
    mock_privacy.check = AsyncMock(return_value=True)

    mock_submitter = AsyncMock()
    mock_submitter.submit = AsyncMock(return_value=True)

    mock_detector = AsyncMock()
    mock_detector.read_form_state = AsyncMock(return_value={
        "modality": "Maestria",
        "area": "Ingenieria",
        "program": "Ingenieria en Sistemas",
        "first_name": "Juan",
        "email": "test@test.com",
        "phone": "5512345678",
        "has_checkbox": False,
        "checkbox_checked": True,
    })

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel), \
         patch.object(mod, "ContactFieldFiller", return_value=mock_contact), \
         patch.object(mod, "PrivacyHandler", return_value=mock_privacy), \
         patch.object(mod, "FormSubmitter", return_value=mock_submitter), \
         patch.object(mod, "FormDetector", return_value=mock_detector):

        result = await filler.fill(_make_ctx())

    assert result is None


@pytest.mark.asyncio
async def test_fill_returns_error_when_area_fails():
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=False)
    mock_sel.exists = AsyncMock(return_value=True)

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel):
        result = await filler.fill(_make_ctx())

    assert result is not None
    assert "Area" in result or "area" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_program_fails():
    filler = _make_filler()

    side_effects = {"modality": True, "area": True, "program": False}

    mock_sel = AsyncMock()
    mock_sel.exists = AsyncMock(return_value=True)
    mock_sel.select = AsyncMock(side_effect=lambda field, **kw: side_effects.get(field, True))

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel):
        result = await filler.fill(_make_ctx())

    assert result is not None
    assert "Programa" in result or "programa" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_name_fails():
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=False)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=True)

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel), \
         patch.object(mod, "ContactFieldFiller", return_value=mock_contact):
        result = await filler.fill(_make_ctx())

    assert result is not None
    assert "nombre" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_email_fails():
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=False)
    mock_contact.set_phone = AsyncMock(return_value=True)

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel), \
         patch.object(mod, "ContactFieldFiller", return_value=mock_contact):
        result = await filler.fill(_make_ctx())

    assert result is not None
    assert "email" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_phone_fails():
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=False)

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel), \
         patch.object(mod, "ContactFieldFiller", return_value=mock_contact):
        result = await filler.fill(_make_ctx())

    assert result is not None
    assert "telefono" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_privacy_fails():
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=True)

    mock_privacy = AsyncMock()
    mock_privacy.check = AsyncMock(return_value=False)

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel), \
         patch.object(mod, "ContactFieldFiller", return_value=mock_contact), \
         patch.object(mod, "PrivacyHandler", return_value=mock_privacy):
        result = await filler.fill(_make_ctx())

    assert result is not None
    assert "privacidad" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_submit_fails():
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=True)

    mock_privacy = AsyncMock()
    mock_privacy.check = AsyncMock(return_value=True)

    mock_submitter = AsyncMock()
    mock_submitter.submit = AsyncMock(return_value=False)

    mock_detector = AsyncMock()
    mock_detector.read_form_state = AsyncMock(return_value={
        "modality": "Maestria",
        "area": "Ingenieria",
        "program": "Ingenieria en Sistemas",
        "first_name": "Juan",
        "email": "test@test.com",
        "phone": "5512345678",
        "has_checkbox": False,
        "checkbox_checked": True,
    })

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel), \
         patch.object(mod, "ContactFieldFiller", return_value=mock_contact), \
         patch.object(mod, "PrivacyHandler", return_value=mock_privacy), \
         patch.object(mod, "FormSubmitter", return_value=mock_submitter), \
         patch.object(mod, "FormDetector", return_value=mock_detector):
        result = await filler.fill(_make_ctx())

    assert result is not None
    assert "submit" in result.lower()


@pytest.mark.asyncio
async def test_fill_skips_area_when_not_exists():
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=False)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=True)

    mock_privacy = AsyncMock()
    mock_privacy.check = AsyncMock(return_value=True)

    mock_submitter = AsyncMock()
    mock_submitter.submit = AsyncMock(return_value=True)

    mock_detector = AsyncMock()
    mock_detector.read_form_state = AsyncMock(return_value={
        "modality": "Maestria",
        "area": "Ingenieria",
        "program": "Ingenieria en Sistemas",
        "first_name": "Juan",
        "email": "test@test.com",
        "phone": "5512345678",
        "has_checkbox": False,
        "checkbox_checked": True,
    })

    import automation.form.fillers.mexico_cms_filler as mod

    with patch.object(mod, "SelectHandler", return_value=mock_sel), \
         patch.object(mod, "ContactFieldFiller", return_value=mock_contact), \
         patch.object(mod, "PrivacyHandler", return_value=mock_privacy), \
         patch.object(mod, "FormSubmitter", return_value=mock_submitter), \
         patch.object(mod, "FormDetector", return_value=mock_detector):
        result = await filler.fill(_make_ctx())

    assert result is None


@pytest.mark.asyncio
async def test_fill_program_input_detection():
    """Cuando <input name='program'> existe, se llena como input sin pasar por select."""
    filler = _make_filler()

    mock_sel = AsyncMock()
    mock_sel.exists = AsyncMock(return_value=True)

    def _select_ok(field, **kw):
        if field == "program":
            raise AssertionError("No debe llamarse sel.select para program")
        return True
    mock_sel.select = AsyncMock(side_effect=_select_ok)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=True)

    mock_privacy = AsyncMock()
    mock_privacy.check = AsyncMock(return_value=True)

    mock_submitter = AsyncMock()
    mock_submitter.submit = AsyncMock(return_value=True)

    mock_detector = AsyncMock()
    mock_detector.read_form_state = AsyncMock(return_value={
        "modality": "Maestria",
        "area": "Ingenieria",
        "program": "Ingenieria en Sistemas",
        "first_name": "Juan",
        "email": "test@test.com",
        "phone": "5512345678",
        "has_checkbox": False,
        "checkbox_checked": True,
    })

    import automation.form.fillers.mexico_cms_filler as mod

    mock_searcher = AsyncMock()
    mock_searcher.select_random_program = AsyncMock(return_value=True)

    ctx = _make_ctx(tag="INPUT")
    with patch.object(mod, "SelectHandler", return_value=mock_sel), \
         patch.object(mod, "ContactFieldFiller", return_value=mock_contact), \
         patch.object(mod, "PrivacyHandler", return_value=mock_privacy), \
         patch.object(mod, "FormSubmitter", return_value=mock_submitter), \
         patch.object(mod, "FormDetector", return_value=mock_detector), \
         patch.object(mod, "ProgramSearchEngine", return_value=mock_searcher):
        result = await filler.fill(ctx)

    assert result is None
    assert mock_searcher.select_random_program.called
