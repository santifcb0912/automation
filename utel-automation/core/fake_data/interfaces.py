from typing import Protocol


class INameProvider(Protocol):
    def get_name(self, country_id: str, fallback: str = "") -> str: ...


class IPhoneProvider(Protocol):
    def get_phone(self, country_id: str, fallback: str = "") -> str: ...
