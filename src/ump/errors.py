import logging
import traceback


class CustomException(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

        self.payload = payload
        logging.error("%s: %s", type(self).__name__, self.message)
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

class ClientError(CustomException):
    """Raised for client-side errors (4xx)."""
    pass

class ServerError(CustomException):
    """Raised for server-side errors (5xx)."""
    pass

class UnexpectedError(CustomException):
    """Raised for unexpected errors."""
    pass