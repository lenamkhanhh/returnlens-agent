"""Model Adapter Exceptions."""

from __future__ import annotations

from typing import Optional


class ModelUnavailableError(Exception):
    """Exception raised when the model provider is unavailable, unconfigured, or fails cleanly."""

    def __init__(
        self,
        message: str = "Model provider is unavailable.",
        code: str = "MODEL_UNAVAILABLE",
        retryable: bool = False,
        correlation_id: str = "",
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.user_message = message
        self.retryable = retryable
        self.correlation_id = correlation_id
        self.original_error = original_error

    def to_error_shape(self) -> dict:
        """Returns the canonical ErrorShape dictionary per 02 §1."""
        return {
            "code": self.code,
            "user_message": self.user_message,
            "retryable": self.retryable,
            "correlation_id": self.correlation_id,
        }
