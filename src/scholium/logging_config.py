"""Operational events only; no file logs or manuscript text."""

import logging


def configure() -> logging.Logger:
    logger = logging.getLogger("scholium")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("scholium: %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    return logger
