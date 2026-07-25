"""Tests for SelectHandler — uses MockPage."""

import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.asyncio

from automation.form.handlers.select_handler import SelectHandler
from tests.mocks.mock_page import MockPage


@pytest.fixture
def mock_page():
    return MockPage()


@pytest.fixture
def handler(mock_page):
    return SelectHandler(mock_page, mock_page.locator("#form"))


class TestExists:
    async def test_returns_true_when_found(self, handler, mock_page):
        mock_page._elements["select[name='program'], select#program, select[id*='program' i]"] = [MagicMock()]
        assert await handler.exists("program") is True

    async def test_returns_false_when_not_found(self, handler):
        assert await handler.exists("nonexistent") is False


class TestSelect:
    async def test_select_matching_preferred_returns_true(self, handler, mock_page):
        mock_page._elements["select[name='program'], select#program, select[id*='program' i]"] = [MagicMock()]
        from unittest.mock import patch
        from tests.mocks.mock_page import MockLocator
        with patch.object(MockLocator, 'evaluate', return_value={"index": 2, "text": "Licenciatura", "value": "licenciatura", "matched": True}):
            assert await handler.select("program", preferred=["Licenciatura"]) is True

    async def test_select_no_match_returns_false(self, handler, mock_page):
        mock_page._elements["select[name='modality'], select#modality, select[id*='modality' i]"] = [MagicMock()]
        from unittest.mock import patch
        from tests.mocks.mock_page import MockLocator
        with patch.object(MockLocator, 'evaluate', return_value=None):
            result = await handler.select("modality", preferred=["Nope"], require_preferred_match=True)
            assert result is False

    async def test_select_not_found_returns_false(self, handler):
        assert await handler.select("nonexistent", preferred=["x"]) is False


