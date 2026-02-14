"""
Data Collection Module

Contains news collectors and data models.
"""

from .models import NewsArticle, NewsCollectionStats, NewsInsight, NewsPublisher, StockConfig

__all__ = [
    "NewsArticle",
    "NewsInsight",
    "NewsPublisher",
    "StockConfig",
    "NewsCollectionStats",
    "MassiveNewsCollector",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "MassiveNewsCollector":
        from .news_collector import MassiveNewsCollector

        return MassiveNewsCollector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
