"""
Prompt Templates

System and user prompts for GPT-4o mini analysis.
"""

from typing import List, Dict, Optional


class PromptTemplates:
    """Prompt templates for different analysis modes."""

    # System prompt - defines the agent's role
    SYSTEM_PROMPT = """You are an expert financial analyst and algorithmic trading advisor with deep expertise in US stock markets.

Your role is to analyze real-time news and market data to generate actionable trading signals for a quantitative trading system.

Key principles:
1. Be concise and data-driven - avoid flowery language
2. Focus on price impact and trading opportunities
3. Consider both fundamental news and technical context
4. Assign clear confidence scores based on information quality
5. Identify risks and contrarian indicators
6. Provide reasoning that can be backtested

Output must be valid JSON following the exact schema provided. No additional commentary."""

    # Pre-market analysis prompt
    PRE_MARKET_TEMPLATE = """Analyze the following news articles collected overnight and provide trading signals for the US market opening.

**Analysis Mode:** Pre-Market (Market opens in {time_to_open})

**Watchlist (Tickers to analyze):**
{watchlist}

**News Articles ({news_count}):**
{news_summary}

**Current Prices (Pre-market/Last Close):**
{price_data}

**Your Task:**
1. Analyze how each news article may impact the watchlist tickers
2. Consider sector relationships and industry dynamics (e.g., "AI boom" → NVDA, AMD, GOOGL)
3. Infer impact even if ticker isn't directly mentioned in news
4. Assess overall market sentiment and sector trends
5. Generate trading signals with confidence scores for watchlist tickers

**Analysis Approach:**
- Act like a professional analyst: read general market news and infer which watchlist tickers are affected
- Consider supply chain relationships, competitive dynamics, and sector correlations
- Example: "AI chip demand surge" → positive for NVDA (GPU maker), AMD (competitor), GOOGL (AI company)
- Don't limit analysis to tickers mentioned in news headlines

**Focus Areas:**
- Earnings reports and guidance changes
- Major product announcements or regulatory news
- Analyst upgrades/downgrades
- Merger & acquisition activity
- Macro economic indicators
- Sector-wide trends and technology shifts

**Output Format:**
Return a valid JSON object with this structure:
```json
{{
  "market_sentiment": "bullish|bearish|neutral",
  "market_summary": "Brief 1-2 sentence market overview",
  "ticker_analyses": [
    {{
      "ticker": "AAPL",
      "signal": "strong_buy|buy|hold|sell|strong_sell",
      "sentiment": "positive|negative|neutral",
      "confidence": 0.85,
      "expected_impact": "bullish|bearish|neutral",
      "impact_magnitude": "low|medium|high",
      "key_points": ["Key insight 1", "Key insight 2"],
      "risk_factors": ["Risk 1", "Risk 2"],
      "reasoning": "Detailed reasoning for the signal"
    }}
  ],
  "top_opportunities": ["Opportunity 1", "Opportunity 2", "Opportunity 3"],
  "top_risks": ["Risk 1", "Risk 2", "Risk 3"],
  "priority_tickers": ["TICKER1", "TICKER2"],
  "avoid_tickers": ["TICKER1", "TICKER2"],
  "overall_risk_level": "low|medium|high|extreme"
}}
```

Respond with ONLY the JSON object, no other text."""

    # Realtime analysis prompt
    REALTIME_TEMPLATE = """Analyze breaking news and provide immediate trading signals for the US market.

**Analysis Mode:** Real-Time (Market is {market_status})

**Watchlist (Tickers to analyze):**
{watchlist}

**Latest News ({news_count} articles in last {time_window}):**
{news_summary}

**Current Market Prices:**
{price_data}

**Recent Price Changes (Last hour):**
{price_changes}

**Your Task:**
1. Analyze how breaking news may impact the watchlist tickers
2. Consider sector relationships and industry dynamics
3. Infer impact even if ticker isn't directly mentioned in news
4. Assess if news is already priced in or will cause further moves
5. Generate time-sensitive signals for watchlist tickers
6. Flag high-volatility tickers that need close monitoring

**Analysis Approach:**
- Act like a professional analyst: read general market news and infer which watchlist tickers are affected
- Consider supply chain relationships, competitive dynamics, and sector correlations
- Example: "Federal Reserve rate decision" → impacts financial sector (JPM, GS), tech growth stocks (AAPL, MSFT)
- Don't limit analysis to tickers mentioned in news headlines

**Focus Areas:**
- Breaking news just published (<30 min)
- Unusual price movements vs. news sentiment
- Momentum shifts and reversal signals
- Volume spikes and liquidity concerns
- Fast-moving situations (halts, circuit breakers)
- Sector-wide implications of breaking news

**Output Format:**
Return a valid JSON object with this structure:
```json
{{
  "market_sentiment": "bullish|bearish|neutral",
  "market_summary": "Brief 1-2 sentence market overview",
  "ticker_analyses": [
    {{
      "ticker": "NVDA",
      "signal": "strong_buy|buy|hold|sell|strong_sell",
      "sentiment": "positive|negative|neutral",
      "confidence": 0.75,
      "expected_impact": "bullish|bearish|neutral",
      "impact_magnitude": "low|medium|high",
      "key_points": ["Key insight 1", "Key insight 2"],
      "risk_factors": ["Risk 1", "Risk 2"],
      "reasoning": "Detailed reasoning for the signal"
    }}
  ],
  "top_opportunities": ["Opportunity 1", "Opportunity 2"],
  "top_risks": ["Risk 1", "Risk 2"],
  "priority_tickers": ["TICKER1", "TICKER2"],
  "avoid_tickers": ["TICKER1", "TICKER2"],
  "overall_risk_level": "low|medium|high|extreme"
}}
```

Respond with ONLY the JSON object, no other text."""

    @staticmethod
    def format_news_summary(news_articles: List[Dict]) -> str:
        """Format news articles for the prompt."""
        if not news_articles:
            return "No news articles available."

        summaries = []
        for idx, article in enumerate(news_articles, 1):
            tickers = ", ".join(article.get("tickers", []))
            title = article.get("title", "No title")
            description = article.get("description", "")
            published = article.get("published_utc", "")

            # Truncate description to save tokens
            if description and len(description) > 200:
                description = description[:200] + "..."

            summary = f"{idx}. [{tickers}] {title}\n   Published: {published}\n   {description}"
            summaries.append(summary)

        return "\n\n".join(summaries)

    @staticmethod
    def format_price_data(prices: Dict[str, float]) -> str:
        """Format price data for the prompt."""
        if not prices:
            return "No price data available."

        lines = []
        for ticker, price in sorted(prices.items()):
            lines.append(f"  {ticker}: ${price:.2f}")

        return "\n".join(lines)

    @staticmethod
    def format_price_changes(
        current_prices: Dict[str, float],
        previous_prices: Dict[str, float]
    ) -> str:
        """Format price changes for the prompt."""
        if not current_prices or not previous_prices:
            return "No price change data available."

        lines = []
        for ticker in sorted(current_prices.keys()):
            current = current_prices.get(ticker)
            previous = previous_prices.get(ticker)

            if current is not None and previous is not None:
                change = current - previous
                pct_change = (change / previous) * 100 if previous != 0 else 0
                symbol = "↑" if change >= 0 else "↓"
                lines.append(f"  {ticker}: {symbol} {pct_change:+.2f}% (${current:.2f})")

        return "\n".join(lines) if lines else "No price changes available."

    @classmethod
    def build_pre_market_prompt(
        cls,
        news_articles: List[Dict],
        current_prices: Dict[str, float],
        time_to_open: str = "30 minutes",
        watchlist: Optional[List[str]] = None,
    ) -> str:
        """Build complete pre-market analysis prompt.

        Args:
            news_articles: List of news article dictionaries
            current_prices: Current prices for tickers
            time_to_open: Time until market opens
            watchlist: List of ticker symbols to analyze (optional)
        """
        news_summary = cls.format_news_summary(news_articles)
        price_data = cls.format_price_data(current_prices)

        # Format watchlist
        watchlist_str = ", ".join(watchlist) if watchlist else ", ".join(current_prices.keys())

        return cls.PRE_MARKET_TEMPLATE.format(
            time_to_open=time_to_open,
            watchlist=watchlist_str,
            news_count=len(news_articles),
            news_summary=news_summary,
            price_data=price_data,
        )

    @classmethod
    def build_realtime_prompt(
        cls,
        news_articles: List[Dict],
        current_prices: Dict[str, float],
        previous_prices: Optional[Dict[str, float]] = None,
        market_status: str = "OPEN",
        time_window: str = "30 minutes",
        watchlist: Optional[List[str]] = None,
    ) -> str:
        """Build complete realtime analysis prompt.

        Args:
            news_articles: List of news article dictionaries
            current_prices: Current prices for tickers
            previous_prices: Previous prices for comparison
            market_status: Market status (OPEN, CLOSED, etc.)
            time_window: Time window for news collection
            watchlist: List of ticker symbols to analyze (optional)
        """
        news_summary = cls.format_news_summary(news_articles)
        price_data = cls.format_price_data(current_prices)

        # Format watchlist
        watchlist_str = ", ".join(watchlist) if watchlist else ", ".join(current_prices.keys())

        # Price changes (optional)
        price_changes = ""
        if previous_prices:
            price_changes = cls.format_price_changes(current_prices, previous_prices)
        else:
            price_changes = "No previous price data available."

        return cls.REALTIME_TEMPLATE.format(
            market_status=market_status,
            watchlist=watchlist_str,
            news_count=len(news_articles),
            time_window=time_window,
            news_summary=news_summary,
            price_data=price_data,
            price_changes=price_changes,
        )
