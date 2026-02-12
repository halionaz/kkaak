"""
News Collector Module

Collects real-time US stock market news using Massive API.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set, Dict, Any
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

try:
    from massive import RESTClient
    from massive.exceptions import BadResponse
    MASSIVE_AVAILABLE = True
except ImportError:
    MASSIVE_AVAILABLE = False
    logger.warning("massive library not installed. Run: pip install massive")

from .models import NewsArticle, NewsInsight, NewsPublisher, NewsCollectionStats


class MassiveNewsCollector:
    """Collects real-time stock market news from Massive API."""

    # Rate limiting settings
    REQUEST_DELAY_SECONDS = 0.5  # Delay between API calls
    MAX_RETRIES = 3  # Maximum retry attempts

    # Memory management for seen articles
    MAX_SEEN_ARTICLES = 10000  # Maximum articles to track

    def __init__(
        self,
        api_key: str,
        trace: bool = False,
        verbose: bool = False
    ):
        """
        Initialize Massive news collector.

        Args:
            api_key: Massive API key
            trace: Enable trace mode for debugging
            verbose: Enable verbose logging
        """
        if not MASSIVE_AVAILABLE:
            raise ImportError(
                "massive library is required. Install it with: pip install massive"
            )

        self.api_key = api_key
        self.client = RESTClient(
            api_key=api_key,
            trace=trace,
            verbose=verbose
        )

        # Track seen articles to avoid duplicates
        self.seen_article_ids: Set[str] = set()

        # Track API call statistics
        self.api_calls_count = 0
        self.api_errors_count = 0

        logger.info("MassiveNewsCollector initialized")

    def _parse_news_response(self, news_data) -> NewsArticle:
        """
        Parse raw news data from Massive API into NewsArticle model.

        Args:
            news_data: Raw news data from API (TickerNews object or dict)

        Returns:
            NewsArticle object
        """
        # Convert to dict if it's an object
        if not isinstance(news_data, dict):
            if hasattr(news_data, "__dict__"):
                # Convert object to dict, handling nested objects
                data_dict = {}
                for key in ["id", "title", "author", "published_utc", "article_url",
                           "tickers", "amp_url", "image_url", "description", "keywords",
                           "insights", "publisher"]:
                    if hasattr(news_data, key):
                        value = getattr(news_data, key)
                        if value is not None:
                            data_dict[key] = value
                news_data = data_dict
            else:
                raise ValueError(f"Cannot parse news data of type {type(news_data)}")

        # Parse insights
        insights = []
        if news_data.get("insights"):
            for insight_data in news_data["insights"]:
                # Handle both dict and object
                if not isinstance(insight_data, dict):
                    insight_dict = {}
                    for attr in ["sentiment", "sentiment_reasoning", "ticker"]:
                        if hasattr(insight_data, attr):
                            insight_dict[attr] = getattr(insight_data, attr)
                    insight_data = insight_dict

                insights.append(NewsInsight(
                    sentiment=insight_data.get("sentiment"),
                    sentiment_reasoning=insight_data.get("sentiment_reasoning"),
                    ticker=insight_data.get("ticker")
                ))

        # Parse publisher
        publisher = None
        if news_data.get("publisher"):
            pub_data = news_data["publisher"]
            # Handle both dict and object
            if not isinstance(pub_data, dict):
                pub_dict = {}
                for attr in ["name", "homepage_url", "logo_url", "favicon_url"]:
                    if hasattr(pub_data, attr):
                        pub_dict[attr] = getattr(pub_data, attr)
                pub_data = pub_dict

            publisher = NewsPublisher(
                name=pub_data.get("name", "Unknown"),
                homepage_url=pub_data.get("homepage_url"),
                logo_url=pub_data.get("logo_url"),
                favicon_url=pub_data.get("favicon_url")
            )

        # Parse published_utc
        published_utc = news_data.get("published_utc")
        if isinstance(published_utc, str):
            published_utc = datetime.fromisoformat(
                published_utc.replace("Z", "+00:00")
            )
        elif not isinstance(published_utc, datetime):
            # Fallback to current time if not parseable
            published_utc = datetime.now(timezone.utc)
        elif published_utc.tzinfo is None:
            # Make timezone-aware if it's naive
            published_utc = published_utc.replace(tzinfo=timezone.utc)

        # Create article
        article = NewsArticle(
            id=news_data["id"],
            title=news_data["title"],
            author=news_data.get("author"),
            published_utc=published_utc,
            article_url=news_data["article_url"],
            tickers=news_data.get("tickers", []),
            amp_url=news_data.get("amp_url"),
            image_url=news_data.get("image_url"),
            description=news_data.get("description"),
            keywords=news_data.get("keywords", []),
            insights=insights,
            publisher=publisher
        )

        return article

    def _fetch_ticker_news_with_retry(
        self,
        ticker: str,
        kwargs: Dict[str, Any]
    ) -> List:
        """
        Fetch news for a single ticker with retry logic.

        Args:
            ticker: Stock ticker symbol
            kwargs: Query parameters

        Returns:
            List of news results
        """
        @retry(
            stop=stop_after_attempt(self.MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((BadResponse, ConnectionError, TimeoutError)),
            before_sleep=before_sleep_log(logger, "WARNING"),
            reraise=True
        )
        def _fetch():
            self.api_calls_count += 1
            ticker_kwargs = kwargs.copy()
            ticker_kwargs["ticker"] = ticker

            # Rename published_utc.gte to published_utc_gte for SDK
            if "published_utc.gte" in ticker_kwargs:
                ticker_kwargs["published_utc_gte"] = ticker_kwargs.pop("published_utc.gte")

            return list(self.client.list_ticker_news(**ticker_kwargs))

        try:
            return _fetch()
        except Exception as e:
            self.api_errors_count += 1
            logger.warning(f"Failed to fetch news for {ticker} after {self.MAX_RETRIES} attempts: {e}")
            return []

    def fetch_news(
        self,
        tickers: Optional[List[str]] = None,
        limit: int = 100,
        published_after: Optional[datetime] = None,
        order: str = "desc"
    ) -> List[NewsArticle]:
        """
        Fetch news articles from Massive API with retry logic and rate limiting.

        Args:
            tickers: List of ticker symbols to filter (None = all tickers)
            limit: Maximum number of articles to fetch (max 1000)
            published_after: Only fetch articles published after this time
            order: Sort order ("asc" or "desc")

        Returns:
            List of NewsArticle objects
        """
        articles = []
        start_time = time.time()

        try:
            # Build query parameters
            kwargs = {
                "limit": min(limit, 1000),
                "order": order,
                "sort": "published_utc"
            }

            # Add time filter if specified
            if published_after:
                # Format as YYYY-MM-DD for API compatibility
                kwargs["published_utc.gte"] = published_after.strftime("%Y-%m-%d")

            logger.info(f"Fetching news with params: limit={kwargs['limit']}, "
                       f"tickers={len(tickers) if tickers else 'all'}, "
                       f"published_after={published_after.strftime('%Y-%m-%d') if published_after else 'any'}")

            # Fetch news from API
            news_results = []
            successful_tickers = []
            failed_tickers = []

            if tickers:
                # Fetch for each ticker with rate limiting
                for idx, ticker in enumerate(tickers):
                    # Rate limiting: add delay between requests
                    if idx > 0:
                        time.sleep(self.REQUEST_DELAY_SECONDS)

                    try:
                        ticker_news = self._fetch_ticker_news_with_retry(ticker, kwargs)
                        news_results.extend(ticker_news)
                        successful_tickers.append(ticker)
                        logger.debug(f"✓ {ticker}: {len(ticker_news)} articles")
                    except Exception as e:
                        failed_tickers.append(ticker)
                        logger.debug(f"✗ {ticker}: failed")

                # Log summary
                logger.info(f"API calls: {len(tickers)} tickers - "
                          f"Success: {len(successful_tickers)}, Failed: {len(failed_tickers)}")

                if failed_tickers:
                    logger.warning(f"Failed tickers: {', '.join(failed_tickers[:5])}"
                                 f"{f' (+{len(failed_tickers)-5} more)' if len(failed_tickers) > 5 else ''}")
            else:
                # Fetch all news without ticker filter
                try:
                    @retry(
                        stop=stop_after_attempt(self.MAX_RETRIES),
                        wait=wait_exponential(multiplier=1, min=2, max=10),
                        retry=retry_if_exception_type((BadResponse, ConnectionError, TimeoutError)),
                        before_sleep=before_sleep_log(logger, "WARNING")
                    )
                    def _fetch_all():
                        self.api_calls_count += 1
                        fetch_kwargs = kwargs.copy()
                        if "ticker" in fetch_kwargs:
                            del fetch_kwargs["ticker"]
                        if "published_utc.gte" in fetch_kwargs:
                            fetch_kwargs["published_utc_gte"] = fetch_kwargs.pop("published_utc.gte")
                        return list(self.client.list_ticker_news(**fetch_kwargs))

                    news_results = _fetch_all()
                except Exception as e:
                    self.api_errors_count += 1
                    logger.error(f"Failed to fetch all news: {e}")

            # Parse results
            parsed_count = 0
            parse_errors = 0

            for news_data in news_results:
                # Convert to dict if it's an object
                if not isinstance(news_data, dict):
                    news_data = news_data.__dict__ if hasattr(news_data, "__dict__") else news_data

                # Skip if we've already seen this article
                article_id = news_data.get("id")
                if article_id in self.seen_article_ids:
                    continue

                # Parse and add article
                try:
                    article = self._parse_news_response(news_data)
                    articles.append(article)
                    self.seen_article_ids.add(article_id)
                    parsed_count += 1

                except Exception as e:
                    parse_errors += 1
                    if parse_errors <= 3:  # Only log first few errors
                        logger.error(f"Failed to parse article {article_id}: {e}")
                    continue

            # Clean up seen_article_ids if it gets too large
            if len(self.seen_article_ids) > self.MAX_SEEN_ARTICLES:
                logger.info(f"Cleaning up seen_article_ids (size: {len(self.seen_article_ids)})")
                # Keep only the most recent half
                old_size = len(self.seen_article_ids)
                self.seen_article_ids = set(list(self.seen_article_ids)[old_size // 2:])
                logger.info(f"Reduced seen_article_ids from {old_size} to {len(self.seen_article_ids)}")

            elapsed = time.time() - start_time
            logger.info(f"Fetched {len(articles)} new articles in {elapsed:.1f}s "
                       f"(API calls: {self.api_calls_count}, errors: {self.api_errors_count})")

            if parse_errors > 0:
                logger.warning(f"Failed to parse {parse_errors} articles")

        except Exception as e:
            logger.error(f"Unexpected error in fetch_news: {e}")
            # Return any articles we successfully fetched before the error
            if articles:
                logger.info(f"Returning {len(articles)} articles fetched before error")

        return articles

    def _fetch_news_direct(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch news using direct REST call (fallback method).

        Args:
            **kwargs: Query parameters

        Returns:
            List of raw news data dictionaries
        """
        import requests

        url = "https://api.massive.com/v2/reference/news"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        params = {}
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except requests.exceptions.RequestException as e:
            logger.error(f"Direct REST call failed: {e}")
            return []

    def fetch_latest_for_tickers(
        self,
        tickers: List[str],
        hours_back: int = 24,
        limit_per_ticker: int = 50
    ) -> List[NewsArticle]:
        """
        Fetch latest news for specific tickers.

        Args:
            tickers: List of ticker symbols
            hours_back: How many hours back to search
            limit_per_ticker: Max articles per ticker

        Returns:
            List of NewsArticle objects
        """
        published_after = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        return self.fetch_news(
            tickers=tickers,
            limit=len(tickers) * limit_per_ticker,
            published_after=published_after
        )

    def fetch_latest_market_news(
        self,
        hours_back: int = 24,
        limit: int = 100
    ) -> List[NewsArticle]:
        """
        Fetch latest market news without ticker filtering.

        This method fetches general market news (not filtered by ticker),
        allowing the LLM to analyze news and infer which tickers/sectors
        may be affected, similar to how an analyst works.

        Args:
            hours_back: How many hours back to search
            limit: Maximum number of articles to fetch

        Returns:
            List of NewsArticle objects
        """
        published_after = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        logger.info(f"Fetching market news (no ticker filter, last {hours_back} hours)")

        return self.fetch_news(
            tickers=None,  # No ticker filter - fetch all market news
            limit=limit,
            published_after=published_after
        )

    def collect_realtime_news(
        self,
        tickers: List[str],
        poll_interval: int = 60,
        callback: Optional[callable] = None,
        duration_minutes: Optional[int] = None
    ) -> NewsCollectionStats:
        """
        Collect real-time news with polling.

        Args:
            tickers: List of ticker symbols to monitor
            poll_interval: Seconds between polls
            callback: Optional callback function(article) called for each new article
            duration_minutes: Run for specified minutes (None = run indefinitely)

        Returns:
            NewsCollectionStats with collection statistics
        """
        stats = NewsCollectionStats()
        start_time = datetime.now(timezone.utc)

        logger.info(f"Starting real-time news collection for {len(tickers)} tickers")
        logger.info(f"Poll interval: {poll_interval}s, Duration: {duration_minutes}min")

        try:
            while True:
                # Check if we should stop
                if duration_minutes:
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        logger.info(f"Collection duration reached: {elapsed:.1f} minutes")
                        break

                # Fetch latest news (last 5 minutes to avoid missing anything)
                published_after = datetime.now(timezone.utc) - timedelta(minutes=5)

                try:
                    articles = self.fetch_news(
                        tickers=tickers,
                        limit=100,
                        published_after=published_after
                    )

                    # Process new articles
                    for article in articles:
                        stats.add_article(article)

                        # Call callback if provided
                        if callback:
                            try:
                                callback(article)
                            except Exception as e:
                                logger.error(f"Callback error for article {article.id}: {e}")

                        logger.info(
                            f"New article: {article.title[:60]}... "
                            f"(Tickers: {', '.join(article.tickers)}, "
                            f"Sentiment: {article.overall_sentiment})"
                        )

                except Exception as e:
                    logger.error(f"Error during news fetch: {e}")

                # Wait before next poll
                time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("Collection stopped by user")

        finally:
            stats.finish()
            logger.info(f"Collection finished. Total articles: {stats.total_articles}")

        return stats

    def fetch_market_moving_news(
        self,
        tickers: Optional[List[str]] = None,
        hours_back: int = 6,
        min_tickers: int = 3
    ) -> List[NewsArticle]:
        """
        Fetch news that could be market-moving (mentioned by multiple tickers).

        Args:
            tickers: List of ticker symbols to filter (None = all)
            hours_back: How many hours back to search
            min_tickers: Minimum number of tickers mentioned to be considered market-moving

        Returns:
            List of potentially market-moving articles
        """
        published_after = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        all_articles = self.fetch_news(
            tickers=tickers,
            limit=500,
            published_after=published_after
        )

        # Filter articles that mention multiple tickers
        market_moving = [
            article for article in all_articles
            if len(article.tickers) >= min_tickers
        ]

        logger.info(
            f"Found {len(market_moving)} potentially market-moving articles "
            f"out of {len(all_articles)} total"
        )

        return market_moving

    def reset_seen_articles(self):
        """Clear the set of seen article IDs."""
        self.seen_article_ids.clear()
        logger.info("Reset seen articles cache")


