"""Logger for masked prompt/response data."""

import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

_logger = logging.getLogger("masking")


def _setup_logger() -> None:
    if _logger.handlers:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "masking.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s\t%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


_setup_logger()


def log_masked_request(
    request_id: str,
    masked_prompt: str,
    pii_count: int,
    pii_placeholders: list[str],
    endpoint: str,
) -> None:
    """Log the masked prompt data (PII-safe: no original values are logged)."""
    record = json.dumps(
        {
            "type": "request",
            "request_id": request_id,
            "endpoint": endpoint,
            "masked_prompt": masked_prompt,
            "pii_count": pii_count,
            "pii_placeholders": pii_placeholders,
        },
        ensure_ascii=False,
    )
    _logger.info(record)


def log_masked_response(
    request_id: str,
    masked_response: str,
    endpoint: str,
) -> None:
    """Log the masked response data (PII-safe: no original values are logged)."""
    record = json.dumps(
        {
            "type": "response",
            "request_id": request_id,
            "endpoint": endpoint,
            "masked_response": masked_response,
        },
        ensure_ascii=False,
    )
    _logger.info(record)
