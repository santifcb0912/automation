import json
import random
from pathlib import Path
from typing import Optional

from core.fake_data.interfaces import INameProvider, IPhoneProvider

NAMES_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "data" / "names.json"
PHONES_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "data" / "phones.json"


class RandomNameProvider(INameProvider):
    def __init__(self, names_file: Optional[Path] = None):
        self._names_file = names_file or NAMES_FILE
        self._data: dict[str, list[str]] = {}
        self._loaded = False

    def get_name(self, country_id: str, fallback: str = "") -> str:
        self._ensure_loaded()
        names = self._data.get(country_id)
        if names:
            return random.choice(names)
        return fallback

    def _ensure_loaded(self):
        if self._loaded:
            return
        if self._names_file.exists():
            try:
                with open(self._names_file, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._loaded = True


class RandomPhoneProvider(IPhoneProvider):
    def __init__(self, phones_file: Optional[Path] = None):
        self._phones_file = phones_file or PHONES_FILE
        self._templates: dict[str, str] = {}
        self._loaded = False

    def get_phone(self, country_id: str, fallback: str = "") -> str:
        self._ensure_loaded()
        template = self._templates.get(country_id)
        if template:
            return self._generate_from_template(template)
        return fallback

    def _ensure_loaded(self):
        if self._loaded:
            return
        if self._phones_file.exists():
            try:
                with open(self._phones_file, encoding="utf-8") as f:
                    self._templates = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._templates = {}
        self._loaded = True

    @staticmethod
    def _generate_from_template(template: str) -> str:
        result: list[str] = []
        i = 0
        while i < len(template):
            ch = template[i]
            if ch == "(":
                end = template.index(")", i)
                options = template[i + 1 : end].split("|")
                result.append(random.choice(options))
                i = end + 1
            elif ch == "#":
                result.append(str(random.randint(0, 9)))
                i += 1
            else:
                result.append(ch)
                i += 1
        return "".join(result)
