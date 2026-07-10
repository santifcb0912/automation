

from core.fake_data.interfaces import INameProvider, IPhoneProvider


class FakeDataService:

    # Inicializa el servicio con los providers de nombres y teléfonos.
    def __init__(
        self,
        name_provider: INameProvider,
        phone_provider: IPhoneProvider,
    ):
        self._name_provider = name_provider
        self._phone_provider = phone_provider

    # Retorna un nombre aleatorio de la pool global.
    def get_name(self) -> str:
        return self._name_provider.get_name()

    # Retorna un teléfono aleatorio del país indicado.
    def get_phone(self, country_id: str) -> str:
        return self._phone_provider.get_phone(country_id)
