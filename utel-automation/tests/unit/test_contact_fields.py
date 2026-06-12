"""Tests for ContactFieldFiller — uses MockPage."""

import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.asyncio

from automation.form.contact_fields import ContactFieldFiller
from tests.mocks.mock_page import MockPage


@pytest.fixture
def mock_page():
    return MockPage()


@pytest.fixture
def filler(mock_page):
    return ContactFieldFiller(mock_page, mock_page.locator("#form"))


class TestFirstExisting:
    async def test_finds_first_matching(self, filler, mock_page):
        mock_page._elements["#first_name"] = [MagicMock()]
        loc = await filler._first_existing(["#first_name", "input[name='name']"])
        assert loc is not None

    async def test_returns_none_when_none_exist(self, filler):
        loc = await filler._first_existing(["#nonexistent", "input[name='ghost']"])
        assert loc is None


class TestSetInput:
    async def test_set_input_fills_and_returns_true(self, filler, mock_page):
        mock_page._elements["#email"] = [MagicMock()]
        result = await filler.set_input(["#email"], "test@utel.com", "email")
        assert result is True

    async def test_set_input_field_not_found_returns_false(self, filler):
        result = await filler.set_input(["#ghost"], "value", "ghost")
        assert result is False


class TestConvenience:
    async def test_set_name(self, filler, mock_page):
        mock_page._elements["#first_name"] = [MagicMock()]
        assert await filler.set_name("Juan Pérez") is True

    async def test_set_email(self, filler, mock_page):
        mock_page._elements["#email"] = [MagicMock()]
        assert await filler.set_email("test@utel.com") is True

    async def test_set_phone(self, filler, mock_page):
        mock_page._elements["#phone"] = [MagicMock()]
        assert await filler.set_phone("5512345678") is True
