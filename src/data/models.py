"""
Data Models

Pydantic models for news articles and stock data.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class NewsInsight(BaseModel):
    """News article insight and sentiment analysis."""

    sentiment: Optional[str] = Field(None, description="Sentiment: positive, negative, or neutral")
    sentiment_reasoning: Optional[str] = Field(None, description="Reasoning behind sentiment")
    ticker: Optional[str] = Field(None, description="Related ticker symbol")


class NewsPublisher(BaseModel):
    """News publisher information."""

    name: str = Field(..., description="Publisher name")
    homepage_url: Optional[HttpUrl] = Field(None, description="Publisher homepage")
    logo_url: Optional[HttpUrl] = Field(None, description="Publisher logo")
    favicon_url: Optional[HttpUrl] = Field(None, description="Publisher favicon")


class NewsArticle(BaseModel):
    """News article from Massive API."""

    id: str = Field(..., description="Unique article ID")
    title: str = Field(..., description="Article title")
    author: Optional[str] = Field(None, description="Article author")
    published_utc: datetime = Field(..., description="Publication timestamp (UTC)")
    article_url: HttpUrl = Field(..., description="Article URL")
    tickers: List[str] = Field(default_factory=list, description="Related ticker symbols")
    amp_url: Optional[HttpUrl] = Field(None, description="AMP version URL")
    image_url: Optional[HttpUrl] = Field(None, description="Article image URL")
    description: Optional[str] = Field(None, description="Article summary/description")
    keywords: Optional[List[str]] = Field(default_factory=list, description="Article keywords")
    insights: Optional[List[NewsInsight]] = Field(default_factory=list, description="Sentiment insights")
    publisher: Optional[NewsPublisher] = Field(None, description="Publisher information")

    # Internal tracking
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="When article was collected")
    processed: bool = Field(default=False, description="Whether article has been processed by LLM")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @property
    def sentiment_summary(self) -> Dict[str, int]:
        """Get sentiment distribution across all insights."""
        if not self.insights:
            return {"positive": 0, "negative": 0, "neutral": 0}

        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        for insight in self.insights:
            if insight.sentiment and insight.sentiment.lower() in sentiment_counts:
                sentiment_counts[insight.sentiment.lower()] += 1

        return sentiment_counts

    @property
    def overall_sentiment(self) -> str:
        """Get overall sentiment (majority vote)."""
        sentiment_summary = self.sentiment_summary
        if not any(sentiment_summary.values()):
            return "neutral"
        return max(sentiment_summary.items(), key=lambda x: x[1])[0]

    def has_ticker(self, ticker: str) -> bool:
        """Check if article mentions a specific ticker."""
        return ticker.upper() in [t.upper() for t in self.tickers]

    def is_relevant_for_tickers(self, tickers: List[str]) -> bool:
        """Check if article is relevant for any of the given tickers."""
        ticker_set = {t.upper() for t in tickers}
        article_tickers = {t.upper() for t in self.tickers}
        return bool(ticker_set.intersection(article_tickers))


class StockConfig(BaseModel):
    """Stock configuration from stocks.yaml."""

    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company/fund name")
    sector: str = Field(..., description="Sector/category")
    priority: int = Field(1, description="Priority level (1=high, 2=medium, 3=low)")


class NewsCollectionStats(BaseModel):
    """Statistics for news collection session."""

    total_articles: int = Field(0, description="Total articles collected")
    articles_per_ticker: Dict[str, int] = Field(default_factory=dict, description="Articles by ticker")
    sentiment_distribution: Dict[str, int] = Field(
        default_factory=lambda: {"positive": 0, "negative": 0, "neutral": 0},
        description="Overall sentiment distribution"
    )
    collection_start: datetime = Field(default_factory=datetime.utcnow, description="Collection start time")
    collection_end: Optional[datetime] = Field(None, description="Collection end time")

    def add_article(self, article: NewsArticle):
        """Add an article to statistics."""
        self.total_articles += 1

        # Count by ticker
        for ticker in article.tickers:
            self.articles_per_ticker[ticker] = self.articles_per_ticker.get(ticker, 0) + 1

        # Update sentiment distribution
        sentiment = article.overall_sentiment
        self.sentiment_distribution[sentiment] += 1

    def finish(self):
        """Mark collection as finished."""
        self.collection_end = datetime.utcnow()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get collection duration in seconds."""
        if not self.collection_end:
            return None
        return (self.collection_end - self.collection_start).total_seconds()


# ============================================================================
# Price Data Models (Finnhub)
# ============================================================================

class StockPrice(BaseModel):
    """Real-time stock price data from Finnhub."""

    ticker: str = Field(..., description="Stock ticker symbol")
    price: float = Field(..., description="Current price")
    volume: int = Field(..., description="Trade volume")
    timestamp: datetime = Field(..., description="Trade timestamp (UTC)")

    # Additional trade data
    trade_conditions: Optional[List[str]] = Field(default_factory=list, description="Trade conditions")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class StockQuote(BaseModel):
    """Stock quote snapshot from Finnhub REST API."""

    ticker: str = Field(..., description="Stock ticker symbol")
    current_price: float = Field(..., alias="c", description="Current price")
    change: float = Field(..., alias="d", description="Change")
    percent_change: float = Field(..., alias="dp", description="Percent change")
    high: float = Field(..., alias="h", description="High price of the day")
    low: float = Field(..., alias="l", description="Low price of the day")
    open: float = Field(..., alias="o", description="Open price of the day")
    previous_close: float = Field(..., alias="pc", description="Previous close price")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Quote timestamp")

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PriceCollectionStats(BaseModel):
    """Statistics for price collection session."""

    total_updates: int = Field(0, description="Total price updates received")
    updates_per_ticker: Dict[str, int] = Field(default_factory=dict, description="Updates by ticker")
    collection_start: datetime = Field(default_factory=datetime.utcnow, description="Collection start time")
    collection_end: Optional[datetime] = Field(None, description="Collection end time")
    connection_errors: int = Field(0, description="Number of connection errors")
    last_update: Optional[datetime] = Field(None, description="Last update timestamp")

    def add_update(self, ticker: str):
        """Add a price update to statistics."""
        self.total_updates += 1
        self.updates_per_ticker[ticker] = self.updates_per_ticker.get(ticker, 0) + 1
        self.last_update = datetime.utcnow()

    def add_error(self):
        """Record a connection error."""
        self.connection_errors += 1

    def finish(self):
        """Mark collection as finished."""
        self.collection_end = datetime.utcnow()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get collection duration in seconds."""
        if not self.collection_end:
            return None
        return (self.collection_end - self.collection_start).total_seconds()

    @property
    def updates_per_second(self) -> Optional[float]:
        """Get average updates per second."""
        duration = self.duration_seconds
        if not duration or duration == 0:
            return None
        return self.total_updates / duration
