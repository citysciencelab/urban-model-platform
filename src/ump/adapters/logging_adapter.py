import logging
from ump.core.interfaces.logging import LoggingPort

class LoggingAdapter(LoggingPort):
    def __init__(self, name: str = "UMP", log_level: int | str = logging.INFO):
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        handler = logging.StreamHandler()
        
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        
        handler.setFormatter(formatter)
        
        if not self.logger.hasHandlers():
            self.logger.addHandler(handler)

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def debug(self, msg: str):
        self.logger.debug(msg)
