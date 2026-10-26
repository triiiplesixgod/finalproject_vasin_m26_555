from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import setup_parser_logging
from valutatrade_hub.parser_service.api_clients import BaseApiClient
from valutatrade_hub.parser_service.storage import (
    RatesStorage,
    format_utc_timestamp,
    generate_record_id,
)

logger = setup_parser_logging()


class RatesUpdater:
    def __init__(
        self, clients: list[BaseApiClient], storage: RatesStorage | None = None
    ) -> None:
        self._clients = clients
        self._storage = storage or RatesStorage()

    def run_update(self) -> dict:
        now = datetime.now(timezone.utc)
        timestamp = format_utc_timestamp(now)

        all_rates: dict[str, dict] = {}
        succeeded_sources: list[str] = []
        failed_sources: list[str] = []

        for client in self._clients:
            source_name = client.SOURCE_NAME or type(client).__name__
            logger.info("Запрашиваю курсы у источника '%s'...", source_name)

            try:
                rates = client.fetch_rates()
            except ApiRequestError as exc:
                logger.error("Источник '%s' недоступен: %s", source_name, exc)
                failed_sources.append(source_name)
                continue

            logger.info(
                "Источник '%s' вернул %d курс(ов): %s",
                source_name,
                len(rates),
                ", ".join(rates.keys()),
            )
            succeeded_sources.append(source_name)

            for info in rates.values():
                info["source"] = source_name
            all_rates.update(rates)

        if not all_rates:
            logger.warning(
                "Ни один источник не вернул курсы. Обновление пропущено. "
                "Упавшие источники: %s",
                ", ".join(failed_sources) or "нет",
            )
            return {
                "updated_pairs": 0,
                "new_history_records": 0,
                "succeeded_sources": succeeded_sources,
                "failed_sources": failed_sources,
            }

        snapshot_pairs: dict[str, dict] = {}
        history_records: list[dict] = []

        for pair_key, info in all_rates.items():
            from_currency, to_currency = pair_key.split("_")
            rate = info["rate"]
            source_name = info["source"]

            snapshot_pairs[pair_key] = {
                "rate": rate,
                "updated_at": timestamp,
                "source": source_name,
            }

            record_id = generate_record_id(from_currency, to_currency, now)
            history_records.append(
                {
                    "id": record_id,
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "rate": rate,
                    "timestamp": timestamp,
                    "source": source_name,
                    "meta": {
                        "raw_id": info.get("raw_id"),
                        "request_ms": info.get("request_ms"),
                        "status_code": info.get("status_code"),
                        "etag": info.get("etag"),
                    },
                }
            )

        self._storage.update_rates_snapshot(snapshot_pairs, refreshed_at=now)
        added_count = self._storage.append_history_records(history_records)

        logger.info(
            "Обновление завершено: %d пар(ы) в снимке, %d новых записей в "
            "истории. Успешные источники: %s. Упавшие источники: %s.",
            len(snapshot_pairs),
            added_count,
            ", ".join(succeeded_sources) or "нет",
            ", ".join(failed_sources) or "нет",
        )

        return {
            "updated_pairs": len(snapshot_pairs),
            "new_history_records": added_count,
            "succeeded_sources": succeeded_sources,
            "failed_sources": failed_sources,
        }