"""
Error handling utilities and decorators

Provides standardized error handling patterns for the KKAAK trading system.
"""

import traceback
from typing import Any

from loguru import logger


class ErrorContext:
    """
    Context manager for standardized error handling.

    Automatically handles:
    - Error logging with traceback
    - Discord error notifications
    - Exception suppression/re-raising

    Usage:
        with ErrorContext("장전 분석", discord=notifier, retry_info="다음: 09:00 ET"):
            # Your code here
            pass

    Example with suppression:
        with ErrorContext("optional operation", reraise=False):
            # This won't crash the program if it fails
            risky_operation()
    """

    def __init__(
        self,
        operation_name: str,
        discord: Any | None = None,
        retry_info: str = "",
        reraise: bool = True,
    ):
        """
        Initialize error context.

        Args:
            operation_name: Human-readable operation name (e.g., "장전 분석")
            discord: Optional Discord notifier for sending error alerts
            retry_info: Optional retry information to include in notification
            reraise: Whether to re-raise the exception (default: True)
        """
        self.operation_name = operation_name
        self.discord = discord
        self.retry_info = retry_info
        self.reraise = reraise

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context manager and handle any exceptions.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback

        Returns:
            True to suppress exception, False to re-raise
        """
        # No exception occurred
        if exc_type is None:
            return True

        # Log the error
        logger.error(f"🚨 {self.operation_name} 실패: {exc_val}")
        traceback.print_exc()

        # Send Discord notification
        if self.discord:
            try:
                self.discord.send_error(
                    error_message=f"🚨 {self.operation_name} 실패",
                    context=str(exc_val),
                    retry_info=self.retry_info,
                )
            except Exception as e:
                # Don't let Discord notification failure crash the program
                logger.warning(f"Discord 에러 알림 전송 실패: {e}")

        # Suppress or re-raise exception
        return not self.reraise
