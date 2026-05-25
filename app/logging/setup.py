from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.settings.paths import LOGS_DIR


def configure_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("lablink")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler = RotatingFileHandler(LOGS_DIR / "app.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)

    crash_handler = RotatingFileHandler(LOGS_DIR / "crash.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    crash_handler.setFormatter(formatter)
    crash_handler.setLevel(logging.ERROR)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(crash_handler)
    logger.addHandler(stream_handler)
    return logger
