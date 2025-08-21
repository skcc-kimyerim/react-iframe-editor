from core.exception.error_codes import ErrorCode


class ServiceException(Exception):
    def __init__(
        self,
        error_code: ErrorCode,
    ):
        super().__init__(message=error_code.value)
        self.error_code = error_code
