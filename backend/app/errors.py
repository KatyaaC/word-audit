class DomainError(Exception):
    """Business-rule violation; the API maps it to an HTTP status."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFound(DomainError):
    def __init__(self, message: str = "Not found"):
        super().__init__(message, 404)


class Conflict(DomainError):
    def __init__(self, message: str):
        super().__init__(message, 409)


class Forbidden(DomainError):
    def __init__(self, message: str):
        super().__init__(message, 403)
