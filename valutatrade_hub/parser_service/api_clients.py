import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    SOURCE_NAME: str = ""

    @abstractmethod
    def fetch_rates(self) -> dict[str, dict]:
        raise NotImplementedError


class CoinGeckoClient(BaseApiClient):
    SOURCE_NAME: str = "CoinGecko"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self._config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, dict]:
        config = self._config
        id_map = config.CRYPTO_ID_MAP
        codes = config.CRYPTO_CURRENCIES

        ids = [id_map[code] for code in codes if code in id_map]
        if not ids:
            raise ApiRequestError(reason="не задан ни один идентификатор CoinGecko")

        params = {
            "ids": ",".join(ids),
            "vs_currencies": config.BASE_CURRENCY.lower(),
        }

        start = time.perf_counter()
        try:
            response = requests.get(
                config.COINGECKO_URL, params=params, timeout=config.REQUEST_TIMEOUT
            )
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(reason=f"CoinGecko недоступен: {exc}") from exc
        request_ms = round((time.perf_counter() - start) * 1000, 2)

        if response.status_code != 200:
            raise ApiRequestError(
                reason=f"CoinGecko вернул статус {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ApiRequestError(reason="CoinGecko вернул некорректный JSON") from exc

        base_key = config.BASE_CURRENCY.lower()
        id_to_code = {v: k for k, v in id_map.items()}
        etag = response.headers.get("ETag")
        status_code = response.status_code

        result: dict[str, dict] = {}
        for coin_id, values in data.items():
            code = id_to_code.get(coin_id)
            if code is None or base_key not in values:
                continue
            result[f"{code}_{config.BASE_CURRENCY}"] = {
                "rate": float(values[base_key]),
                "raw_id": coin_id,
                "status_code": status_code,
                "request_ms": request_ms,
                "etag": etag,
            }

        if not result:
            raise ApiRequestError(reason="CoinGecko не вернул ни одного курса")

        return result


class ExchangeRateApiClient(BaseApiClient):
    SOURCE_NAME: str = "ExchangeRate-API"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self._config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, dict]:
        config = self._config

        if not config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                reason="не задан EXCHANGERATE_API_KEY (переменная окружения)"
            )

        url = (
            f"{config.EXCHANGERATE_API_URL}/{config.EXCHANGERATE_API_KEY}"
            f"/latest/{config.BASE_CURRENCY}"
        )

        start = time.perf_counter()
        try:
            response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(reason=f"ExchangeRate-API недоступен: {exc}") from exc
        request_ms = round((time.perf_counter() - start) * 1000, 2)

        if response.status_code == 429:
            raise ApiRequestError(
                reason="превышен лимит запросов к ExchangeRate-API (429)"
            )
        if response.status_code != 200:
            raise ApiRequestError(
                reason=f"ExchangeRate-API вернул статус {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ApiRequestError(
                reason="ExchangeRate-API вернул некорректный JSON"
            ) from exc

        if data.get("result") != "success":
            error_type = data.get("error-type", "unknown-error")
            raise ApiRequestError(
                reason=f"ExchangeRate-API сообщил об ошибке: {error_type}"
            )

        rates = data.get("conversion_rates", {})
        etag = response.headers.get("ETag")
        status_code = response.status_code

        result: dict[str, dict] = {}
        for code in config.FIAT_CURRENCIES:
            if code in rates:
                result[f"{code}_{config.BASE_CURRENCY}"] = {
                    "rate": float(rates[code]),
                    "raw_id": None,
                    "status_code": status_code,
                    "request_ms": request_ms,
                    "etag": etag,
                }

        if not result:
            raise ApiRequestError(
                reason="ExchangeRate-API не вернул ни одного нужного курса"
            )

        return result
