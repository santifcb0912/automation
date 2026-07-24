"""Mock de Playwright Page para tests unitarios.

Implementa las partes de Page que usan los componentes refactorizados,
pero sin navegador real. Permite testear la lógica de selección,
fill y submit sin Playwright.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock


@dataclass
class MockElement:
    tag: str = "input"
    attrs: dict = field(default_factory=dict)
    value: str = ""
    checked: bool = False
    visible: bool = True
    rect: dict = field(default_factory=lambda: {"x": 0, "y": 0, "width": 100, "height": 30})


class MockPage:
    """Simula una Page de Playwright para tests unitarios."""

    def __init__(self):
        self.url = "https://example.com"
        self._elements: dict[str, list[MockElement]] = {}
        self._selected_values: dict[str, str] = {}
        self._checkbox_checked: bool = False
        self._evaluate_results: dict[str, Any] = {}
        self._select_options: dict[str, list[str]] = {}

        # AsyncMock para métodos de Playwright no implementados
        self.goto = AsyncMock()
        self.wait_for_timeout = AsyncMock()
        self.wait_for_load_state = AsyncMock()
        self.wait_for_selector = AsyncMock()
        self.close = AsyncMock()
        self.content = AsyncMock(return_value="<html></html>")
        self.reload = AsyncMock()
        self.wait_for_timeout = AsyncMock()
        self.wait_for_function = AsyncMock()
        self.keyboard = MagicMock()
        self.keyboard.press = AsyncMock()
        self.keyboard.type = AsyncMock()
        self.mouse = MagicMock()
        self.mouse.click = AsyncMock()
        self.mouse.move = AsyncMock()
        self.mouse.down = AsyncMock()
        self.mouse.up = AsyncMock()
        self.mouse.wheel = AsyncMock()
        self.viewport_size = {"width": 1366, "height": 768}

    def mock_select(self, name: str, options: list[str], selected: str = ""):
        """Configura un <select> simulado con opciones."""
        self._select_options[name] = options
        self._selected_values[name] = selected

    def mock_evaluate(self, key: str, return_value: Any):
        """Configura un valor de retorno para page.evaluate."""
        self._evaluate_results[key] = return_value

    def selected_value(self, name: str) -> str:
        return self._selected_values.get(name, "")

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        if expression in self._evaluate_results:
            return self._evaluate_results[expression]
        return self._evaluate_results.get(expression[:80], None)

    async def query_selector(self, selector: str) -> Optional[Any]:
        return MagicMock() if selector in self._elements else None

    async def query_selector_all(self, selector: str) -> list:
        return self._elements.get(selector, [])

    def locator(self, selector: str) -> "MockLocator":
        return MockLocator(self, selector)

    @property
    def page(self):
        return self


class MockLocator:
    """Simula un Locator de Playwright."""

    def __init__(self, page: MockPage, selector: str):
        self._page = page
        self._selector = selector
        self.first = self
        self._evaluate_result: Any = None
        self._filled_value: str = ""

    def mock_evaluate(self, return_value: Any):
        self._evaluate_result = return_value

    def locator(self, selector: str) -> "MockLocator":
        return MockLocator(self._page, selector)

    async def count(self) -> int:
        return 1 if self._selector in self._page._elements else 0

    async def is_visible(self) -> bool:
        return True

    async def click(self, **kwargs):
        pass

    async def dispatch_event(self, action: str):
        if action == "click":
            self._page._checkbox_checked = True

    async def fill(self, value: str, **kwargs):
        self._filled_value = value

    async def scroll_into_view_if_needed(self, **kwargs):
        pass

    async def bounding_box(self) -> Optional[dict]:
        return {"x": 0, "y": 0, "width": 100, "height": 30}

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        if self._evaluate_result is not None:
            return self._evaluate_result
        if "querySelector" in expression and "checkbox" in expression:
            return self._page._checkbox_checked
        # First try exact match, then truncated prefix match
        if expression in self._page._evaluate_results:
            return self._page._evaluate_results[expression]
        return self._page._evaluate_results.get(expression[:80], None)

    async def input_value(self, **kwargs) -> str:
        return getattr(self, '_filled_value', '')

    async def inner_text(self, **kwargs) -> str:
        return ""

    async def press(self, key: str, **kwargs):
        pass

    async def type(self, text: str, **kwargs):
        pass

    def nth(self, index: int):
        return self

    async def element_handle(self) -> Any:
        return MagicMock()
