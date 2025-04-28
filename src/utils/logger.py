import logging
import os
import sys
from src.config.settings import settings


class CustomFormatter(logging.Formatter):
    """Custom formatter for logs"""

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    format_template = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format_template + reset,
        logging.INFO: grey + format_template + reset,
        logging.WARNING: yellow + format_template + reset,
        logging.ERROR: red + format_template + reset,
        logging.CRITICAL: bold_red + format_template + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logger(name: str) -> logging.Logger:
    """
    Configures a custom logger

    Args:
        name: Logger name

    Returns:
        logging.Logger: Logger configurado
    """
    logger = logging.getLogger(name)

    # Remove existing handlers to avoid duplication
    if logger.handlers:
        logger.handlers.clear()

    # Configure the logger level based on the environment variable or configuration
    log_level = getattr(logging, os.getenv("LOG_LEVEL", settings.LOG_LEVEL).upper())
    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter())
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    # Prevent logs from being propagated to the root logger
    logger.propagate = False

    return logger
