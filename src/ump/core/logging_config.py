"""Central logging configuration utilities.

Adds a single composition-root driven `configure_logging` that wires
separate stdout/stderr sinks and injects a correlation id into all log
records. Adapters or domain code never mutate global logging; they only
emit via `LoggingPort` or standard module loggers. Uvicorn is prevented
from stomping configuration by passing `log_config=None` in `main`.
It is a pragmatic deviation: Logging has two viable patterns

Pattern A (what we have now)

Core: calls LoggingPort.info(...)
Adapter: only translates calls to underlying logging API
Composition root: configures handlers/sinks (stdout, stderr, file, remote) once
Rationale: logging is inherently cross‑cutting; centralizing avoids multiple handlers, duplication, races, inconsistent formats.
Pattern B (adapter owns sinks)

Core: same
Adapter: on init installs handlers (file, stdout, remote), filters, formatters
Composition root: just instantiates chosen adapter variant (e.g. ConsoleLoggingAdapter, FileLoggingAdapter, RemoteLoggingAdapter)
Rationale: consistent with “DB adapter owns SQL”; pluggable adapter selection moves all technical concerns behind the port.

Choise guideline (for later):
If we can anticipate multiple distinct logging strategies selectable via environment (e.g. FILE, CONSOLE, REMOTE) and minimal 3rd-party logger consistency needs: move sink setup into adapter subclasses.
If we need both: keep a thin core adapter plus a “logging backend factory” invoked by composition root that returns an initialized adapter and does global handler setup.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional
import contextvars

# Correlation id context variable (populated per-request by FastAPI middleware)
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="-"
)

DEFAULT_FORMAT = (
    "[%(asctime)s] %(levelname)s %(name)s %(correlation_id)s: %(message)s"
)


def _coerce_level(level: int | str | None) -> int:
    if level is None:
        return logging.INFO
    if isinstance(level, int):
        return level
    key = str(level).upper().strip()
    # Python 3.11 mapping helper
    mapping_getter = getattr(logging, "getLevelNamesMapping", None)
    if callable(mapping_getter):
        mapping = mapping_getter()
        if isinstance(mapping, dict) and key in mapping:
            return mapping[key]
    return logging._nameToLevel.get(key, logging.INFO)


class _CorrelationIdFilter(logging.Filter):
    """Inject correlation id from contextvar into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - simple
        try:
            record.correlation_id = correlation_id_var.get()
        except LookupError:
            record.correlation_id = "-"
        return True


class _MaxLevelFilter(logging.Filter):
    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover
        return record.levelno <= self.max_level


class _MinLevelFilter(logging.Filter):
    def __init__(self, min_level: int):
        super().__init__()
        self.min_level = min_level

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover
        return record.levelno >= self.min_level


def configure_logging(
    level: int | str | None = None,
    fmt: Optional[str] = None,
    disable_uvicorn_access: bool = False,
) -> None:
    """Configure root logger with separate stdout/stderr sinks & correlation id.

    Notes
    -----
    * Uvicorn will inherit this configuration when `log_config=None` is used.
    * Access log suppression achieved by raising level on `uvicorn.access`.
    """
    numeric_level = _coerce_level(level)
    fmt = fmt or DEFAULT_FORMAT

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Clear existing handlers to avoid duplication on reload
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(fmt)
    cid_filter = _CorrelationIdFilter()

    # stdout handler for DEBUG/INFO
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(_MaxLevelFilter(logging.INFO))
    stdout_handler.addFilter(cid_filter)
    stdout_handler.setFormatter(formatter)

    # stderr handler for WARNING+
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.addFilter(_MinLevelFilter(logging.WARNING))
    stderr_handler.addFilter(cid_filter)
    stderr_handler.setFormatter(formatter)

    root.addHandler(stdout_handler)
    root.addHandler(stderr_handler)

    # Adjust uvicorn access logger if requested
    if disable_uvicorn_access:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.getLogger("UMP").debug(
        "Logging configured level=%s disable_uvicorn_access=%s", numeric_level, disable_uvicorn_access
    )


def generate_uvicorn_log_config(level: int | str | None) -> dict:
    """Return a uvicorn-compatible log_config dict that preserves UMP logger level.

    This prevents uvicorn from overwriting custom handler/level setup and ensures
    our domain logs appear after server startup (uvicorn normally reconfigures
    logging when run()).
    """
    numeric_level = _coerce_level(level)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "logging.Formatter",
                "fmt": DEFAULT_FORMAT,
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": numeric_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": numeric_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": numeric_level,
                "propagate": False,
            },
            "UMP": {
                "handlers": ["default"],
                "level": numeric_level,
                "propagate": False,
            },
        },
    }
