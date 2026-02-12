"""
Analysis Models

Pydantic models for LLM analysis results and trading signals.
"""

from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk level for trading signals."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class TradingSignal(str, Enum):
    """Trading signal recommendation."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class TickerAnalysis(BaseModel):
    """Analysis for a specific ticker."""

    ticker: str = Field(..., description="Stock ticker symbol")
    signal: TradingSignal = Field(..., description="Trading signal")
    sentiment: str = Field(..., description="Overall sentiment (positive/negative/neutral)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")

    # Price impact
    expected_impact: str = Field(..., description="Expected price impact (bullish/bearish/neutral)")
    impact_magnitude: str = Field(..., description="Impact magnitude (low/medium/high)")

    # Key insights
    key_points: List[str] = Field(default_factory=list, description="Key points from news")
    risk_factors: List[str] = Field(default_factory=list, description="Risk factors to consider")

    # Reasoning
    reasoning: str = Field(..., description="Detailed reasoning for the signal")


class AnalysisResult(BaseModel):
    """Complete analysis result from GPT-4o mini."""

    # Metadata
    analysis_id: str = Field(..., description="Unique analysis ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Analysis timestamp")
    model: str = Field(default="gpt-4o-mini", description="Model used for analysis")

    # Market overview
    market_sentiment: str = Field(..., description="Overall market sentiment")
    market_summary: str = Field(..., description="Brief market summary")

    # Ticker-specific analysis
    ticker_analyses: List[TickerAnalysis] = Field(default_factory=list, description="Per-ticker analysis")

    # Top opportunities/risks
    top_opportunities: List[str] = Field(default_factory=list, description="Top opportunities identified")
    top_risks: List[str] = Field(default_factory=list, description="Top risks identified")

    # Trading recommendations
    priority_tickers: List[str] = Field(default_factory=list, description="Priority tickers to watch")
    avoid_tickers: List[str] = Field(default_factory=list, description="Tickers to avoid")

    # Risk assessment
    overall_risk_level: RiskLevel = Field(..., description="Overall market risk level")

    # Token usage (for cost tracking)
    tokens_used: Optional[int] = Field(None, description="Total tokens used")
    cost_usd: Optional[float] = Field(None, description="Estimated cost in USD")

    # Source data
    news_count: int = Field(0, description="Number of news articles analyzed")
    news_ids: List[str] = Field(default_factory=list, description="IDs of analyzed articles")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def get_ticker_analysis(self, ticker: str) -> Optional[TickerAnalysis]:
        """Get analysis for a specific ticker."""
        for analysis in self.ticker_analyses:
            if analysis.ticker.upper() == ticker.upper():
                return analysis
        return None

    def get_buy_signals(self) -> List[TickerAnalysis]:
        """Get all buy signals (strong_buy and buy)."""
        return [
            a for a in self.ticker_analyses
            if a.signal in [TradingSignal.STRONG_BUY, TradingSignal.BUY]
        ]

    def get_sell_signals(self) -> List[TickerAnalysis]:
        """Get all sell signals (strong_sell and sell)."""
        return [
            a for a in self.ticker_analyses
            if a.signal in [TradingSignal.STRONG_SELL, TradingSignal.SELL]
        ]

    @property
    def high_confidence_signals(self) -> List[TickerAnalysis]:
        """Get high confidence signals (>0.7)."""
        return [a for a in self.ticker_analyses if a.confidence > 0.7]


class AnalysisRequest(BaseModel):
    """Request for LLM analysis."""

    mode: str = Field(..., description="Analysis mode: 'pre_market' or 'realtime'")
    news_articles: List[Dict] = Field(..., description="News articles to analyze")
    current_prices: Optional[Dict[str, float]] = Field(None, description="Current prices for tickers")
    market_context: Optional[str] = Field(None, description="Additional market context")

    # Analysis preferences
    focus_tickers: Optional[List[str]] = Field(None, description="Specific tickers to focus on")
    risk_tolerance: str = Field("medium", description="Risk tolerance: low/medium/high")

    class Config:
        json_schema_extra = {
            "example": {
                "mode": "pre_market",
                "news_articles": [],
                "current_prices": {"AAPL": 275.50, "NVDA": 190.05},
                "market_context": "Market opening in 30 minutes",
                "focus_tickers": ["AAPL", "NVDA"],
                "risk_tolerance": "medium"
            }
        }
