"""Centralized logging configuration with console, file, and Langfuse outputs."""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from backend.config.settings import settings
from backend.src.utils.langfuse_setup import get_langfuse_client


class LangfuseHandler(logging.Handler):
    """Logging handler that sends logs to Langfuse as trace events."""

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = get_langfuse_client()
        return self._client

    def emit(self, record: logging.LogRecord) -> None:
        client = self._get_client()
        if client is None:
            return

        try:
            trace_id = getattr(record, "trace_id", None)
            if trace_id:
                client.trace(id=trace_id, name=record.name, metadata={
                    "level": record.levelname,
                    "message": self.format(record),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                })
        except Exception:
            pass


def setup_logger(
    name: str = "hr_ops",
    log_level: str | None = None,
    log_file: str | None = None,
    enable_langfuse: bool = True,
) -> logging.Logger:
    """Configure and return a logger with console, file, and optional Langfuse handlers.

    Args:
        name: Logger name (used for logger hierarchy).
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR). Defaults to settings.log_level.
        log_file: Path to log file. Defaults to settings.log_file.
        enable_langfuse: Whether to add Langfuse handler.

    Returns:
        Configured logger instance.
    """
    level = getattr(logging, (log_level or settings.log_level).upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is None:
        log_file = settings.log_file
    log_dir = Path(log_file).parent
    log_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10_485_760,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if enable_langfuse and settings.langfuse_public_key and settings.langfuse_secret_key:
        langfuse_handler = LangfuseHandler(level=level)
        langfuse_handler.setFormatter(formatter)
        logger.addHandler(langfuse_handler)

    logger.propagate = False
    return logger


def get_logger(name: str = "hr_ops") -> logging.Logger:
    """Get or create a logger instance with default configuration."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


logger = setup_logger()