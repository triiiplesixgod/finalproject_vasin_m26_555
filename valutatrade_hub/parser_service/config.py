import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from valutatrade_hub.infra.settings import SettingsLoader

load_dotenv()


def _default_crypto_id_map() -> dict[str, str]:
    return {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    }


@dataclass
class ParserConfig:
    # Ключ загружается из переменной окружения (.env, не отслеживается git)
    EXCHANGERATE_API_KEY: str | None = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY")
    )

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = field(default_factory=_default_crypto_id_map)

    RATES_FILE_PATH: str = field(
        default_factory=lambda: str(SettingsLoader().rates_file)
    )
    HISTORY_FILE_PATH: str = field(
        default_factory=lambda: str(SettingsLoader().history_file)
    )

    REQUEST_TIMEOUT: int = 10
