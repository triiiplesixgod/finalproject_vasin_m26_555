import logging
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3 

_configured = False


def setup_logging(verbose: bool = False) -> logging.Logger:
    global _configured

    settings = SettingsLoader()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("valutatrade_hub")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not _configured:
        handler = RotatingFileHandler(
            filename=settings.log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        _configured = True

    return logger