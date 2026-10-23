from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактный базовый класс"""

    def __init__(self, name: str, code: str) -> None:
        self.name = self._validate_name(name)
        self.code = self._validate_code(code)

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Имя валюты не может быть пустым")
        return name.strip()

    @staticmethod
    def _validate_code(code: str) -> str:
        if not isinstance(code, str):
            raise ValueError("Код валюты должен быть строкой")
        normalized = code.strip().upper()
        if not (2 <= len(normalized) <= 5):
            raise ValueError("Код валюты должен содержать от 2 до 5 символов")
        if not normalized.isalpha():
            raise ValueError("Код валюты должен состоять только из букв, без пробелов")
        return normalized

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строковое представление валюты"""
        raise NotImplementedError


class FiatCurrency(Currency):
    """Фиатная валюта"""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name=name, code=code)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта"""

    def __init__(
        self, name: str, code: str, algorithm: str, market_cap: float
    ) -> None:
        super().__init__(name=name, code=code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


_CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency(name="US Dollar", code="USD", issuing_country="United States"),
    "EUR": FiatCurrency(name="Euro", code="EUR", issuing_country="Eurozone"),
    "RUB": FiatCurrency(
        name="Russian Ruble", code="RUB", issuing_country="Russian Federation"
    ),
    "BTC": CryptoCurrency(
        name="Bitcoin", code="BTC", algorithm="SHA-256", market_cap=1.12e12
    ),
    "ETH": CryptoCurrency(
        name="Ethereum", code="ETH", algorithm="Ethash", market_cap=4.5e11
    ),
}


def get_currency(code: str) -> Currency:
    """Возвращает объект валюты по коду"""
    normalized = code.strip().upper()
    currency = _CURRENCY_REGISTRY.get(normalized)
    if currency is None:
        raise CurrencyNotFoundError(code=normalized)
    return currency


def list_supported_codes() -> list[str]:
    """Возвращает список всех поддерживаемых кодов валют"""
    return sorted(_CURRENCY_REGISTRY.keys())