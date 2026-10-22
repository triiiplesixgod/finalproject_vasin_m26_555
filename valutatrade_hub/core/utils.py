"""Вспомогательные функции: работа с JSON-файлами и валидация входных данных."""

import json
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"


def load_json(file_path: Path, default):
    """Загружает данные из JSON-файла."""
    if not file_path.exists():
        return default
    with open(file_path, encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return default
        return json.loads(content)


def save_json(file_path: Path, data) -> None:
    """Сохраняет данные в JSON-файл с читаемым форматированием."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def validate_amount(amount) -> float:
    """Проверяет, что amount - положительное число, и возвращает его как float."""
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise TypeError("'amount' должен быть числом")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return float(amount)


def validate_currency_code(code: str) -> str:
    """Проверяет код валюты и приводит его к верхнему регистру."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    return code.strip().upper()


def get_next_user_id(users: list[dict]) -> int:
    """Вычисляет следующий свободный user_id."""
    if not users:
        return 1
    return max(user["user_id"] for user in users) + 1


def is_rate_fresh(updated_at: str, max_age_minutes: int = 5) -> bool:
    """Проверяет, что курс обновлялся не позднее max_age_minutes назад."""
    updated_dt = datetime.fromisoformat(updated_at)
    return datetime.now() - updated_dt < timedelta(minutes=max_age_minutes)
