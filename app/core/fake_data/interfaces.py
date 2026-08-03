from typing import Protocol


class INameProvider(Protocol):
    # Retorna un nombre aleatorio de la pool global
    def get_name(self) -> str: ...


class IPhoneProvider(Protocol):
    # Retorna un telefono aleatorio del pais indicado
    def get_phone(self, country_id: str) -> str: ...
