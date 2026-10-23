from valutatrade_hub.core.utils import load_json, save_json
from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._settings = SettingsLoader()
        self._initialized = True

    def load_users(self) -> list[dict]:
        return load_json(self._settings.users_file, default=[])

    def save_users(self, users: list[dict]) -> None:
        save_json(self._settings.users_file, users)

    def load_portfolios(self) -> list[dict]:
        return load_json(self._settings.portfolios_file, default=[])

    def save_portfolios(self, portfolios: list[dict]) -> None:
        save_json(self._settings.portfolios_file, portfolios)

    def load_rates(self) -> dict:
        return load_json(self._settings.rates_file, default={})

    def save_rates(self, rates: dict) -> None:
        save_json(self._settings.rates_file, rates)
