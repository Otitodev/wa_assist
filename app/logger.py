"""
Structured logging configuration for HybridFlow.
Outputs JSON-formatted logs with contextual information.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON.
    Includes contextual fields like tenant_id, chat_id, message_id when available.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: LogRecord instance

        Returns:
            JSON string with log data
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add contextual fields if present
        contextual_fields = [
            "tenant_id",
            "chat_id",
            "message_id",
            "instance",
            "event",
            "action",
            "provider",
            "model",
            "duration_ms",
            "error_type",
        ]

        for field in contextual_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record.__dict__
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, default=str)


def setup_logger(
    name: str = "hybridflow",
    level: str = "INFO",
    enable_json: bool = True
) -> logging.Logger:
    """
    Set up and configure a logger instance.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_json: If True, use JSON formatter; if False, use standard formatter

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter
    if enable_json:
        formatter = JSONFormatter()
    else:
        # Standard formatter for local development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Create default logger instance
# Log level will be set from config when imported
logger = logging.getLogger("hybridflow")


def configure_logger_from_config():
    """
    Configure logger using settings from config module.
    Call this after config is loaded.
    """
    try:
        from .config import LOG_LEVEL
        level = LOG_LEVEL.upper()
    except ImportError:
        level = "INFO"

    global logger
    logger = setup_logger(level=level)


def log_with_context(
    level: str,
    message: str,
    tenant_id: Optional[int] = None,
    chat_id: Optional[str] = None,
    message_id: Optional[str] = None,
    instance: Optional[str] = None,
    event: Optional[str] = None,
    action: Optional[str] = None,
    **kwargs
):
    """
    Log a message with contextual fields.

    Args:
        level: Log level (info, warning, error, debug)
        message: Log message
        tenant_id: Tenant ID
        chat_id: WhatsApp chat ID
        message_id: Message ID
        instance: Instance name
        event: Event type
        action: Action taken
        **kwargs: Additional contextual fields
    """
    extra = {}

    if tenant_id is not None:
        extra["tenant_id"] = tenant_id
    if chat_id is not None:
        extra["chat_id"] = chat_id
    if message_id is not None:
        extra["message_id"] = message_id
    if instance is not None:
        extra["instance"] = instance
    if event is not None:
        extra["event"] = event
    if action is not None:
        extra["action"] = action

    # Add any additional kwargs as extra fields
    extra.update(kwargs)

    log_func = getattr(logger, level.lower())
    log_func(message, extra=extra)


# Convenience functions
def log_info(message: str, **kwargs):
    """Log info message with context"""
    log_with_context("info", message, **kwargs)


def log_warning(message: str, **kwargs):
    """Log warning message with context"""
    log_with_context("warning", message, **kwargs)


def log_error(message: str, exc_info=False, **kwargs):
    """Log error message with context"""
    if exc_info:
        logger.error(message, exc_info=True, extra=kwargs)
    else:
        log_with_context("error", message, **kwargs)


def log_debug(message: str, **kwargs):
    """Log debug message with context"""
    log_with_context("debug", message, **kwargs)
