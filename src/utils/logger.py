import logging
import os
import sys
from typing import Optional
from src.config.settings import settings

class CustomFormatter(logging.Formatter):
    """Formatação personalizada para logs"""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    format_template = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format_template + reset,
        logging.INFO: grey + format_template + reset,
        logging.WARNING: yellow + format_template + reset,
        logging.ERROR: red + format_template + reset,
        logging.CRITICAL: bold_red + format_template + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logger(name: str) -> logging.Logger:
    """
    Configura um logger personalizado
    
    Args:
        name: Nome do logger
    
    Returns:
        logging.Logger: Logger configurado
    """
    logger = logging.getLogger(name)
    
    # Remove handlers existentes para evitar duplicação
    if logger.handlers:
        logger.handlers.clear()
    
    # Configura o nível do logger baseado na variável de ambiente ou configuração
    log_level = getattr(logging, os.getenv("LOG_LEVEL", settings.LOG_LEVEL).upper())
    logger.setLevel(log_level)
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter())
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)
    
    # Impede que os logs sejam propagados para o logger root
    logger.propagate = False
    
    return logger 