from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


class ScriptLoader:
    _SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"

    @classmethod
    @lru_cache(maxsize=None)
    def load(cls, name: str) -> str:
        path = cls._SCRIPTS_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Script not found: {path}")
        return path.read_text(encoding="utf-8")

    @classmethod
    async def evaluate(cls, page: Page, script_name: str, arg: Any = None) -> Any:
        js = cls.load(script_name)
        if arg is not None:
            return await page.evaluate(js, arg)
        return await page.evaluate(js)
