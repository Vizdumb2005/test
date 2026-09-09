import logging
import os
import sys
from typing import Optional

import structlog


def setup_logging(log_level: str = "info") -> structlog.BoundLogger:
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=shared_processors
        + [
            (
                structlog.dev.ConsoleRenderer()
                if os.getenv("APP_ENV") != "production"
                else structlog.processors.JSONRenderer()
            ),
        ],
    )

    stdlib_logger = logging.getLogger("enterprise_rag")
    stdlib_logger.handlers = [logging.StreamHandler(sys.stdout)]
    stdlib_logger.handlers[0].setFormatter(formatter)
    stdlib_logger.setLevel(level)
    return structlog.get_logger("enterprise_rag")


logger = setup_logging(os.getenv("LOG_LEVEL", "info"))


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
