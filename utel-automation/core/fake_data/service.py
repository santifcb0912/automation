"""FakeDataService — facade para generación de datos ficticios.

Sigue el principio de responsabilidad única (SRP):
- Coordina la generación de nombres, teléfonos y otros datos
- Delega la lógica específica a los providers correspondientes
- Fácil de extender (OCP): agregar un nuevo provider no modifica el código existente
"""

from core.fake_data.interfaces import INameProvider, IPhoneProvider


class FakeDataService:
    def __init__(
        self,
        name_provider: INameProvider,
        phone_provider: IPhoneProvider,
    ):
        self._name_provider = name_provider
        self._phone_provider = phone_provider

    def get_name(self, country_id: str, fallback: str = "") -> str:
        return self._name_provider.get_name(country_id, fallback)

    def get_phone(self, country_id: str, fallback: str = "") -> str:
        return self._phone_provider.get_phone(country_id, fallback)
