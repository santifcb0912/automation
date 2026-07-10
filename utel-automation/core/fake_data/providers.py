import json
import random
from pathlib import Path
from typing import Optional

from core.fake_data.interfaces import INameProvider, IPhoneProvider

# Ruta al JSON con lista plana de nombres (misma pool para todos los países).
NAMES_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "data" / "names.json"

# Ruta al JSON con plantillas de teléfonos con formato local por país.
PHONES_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "data" / "phones.json"


class RandomNameProvider(INameProvider):

    # Configura la ruta al JSON de nombres planos.
    def __init__(self, names_file: Optional[Path] = None):
        self._names_file = names_file or NAMES_FILE
        self._names: list[str] = []
        self._loaded = False

    # Retorna un nombre al azar de la pool global (independiente del país).
    def get_name(self) -> str:
        self._ensure_loaded()
        if self._names:
            return random.choice(self._names)
        return ""

    # Carga la lista plana de nombres desde el archivo JSON.
    def _ensure_loaded(self):
        if self._loaded:
            return
        if self._names_file.exists():
            try:
                with open(self._names_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._names = data if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                self._names = []
        self._loaded = True


class RandomPhoneProvider(IPhoneProvider):

    # Configura la ruta al JSON de teléfonos. Usa el archivo por defecto si no se especifica otro.
    def __init__(self, phones_file: Optional[Path] = None):
        self._phones_file = phones_file or PHONES_FILE
        self._templates: dict[str, str] = {}
        self._loaded = False

    # Retorna un teléfono aleatorio del país indicado. Si no hay template, retorna vacío.
    def get_phone(self, country_id: str) -> str:
        self._ensure_loaded()
        template = self._templates.get(country_id)
        if template:
            return self._generate_from_template(template)
        return ""

    # Carga las plantillas de teléfonos desde el archivo JSON si no están cargadas.
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

    # Genera un número telefónico aleatorio a partir de una plantilla de teléfono.
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
