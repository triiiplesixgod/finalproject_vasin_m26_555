class ValutaTradeError(Exception):
    """Базовое исключение для всех доменных ошибок приложения"""


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств"""

    def __init__(self, available: float, required: float, code: str) -> None:
        self.available = available
        self.required = required
        self.code = code
        message = (
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )
        super().__init__(message)


class CurrencyNotFoundError(ValutaTradeError):
    """Неизвестная валюта"""

    def __init__(self, code: str) -> None:
        self.code = code
        message = f"Неизвестная валюта '{code}'"
        super().__init__(message)


class ApiRequestError(ValutaTradeError):
    """Сбой внешнего API"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        message = f"Ошибка при обращении к внешнему API: {reason}"
        super().__init__(message)