"""Tests unitarios para CmsFiller.

Validan que fill() llama los metodos correctos en el orden correcto
y que retorna Optional[str] segun el resultado de cada paso.
Usa mocks para SelectHandler, ContactFieldFiller, PrivacyHandler, FormSubmitter y FormDetector.
Los mocks se inyectan por constructor en vez de usar patch.object.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from config.countries import Country
from config.form_configs import CmsConfig
from automation.form.contracts.fill_context import FillContext
from automation.form.fillers.cms_filler import CmsFiller


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


def _make_filler(select_handler=None, contact_filler=None, privacy_handler=None,
                 submitter=None, detector=None, validator=None) -> CmsFiller:
    page = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    return CmsFiller(
        _make_config(), page, _make_country(), MagicMock(),
        select_handler=select_handler, contact_filler=contact_filler,
        privacy_handler=privacy_handler, submitter=submitter,
        detector=detector, validator=validator,
    )


@pytest.mark.asyncio
async def test_fill_returns_none_on_success():
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

    filler = _make_filler(
        select_handler=mock_sel, contact_filler=mock_contact,
        privacy_handler=mock_privacy, submitter=mock_submitter,
        detector=mock_detector,
    )
    result = await filler.fill(_make_ctx())

    assert result is None


@pytest.mark.asyncio
async def test_fill_returns_error_when_area_fails():
    mock_sel = AsyncMock()
    async def _select_side(field_name, **kw):
        return field_name != "area"
    mock_sel.select = AsyncMock(side_effect=_select_side)
    mock_sel.exists = AsyncMock(return_value=True)

    filler = _make_filler(select_handler=mock_sel)
    result = await filler.fill(_make_ctx())

    assert result is not None
    assert "Area" in result or "area" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_program_fails():
    side_effects = {"modality": True, "area": True, "program": False}

    mock_sel = AsyncMock()
    mock_sel.exists = AsyncMock(return_value=True)
    mock_sel.select = AsyncMock(side_effect=lambda field, **kw: side_effects.get(field, True))

    filler = _make_filler(select_handler=mock_sel)
    result = await filler.fill(_make_ctx())

    assert result is not None
    assert "Programa" in result or "programa" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_name_fails():
    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=False)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=True)

    filler = _make_filler(select_handler=mock_sel, contact_filler=mock_contact)
    result = await filler.fill(_make_ctx())

    assert result is not None
    assert "nombre" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_email_fails():
    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=False)
    mock_contact.set_phone = AsyncMock(return_value=True)

    filler = _make_filler(select_handler=mock_sel, contact_filler=mock_contact)
    result = await filler.fill(_make_ctx())

    assert result is not None
    assert "email" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_phone_fails():
    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=False)

    filler = _make_filler(select_handler=mock_sel, contact_filler=mock_contact)
    result = await filler.fill(_make_ctx())

    assert result is not None
    assert "telefono" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_privacy_fails():
    mock_sel = AsyncMock()
    mock_sel.select = AsyncMock(return_value=True)
    mock_sel.exists = AsyncMock(return_value=True)

    mock_contact = AsyncMock()
    mock_contact.set_name = AsyncMock(return_value=True)
    mock_contact.set_email = AsyncMock(return_value=True)
    mock_contact.set_phone = AsyncMock(return_value=True)

    mock_privacy = AsyncMock()
    mock_privacy.check = AsyncMock(return_value=False)

    filler = _make_filler(select_handler=mock_sel, contact_filler=mock_contact,
                          privacy_handler=mock_privacy)
    result = await filler.fill(_make_ctx())

    assert result is not None
    assert "privacidad" in result.lower()


@pytest.mark.asyncio
async def test_fill_returns_error_when_submit_fails():
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

    filler = _make_filler(
        select_handler=mock_sel, contact_filler=mock_contact,
        privacy_handler=mock_privacy, submitter=mock_submitter,
        detector=mock_detector,
    )
    result = await filler.fill(_make_ctx())

    assert result is not None
    assert "submit" in result.lower()


@pytest.mark.asyncio
async def test_fill_skips_area_when_not_exists():
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

    filler = _make_filler(
        select_handler=mock_sel, contact_filler=mock_contact,
        privacy_handler=mock_privacy, submitter=mock_submitter,
        detector=mock_detector,
    )
    result = await filler.fill(_make_ctx())

    assert result is None


@pytest.mark.asyncio
async def test_fill_program_input_detection():
    """Cuando <input name='program'> existe, se llena como input sin pasar por select."""
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

    mock_searcher = AsyncMock()
    mock_searcher.select_random_program = AsyncMock(return_value=True)

    filler = _make_filler(
        select_handler=mock_sel, contact_filler=mock_contact,
        privacy_handler=mock_privacy, submitter=mock_submitter,
        detector=mock_detector,
    )
    ctx = _make_ctx(tag="INPUT")
    import automation.form.fillers.cms_filler as mod
    with patch.object(mod, "ProgramSearchEngine", return_value=mock_searcher):
        result = await filler.fill(ctx)

    assert result is None
    assert mock_searcher.select_random_program.called