def test_news_collection(api_key: str, tickers: List[str]):
    """
    Test news collection functionality.

    Args:
        api_key: Massive API key
        tickers: List of tickers to test
    """
    print(f"\n{'='*60}")
    print(f"Testing Massive News Collector")
    print(f"{'='*60}\n")

    collector = MassiveNewsCollector(api_key=api_key, verbose=True)

    print(f"Fetching latest news for: {', '.join(tickers)}\n")

    # Fetch news from last 24 hours
    articles = collector.fetch_latest_for_tickers(
        tickers=tickers,
        hours_back=24,
        limit_per_ticker=5
    )

    print(f"\nFound {len(articles)} articles:\n")

    for i, article in enumerate(articles[:10], 1):
        print(f"{i}. {article.title}")
        print(f"   Tickers: {', '.join(article.tickers)}")
        print(f"   Sentiment: {article.overall_sentiment}")
        print(f"   Published: {article.published_utc}")
        print(f"   URL: {article.article_url}")
        print()

    # Test market-moving news
    print("\nFetching market-moving news...\n")
    market_moving = collector.fetch_market_moving_news(
        tickers=tickers,
        hours_back=12,
        min_tickers=2
    )

    print(f"Found {len(market_moving)} market-moving articles:\n")

    for i, article in enumerate(market_moving[:5], 1):
        print(f"{i}. {article.title}")
        print(f"   Affects {len(article.tickers)} tickers: {', '.join(article.tickers)}")
        print(f"   Sentiment: {article.overall_sentiment}")
        print()


if __name__ == "__main__":
    import os
    import sys
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    api_key = os.getenv("MASSIVE_API_KEY")

    if not api_key:
        print("Error: MASSIVE_API_KEY not found in .env file")
        print("Please set your Massive API key in .env file")
        sys.exit(1)

    # Test tickers
    test_tickers = ["AAPL", "NVDA", "TSLA", "GOOGL", "MSFT"]

    try:
        test_news_collection(api_key, test_tickers)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
