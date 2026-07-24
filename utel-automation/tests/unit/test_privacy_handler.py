"""Tests unitarios para PrivacyHandler.

Valida que dispatch_event("click") marque el checkbox en input[type='checkbox']
oculto (Chakra), y que la ausencia de checkbox retorne False.
"""

import pytest

from automation.form.handlers.privacy_handler import PrivacyHandler
from tests.mocks.mock_page import MockElement, MockPage


@pytest.mark.asyncio
async def test_dispatch_event_marks_checkbox():
    """dispatch_event("click") en input[type='checkbox'] debe marcar el checkbox."""
    page = MockPage()
    page._elements["input[type='checkbox']"] = [MockElement()]
    form_scope = page.locator("#scope")

    handler = PrivacyHandler(page, form_scope)
    result = await handler.check()

    assert result is True
    assert page._checkbox_checked is True


@pytest.mark.asyncio
async def test_no_checkbox_returns_false():
    """Sin checkbox input ni candidatos visuales, debe retornar False."""
    page = MockPage()
    form_scope = page.locator("#scope")

    handler = PrivacyHandler(page, form_scope)
    result = await handler.check()

    assert result is False
