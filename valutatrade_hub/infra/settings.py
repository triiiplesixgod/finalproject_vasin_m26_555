from pathlib import Path

class SettingsLoader:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self.project_root: Path = Path(__file__).resolve().parents[2]
        self.data_dir: Path = self.project_root / "data"
        self.users_file: Path = self.data_dir / "users.json"
        self.portfolios_file: Path = self.data_dir / "portfolios.json"
        self.rates_file: Path = self.data_dir / "rates.json"

        self.logs_dir: Path = self.project_root / "logs"
        self.log_file: Path = self.logs_dir / "actions.log"

        self.rates_ttl_seconds: int = 300
        self.default_base_currency: str = "USD"

        self._initialized = True