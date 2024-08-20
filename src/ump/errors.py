import traceback
import logging

class CustomException(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

        self.payload = payload
        logging.error(f"{type(self).__name__}: {self.message}")
        traceback.print_exc()

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error_message'] = self.message
        return rv

    def __str__(self) -> str:
       return str(self.to_dict())

class InvalidUsage(CustomException):
  pass

class GeoserverException(CustomException):
  pass
