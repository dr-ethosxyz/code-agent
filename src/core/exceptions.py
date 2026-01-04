"""Custom API exceptions for the application."""


class ApiException(Exception):
    """Base exception for all API errors."""

    def __init__(
        self,
        status_code: int,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(ApiException):
    """Resource not found exception."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(404, f"{resource} not found: {identifier}")


class UnauthorizedError(ApiException):
    """Unauthorized access exception."""

    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(401, message)


class ValidationError(ApiException):
    """Request validation error."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(422, message, details)


class ExternalServiceError(ApiException):
    """External service (GitHub, Slack, etc.) error."""

    def __init__(self, service: str, message: str) -> None:
        super().__init__(502, f"{service} error: {message}")


class PRNotFoundError(NotFoundError):
    """Pull request not found."""

    def __init__(self, owner: str, repo: str, pr_number: int) -> None:
        super().__init__("Pull request", f"{owner}/{repo}#{pr_number}")


class SignatureVerificationError(UnauthorizedError):
    """Webhook signature verification failed."""

    def __init__(self, source: str = "webhook") -> None:
        super().__init__(f"Invalid {source} signature")
