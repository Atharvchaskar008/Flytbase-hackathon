import logging
import sys
import os


def setup_logger(name: str = "trace") -> logging.Logger:
    """Setup logger with configuration"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    # Get log level from environment or default to INFO
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger.setLevel(log_level)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = setup_logger()
