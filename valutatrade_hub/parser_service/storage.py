import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from valutatrade_hub.parser_service.config import ParserConfig


def format_utc_timestamp(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_record_id(
    from_currency: str, to_currency: str, timestamp: datetime
) -> str:
    ts = format_utc_timestamp(timestamp)
    return f"{from_currency.upper()}_{to_currency.upper()}_{ts}"


def _atomic_write_json(file_path: Path, data: object) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=file_path.parent, prefix=f".{file_path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
        os.replace(tmp_path, file_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


class RatesStorage:

    def __init__(self, config: ParserConfig | None = None) -> None:
        self._config = config or ParserConfig()
        self._rates_file = Path(self._config.RATES_FILE_PATH)
        self._history_file = Path(self._config.HISTORY_FILE_PATH)

    # текущий снимок курсов

    def load_rates_snapshot(self) -> dict:
        if not self._rates_file.exists():
            return {"pairs": {}, "last_refresh": None}

        content = self._rates_file.read_text(encoding="utf-8").strip()
        if not content:
            return {"pairs": {}, "last_refresh": None}

        data = json.loads(content)
        data.setdefault("pairs", {})
        data.setdefault("last_refresh", None)
        return data

    def save_rates_snapshot(self, data: dict) -> None:
        """Атомарно сохраняет снимок курсов целиком"""
        _atomic_write_json(self._rates_file, data)

    def update_rates_snapshot(
        self, new_pairs: dict[str, dict], refreshed_at: datetime | None = None
    ) -> dict:
        snapshot = self.load_rates_snapshot()
        pairs = snapshot["pairs"]

        for pair_key, pair_data in new_pairs.items():
            existing = pairs.get(pair_key)
            if existing is None or pair_data["updated_at"] >= existing["updated_at"]:
                pairs[pair_key] = pair_data

        snapshot["pairs"] = pairs
        snapshot["last_refresh"] = format_utc_timestamp(
            refreshed_at or datetime.now(timezone.utc)
        )
        self.save_rates_snapshot(snapshot)
        return snapshot

    # журнал истории

    def load_history(self) -> list[dict]:
        if not self._history_file.exists():
            return []

        content = self._history_file.read_text(encoding="utf-8").strip()
        if not content:
            return []

        return json.loads(content)

    def append_history_records(self, records: list[dict]) -> int:
        """Добавляет новые записи в историю, избегая дублей по id"""
        history = self.load_history()
        existing_ids = {item["id"] for item in history}

        new_records = [r for r in records if r["id"] not in existing_ids]
        if not new_records:
            return 0

        history.extend(new_records)
        _atomic_write_json(self._history_file, history)
        return len(new_records)