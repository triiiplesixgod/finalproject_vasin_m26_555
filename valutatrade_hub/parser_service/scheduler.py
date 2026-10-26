import time

from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import setup_parser_logging
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = setup_parser_logging()


def run_scheduler(interval_seconds: int | None = None) -> None:
    if interval_seconds is None:
        interval_seconds = SettingsLoader().rates_ttl_seconds

    updater = RatesUpdater(
        clients=[CoinGeckoClient(), ExchangeRateApiClient()],
        storage=RatesStorage(),
    )

    logger.info(
        "Scheduler запущен. Интервал обновления: %d секунд.", interval_seconds
    )

    try:
        while True:
            summary = updater.run_update()
            logger.info("Очередной цикл обновления завершён: %s", summary)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Scheduler остановлен пользователем (Ctrl+C).")


if __name__ == "__main__":
    run_scheduler()