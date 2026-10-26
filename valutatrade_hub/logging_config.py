import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(levelname)s %(asctime)s %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"

_configured = False
_parser_configured = False


def _build_file_handler(file_path: Path) -> RotatingFileHandler:
    """Создаёт настроенный файловый хендлер с ротацией"""
    handler = RotatingFileHandler(
        filename=file_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATEFMT)
    handler.setFormatter(formatter)
    return handler


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Настраивает основной логгер приложения"""
    global _configured

    settings = SettingsLoader()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("valutatrade_hub")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not _configured:
        logger.addHandler(_build_file_handler(settings.log_file))
        _configured = True

    return logger


def setup_parser_logging(verbose: bool = False) -> logging.Logger:
    """Настраивает отдельный логгер Parser Service"""
    global _parser_configured

    settings = SettingsLoader()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("valutatrade_hub.parser_service")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False

    if not _parser_configured:
        logger.addHandler(_build_file_handler(settings.parser_log_file))
        _parser_configured = True

    return logger