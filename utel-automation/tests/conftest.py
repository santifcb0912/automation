"""Fixtures compartidos para todos los tests."""

import pytest
from pytest_mock import MockerFixture

from config.countries import Country, COUNTRIES
from tests.mocks.mock_page import MockPage


@pytest.fixture
def mock_page():
    return MockPage()


@pytest.fixture
def mock_country():
    return COUNTRIES[0]  # Mexico


@pytest.fixture
def sample_lead():
    from core.models import LeadRow
    return LeadRow(
        row_number=5,
        country_name="Mexico",
        nivel="Maestría",
        landing_url="https://utel.edu.mx/maestrias-online",
        form_type="FormLP",
        cliente="Test",
    )
