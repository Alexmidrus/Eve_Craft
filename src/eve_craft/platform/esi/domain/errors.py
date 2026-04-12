from __future__ import annotations


class EsiError(RuntimeError):
    """Base exception for ESI integration failures."""


class EsiConfigurationError(EsiError):
    """Raised when the ESI module is not configured well enough to execute a request."""


class EsiAuthenticationError(EsiError):
    """Raised when an authenticated request cannot acquire a valid token."""


class EsiHttpError(EsiError):
    """Raised when the ESI endpoint responds with a non-success HTTP status."""

    def __init__(self, message: str, *, status_code: int, payload: object | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class EsiRateLimitedError(EsiHttpError):
    """Raised when the ESI module is blocked by API rate limiting."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        retry_after_seconds: int | None,
        payload: object | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, payload=payload)
        self.retry_after_seconds = retry_after_seconds


class EsiCacheMissError(EsiError):
    """Raised when a cache revalidation succeeds with 304 but the local payload is missing."""

