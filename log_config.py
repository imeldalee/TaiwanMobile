import logging
import sys
from typing import Optional

ROOT_LOGGER_NAME = "task_scheduler"


def get_logger(module_name):
    """Return a child logger under the application root."""
    return logging.getLogger("{}.{}".format(ROOT_LOGGER_NAME, module_name))


def setup_logging(level=logging.INFO, name=None):
    """
    Configure the root application logger once.
    Child modules should use get_logger(__name__ suffix).
    """
    logger_name = name or ROOT_LOGGER_NAME
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger


def log_with_context(logger, level, message, **context):
    """Append traceable key=value context to a log message."""
    if context:
        suffix = " | " + " ".join(
            "{}={}".format(key, value) for key, value in sorted(context.items())
        )
        message = "{}{}".format(message, suffix)
    logger.log(level, message)


def log_exception(logger, message, exc=None, **context):
    """Log an exception with consistent context fields."""
    log_with_context(logger, logging.ERROR, message, **context)
    if exc is not None:
        logger.exception("[%s] %s", exc.code if hasattr(exc, "code") else "ERROR", exc)
