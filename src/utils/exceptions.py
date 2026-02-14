"""
Custom exceptions for KKAAK trading system

Provides a structured exception hierarchy for different error types
throughout the trading pipeline.
"""

from typing import Optional


class KKAAKException(Exception):
    """Base exception for all KKAAK errors"""
    pass


class DataCollectionError(KKAAKException):
    """Errors during data collection (news, prices)"""
    pass


class AnalysisError(KKAAKException):
    """Errors during LLM analysis"""
    pass


class SignalGenerationError(KKAAKException):
    """Errors during signal generation"""
    pass


class BacktestError(KKAAKException):
    """Errors during backtesting"""
    pass


class APIError(KKAAKException):
    """External API errors"""

    def __init__(self, message: str, api_name: str, retry_after: Optional[int] = None):
        """
        Initialize API error.

        Args:
            message: Error message
            api_name: Name of the API that failed
            retry_after: Optional seconds to wait before retrying
        """
        super().__init__(message)
        self.api_name = api_name
        self.retry_after = retry_after

    def __str__(self):
        msg = f"{self.api_name}: {super().__str__()}"
        if self.retry_after:
            msg += f" (retry after {self.retry_after}s)"
        return msg
