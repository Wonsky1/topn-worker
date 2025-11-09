"""Centralized logging configuration for the topn-worker application.

This module provides a unified logging setup with:
- Console output for real-time monitoring
- Rotating file logs for persistence
- Structured log format with timestamps
- Configurable log levels via environment variables
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    log_filename: str = "topn_worker.log",
    rotation_when: str = "midnight",
    rotation_interval: int = 1,
    backup_count: int = 30,
    console_output: bool = True,
) -> logging.Logger:
    """Configure application-wide logging with file rotation and console output.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files. If None, uses current directory
        log_filename: Name of the log file
        rotation_when: When to rotate logs ('S', 'M', 'H', 'D', 'midnight', 'W0'-'W6')
        rotation_interval: Interval for rotation (e.g., 1 day)
        backup_count: Number of backup files to keep
        console_output: Whether to output logs to console

    Returns:
        Configured root logger instance
    """
    # Determine log directory
    if log_dir is None:
        log_dir = Path.cwd()
    else:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

    log_file_path = log_dir / log_filename

    # Define log format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Create formatters
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Configure file handler with rotation
    file_handler = TimedRotatingFileHandler(
        filename=str(log_file_path),
        when=rotation_when,
        interval=rotation_interval,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # Capture all levels in file

    # Prepare handlers list
    handlers = [file_handler]

    # Add console handler if requested
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)  # Console respects log_level
        handlers.append(console_handler)

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,  # Root logger captures everything
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Get root logger
    root_logger = logging.getLogger()

    # Suppress overly verbose third-party loggers
    _configure_third_party_loggers()

    root_logger.info(
        "Logging initialized: level=%s, file=%s, rotation=%s, backups=%d",
        log_level,
        log_file_path,
        rotation_when,
        backup_count,
    )

    return root_logger


def _configure_third_party_loggers():
    """Reduce noise from verbose third-party libraries."""
    # Set httpx to WARNING to avoid excessive connection logs
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Set httpcore to WARNING
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Suppress urllib3 info logs
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Suppress asyncio debug logs
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.

    This is a convenience function that wraps logging.getLogger()
    with consistent configuration.

    Args:
        name: Logger name (typically __name__ from the calling module)

    Returns:
        Logger instance for the specified name

    Example:
        >>> from core.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Module initialized")
    """
    return logging.getLogger(name)
