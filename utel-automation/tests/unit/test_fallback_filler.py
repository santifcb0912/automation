"""Tests for FallbackFiller — no depende de MockPage (no usa Playwright)."""

import pytest

pytestmark = pytest.mark.asyncio

from automation.form.contracts.i_form_filler import IFormFiller
from automation.form.contracts.fill_context import FillContext
from automation.form.fillers.fallback_filler import FallbackFiller


def _make_ctx() -> FillContext:
    """Crea un FillContext mínimo. FallbackFiller lo ignora."""
    from tests.mocks.mock_page import MockPage
    page = MockPage()
    return FillContext(
        form_scope=page.locator("#scope"),
        level="Maestria",
        raw_level="Maestría",
        test_email="test@utel.com",
        fake_name="Juan Pérez",
        fake_phone="5512345678",
    )


class TestReturnsReason:
    async def test_returns_exact_reason(self):
        filler = FallbackFiller("Strategy no implementada para pais: colombia")
        result = await filler.fill(_make_ctx())
        assert result == "Strategy no implementada para pais: colombia"

    async def test_returns_empty_reason(self):
        filler = FallbackFiller("")
        result = await filler.fill(_make_ctx())
        assert result == ""

    async def test_multiple_calls_return_same_reason(self):
        filler = FallbackFiller("error persistente")
        r1 = await filler.fill(_make_ctx())
        r2 = await filler.fill(_make_ctx())
        assert r1 == r2 == "error persistente"


class TestImplementsIFormFiller:
    async def test_is_iform_filler_structural(self):
        """Verifica tipado estructural: FallbackFiller cumple el Protocol."""
        filler: IFormFiller = FallbackFiller("x")
        result = await filler.fill(_make_ctx())
        assert result == "x"

    async def test_has_fill_method_with_correct_signature(self):
        filler = FallbackFiller("x")
        assert hasattr(filler, "fill")
        assert callable(filler.fill)


class TestIgnoresContext:
    async def test_result_independent_of_level(self):
        filler = FallbackFiller("err")
        ctx1 = _make_ctx()
        ctx1.level = "Licenciatura"
        ctx2 = _make_ctx()
        ctx2.level = "Doctorado"
        assert await filler.fill(ctx1) == await filler.fill(ctx2)

    async def test_result_independent_of_email(self):
        filler = FallbackFiller("err")
        ctx1 = _make_ctx()
        ctx1.test_email = "a@b.com"
        ctx2 = _make_ctx()
        ctx2.test_email = "c@d.com"
        assert await filler.fill(ctx1) == await filler.fill(ctx2)

    async def test_result_independent_of_scope(self):
        filler = FallbackFiller("err")
        from tests.mocks.mock_page import MockPage
        ctx1 = _make_ctx()
        ctx1.form_scope = MockPage().locator("#form1")
        ctx2 = _make_ctx()
        ctx2.form_scope = MockPage().locator("#form2")
        assert await filler.fill(ctx1) == await filler.fill(ctx2)
