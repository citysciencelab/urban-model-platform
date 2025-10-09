from ump.core.models.ogcp_exception import OGCExceptionResponse

class OGCProcessException(Exception):
    def __init__(self, response: OGCExceptionResponse):
        self.response = response