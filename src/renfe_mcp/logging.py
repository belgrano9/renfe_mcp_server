"""
Application logging configuration for Renfe MCP Server.

Provides structured logging with support for:
- Console output with colors (when available)
- File output for persistent logs
- Correlation IDs for request tracing
- Configurable log levels
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Optional, Any, Callable

from renfe_mcp.config import get_config

# Context variable for request correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get current correlation ID or generate a new one."""
    cid = correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        correlation_id.set(cid)
    return cid


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set correlation ID for current context."""
    if cid is None:
        cid = str(uuid.uuid4())[:8]
    correlation_id.set(cid)
    return cid


class CorrelationFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or "-"
        return True


class ColorFormatter(logging.Formatter):
    """Formatter that adds colors for console output."""

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, fmt: str, datefmt: Optional[str] = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """
    Set up application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        console: Whether to log to console

    Returns:
        Root logger for the application
    """
    config = get_config()
    level = level or config.log_level

    # Get the root logger for our application
    logger = logging.getLogger("renfe_mcp")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Add correlation ID filter
    correlation_filter = CorrelationFilter()

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.addFilter(correlation_filter)

        console_format = "%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s: %(message)s"
        console_handler.setFormatter(ColorFormatter(console_format, datefmt="%H:%M:%S"))
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_handler.addFilter(correlation_filter)

        file_format = "%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
        file_handler.setFormatter(logging.Formatter(file_format))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Logger instance
    """
    # Ensure the name is under our namespace
    if not name.startswith("renfe_mcp"):
        name = f"renfe_mcp.{name}"
    return logging.getLogger(name)


def log_function_call(logger: Optional[logging.Logger] = None):
    """
    Decorator to log function entry and exit.

    Args:
        logger: Logger to use (defaults to function's module logger)
    """
    def decorator(func: Callable) -> Callable:
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate correlation ID if not set
            cid = get_correlation_id()

            # Log entry
            func_name = func.__qualname__
            logger.debug(f"Entering {func_name}")

            try:
                result = func(*args, **kwargs)
                logger.debug(f"Exiting {func_name}")
                return result
            except Exception as e:
                logger.error(f"Exception in {func_name}: {e}", exc_info=True)
                raise

        return wrapper
    return decorator


class LogContext:
    """
    Context manager for structured logging with automatic correlation ID.

    Usage:
        with LogContext("search_trains", origin="Madrid", destination="Barcelona"):
            # ... code that may log ...
            pass
    """

    def __init__(self, operation: str, **context: Any):
        """
        Initialize log context.

        Args:
            operation: Name of the operation being performed
            **context: Additional context to include in logs
        """
        self.operation = operation
        self.context = context
        self.logger = get_logger("context")
        self.start_time = None
        self.cid = None

    def __enter__(self) -> "LogContext":
        self.cid = set_correlation_id()
        self.start_time = datetime.now()

        context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
        self.logger.info(f"Starting {self.operation}: {context_str}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000

        if exc_type is None:
            self.logger.info(f"Completed {self.operation} in {duration_ms:.0f}ms")
        else:
            self.logger.error(
                f"Failed {self.operation} after {duration_ms:.0f}ms: {exc_val}",
                exc_info=True
            )

        # Don't suppress exceptions
        return False

    def log(self, message: str, level: str = "INFO", **extra: Any) -> None:
        """Log a message within this context."""
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        if extra:
            message = f"{message} ({', '.join(f'{k}={v}' for k, v in extra.items())})"
        log_func(message)


# Initialize logging on module load
_initialized = False


def initialize_logging() -> logging.Logger:
    """Initialize application logging (idempotent)."""
    global _initialized
    if not _initialized:
        config = get_config()
        logger = setup_logging(
            level=config.log_level,
            log_file="logs/app.log",
            console=True
        )
        _initialized = True
        return logger
    return get_logger("renfe_mcp")
