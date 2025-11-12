import logging
from ump.core.interfaces.logging import LoggingPort
from ump.core.logging_config import correlation_id_var  # ensure module import side effects once

class LoggingAdapter(LoggingPort):
    """Concrete logging adapter.

    Delegates to Python's logging. It intentionally does NOT add its own
    handlers so that central `configure_logging` controls sinks. Correlation
    id is injected by root handlers via filter; we simply emit.
    """

    def __init__(self, name: str = "UMP", log_level: int | str = logging.INFO):
        self.logger = logging.getLogger(name)
        # Normalize level string -> numeric
        if isinstance(log_level, str):
            level_key = log_level.upper().strip()
            mapping_getter = getattr(logging, "getLevelNamesMapping", None)
            numeric = None
            if callable(mapping_getter):
                mapping_obj = mapping_getter()
                if isinstance(mapping_obj, dict):
                    numeric = mapping_obj.get(level_key)
            if numeric is None:
                numeric = logging._nameToLevel.get(level_key, logging.INFO)
            log_level = numeric
        self.logger.setLevel(log_level)
        # Allow messages to bubble to root handlers (separate sinks)
        self.logger.propagate = True
        self.logger.debug("Initialized logger name=%s level=%s", name, self.logger.level)

    def info(self, msg: str, *args):
        self.logger.info(msg, *args)

    def warning(self, msg: str, *args):
        self.logger.warning(msg, *args)

    def error(self, msg: str, *args):
        self.logger.error(msg, *args)

    def debug(self, msg: str, *args):
        self.logger.debug(msg, *args)
