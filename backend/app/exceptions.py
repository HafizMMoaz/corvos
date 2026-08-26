"""Structured error hierarchy for Corvos.

Every error response follows a backward-compatible contract:

    {
      "error": {
        "code": "SOME_ERROR_CODE",
        "message": "Human-readable, client-safe message.",
        "status": 422,
        "request_id": "req_...",
        "timestamp": "2026-04-14T12:00:00Z",
        "report_url": "https://github.com/HafizMMoaz/Corvos/issues"
      },
      "detail": "Human-readable, client-safe message."   # legacy compat
    }
"""

from __future__ import annotations

ISSUES_URL = "https://github.com/HafizMMoaz/Corvos/issues"

GENERIC_5XX_MESSAGE = (
    "An internal error occurred. Please try again or report this issue if it persists."
)


class CorvosError(Exception):
    """Base exception that global handlers translate into the structured envelope."""

    def __init__(
        self,
        message: str = GENERIC_5XX_MESSAGE,
        *,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        safe_for_client: bool = True,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.safe_for_client = safe_for_client


class ConnectorError(CorvosError):
    def __init__(self, message: str, *, code: str = "CONNECTOR_ERROR") -> None:
        super().__init__(message, code=code, status_code=502)


class DatabaseError(CorvosError):
    def __init__(
        self,
        message: str = "A database error occurred.",
        *,
        code: str = "DATABASE_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=500)


class ConfigurationError(CorvosError):
    def __init__(
        self,
        message: str = "A configuration error occurred.",
        *,
        code: str = "CONFIGURATION_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=500)


class ExternalServiceError(CorvosError):
    def __init__(
        self,
        message: str = "An external service is unavailable.",
        *,
        code: str = "EXTERNAL_SERVICE_ERROR",
    ) -> None:
        super().__init__(message, code=code, status_code=502)


class NotFoundError(CorvosError):
    def __init__(
        self,
        message: str = "The requested resource was not found.",
        *,
        code: str = "NOT_FOUND",
    ) -> None:
        super().__init__(message, code=code, status_code=404)


class ForbiddenError(CorvosError):
    def __init__(
        self,
        message: str = "You don't have permission to access this resource.",
        *,
        code: str = "FORBIDDEN",
    ) -> None:
        super().__init__(message, code=code, status_code=403)


class ValidationError(CorvosError):
    def __init__(
        self, message: str = "Validation failed.", *, code: str = "VALIDATION_ERROR"
    ) -> None:
        super().__init__(message, code=code, status_code=422)
