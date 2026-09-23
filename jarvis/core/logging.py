"""JARVIS Logging Configuration"""

import logging
import sys
from pathlib import Path
from typing import Optional
from loguru import logger
from jarvis.core.config import get_settings


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    console: Optional[bool] = None,
    file_max_mb: Optional[int] = None,
    file_count: Optional[int] = None,
) -> None:
    """Configure application logging."""
    settings = get_settings()

    log_level = level or settings.logging.level
    log_console = console if console is not None else settings.logging.console
    max_mb = file_max_mb or settings.logging.file_max_mb
    count = file_count or settings.logging.file_count

    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    if log_console:
        logger.add(
            sys.stderr,
            level=log_level,
            format=log_format,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    if log_file is None:
        log_file = settings.get_log_dir() / "jarvis.log"

    logger.add(
        log_file,
        level=log_level,
        format=log_format,
        rotation=f"{max_mb} MB",
        retention=f"{count} days",
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )

    logger.info(f"Logging initialized - Level: {log_level}, File: {log_file}")


def get_logger(name: str):
    """Get a logger instance for a module."""
    return logger.bind(module=name)


class InterceptHandler(logging.Handler):
    """Intercept standard logging and redirect to loguru."""

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == __file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_stdlib_logging() -> None:
    """Redirect standard library logging to loguru."""
    import logging

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def log_exception(exc: Exception, context: str = "") -> None:
    """Log an exception with context."""
    logger.opt(exception=exc).error(f"Exception in {context}: {exc}")


def log_task_start(task_id: str, goal: str) -> None:
    """Log task start."""
    logger.info(f"TASK START [{task_id}] Goal: {goal}")


def log_task_step(task_id: str, step: str, status: str) -> None:
    """Log task step."""
    logger.info(f"TASK STEP [{task_id}] {step} - {status}")


def log_task_complete(task_id: str, success: bool, message: str = "") -> None:
    """Log task completion."""
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"TASK COMPLETE [{task_id}] {status}: {message}")


def log_tool_call(tool: str, args: dict, result: any = None, error: Exception = None) -> None:
    """Log tool invocation."""
    if error:
        logger.error(f"TOOL CALL [{tool}] Args: {args} - ERROR: {error}")
    else:
        logger.debug(f"TOOL CALL [{tool}] Args: {args} - Result: {type(result).__name__}")


def log_approval(action: str, details: str, approved: bool) -> None:
    """Log approval decision."""
    status = "APPROVED" if approved else "DENIED"
    logger.warning(f"APPROVAL [{status}] Action: {action} - {details}")


def log_security_event(event: str, details: dict) -> None:
    """Log security-relevant event."""
    logger.warning(f"SECURITY [{event}] {details}")


def log_performance(operation: str, duration_ms: float, metadata: dict = None) -> None:
    """Log performance metric."""
    logger.info(f"PERF [{operation}] {duration_ms:.2f}ms {metadata or ''}")