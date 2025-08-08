import structlog
import logging
import sys
from typing import Any, Dict


def configure_logging(debug: bool = False) -> None:
    """Configure structured logging"""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if not debug else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive information in logs"""
    sensitive_keys = {"api_key", "token", "password", "secret", "authorization"}
    
    masked_data = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            masked_data[key] = "***MASKED***"
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value)
        else:
            masked_data[key] = value
    
    return masked_data