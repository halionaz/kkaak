#!/usr/bin/env python3
"""
Real-time News Collection Script

Collects US stock market news using Massive API.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.data.news_collector import MassiveNewsCollector
from src.notification.discord_notifier import DiscordNotifier
from src.utils.config_loader import ConfigLoader


def setup_logging():
    """Configure logging."""
    log_dir = project_root / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"news_collection_{datetime.now().strftime('%Y%m%d')}.log"

    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level=os.getenv("LOG_LEVEL", "INFO"),
    )

    # Add file handler
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {message}",
        level="DEBUG",
        rotation="100 MB",
    )


def on_new_article(article, notifier=None):
    """
    Callback function for new articles.

    Args:
        article: NewsArticle object
        notifier: Optional DiscordNotifier
    """
    logger.info(f"NEW: {article.title}")
    logger.info(f"  Tickers: {', '.join(article.tickers)}")
    logger.info(f"  Sentiment: {article.overall_sentiment}")
    logger.info(f"  URL: {article.article_url}")

    # Send to Discord if notifier is available
    if notifier:
        try:
            # Send notification for high-impact news
            if len(article.tickers) >= 3 or article.overall_sentiment != "neutral":
                notifier.send_realtime_signal(
                    ticker=", ".join(article.tickers[:3]),
                    action="NEWS",
                    confidence=1.0,
                    reasoning=article.description or article.title,
                    news_title=article.title,
                    news_url=str(article.article_url),
                )
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")


def collect_historical(collector: MassiveNewsCollector, tickers: list, hours_back: int = 24):
    """
    Collect historical news articles.

    Args:
        collector: MassiveNewsCollector instance
        tickers: List of ticker symbols
        hours_back: Hours to look back
    """
    logger.info(f"Collecting news from last {hours_back} hours...")

    articles = collector.fetch_latest_for_tickers(
        tickers=tickers, hours_back=hours_back, limit_per_ticker=50
    )

    logger.info(f"Found {len(articles)} articles")

    # Save to JSON for later analysis
    if articles:
        output_dir = project_root / "data" / "news"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        import json

        with open(output_file, "w") as f:
            json.dump([article.model_dump() for article in articles], f, indent=2, default=str)

        logger.info(f"Saved to: {output_file}")

    # Display summary
    sentiment_summary = {"positive": 0, "negative": 0, "neutral": 0}
    ticker_counts = {}

    for article in articles:
        sentiment_summary[article.overall_sentiment] += 1

        for ticker in article.tickers:
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1

    logger.info("\nSentiment Distribution:")
    for sentiment, count in sentiment_summary.items():
        logger.info(f"  {sentiment.capitalize()}: {count}")

    logger.info("\nTop 10 Most Mentioned Tickers:")
    sorted_tickers = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)
    for ticker, count in sorted_tickers[:10]:
        logger.info(f"  {ticker}: {count} articles")


def collect_realtime(
    collector: MassiveNewsCollector,
    tickers: list,
    poll_interval: int = 60,
    duration_minutes: int = None,
    notifier: DiscordNotifier = None,
):
    """
    Collect real-time news articles.

    Args:
        collector: MassiveNewsCollector instance
        tickers: List of ticker symbols
        poll_interval: Seconds between polls
        duration_minutes: Duration in minutes (None = indefinite)
        notifier: Optional Discord notifier
    """
    logger.info("Starting real-time news collection...")
    logger.info(f"Monitoring {len(tickers)} tickers")
    logger.info(f"Poll interval: {poll_interval}s")

    if duration_minutes:
        logger.info(f"Duration: {duration_minutes} minutes")
    else:
        logger.info("Duration: Indefinite (press Ctrl+C to stop)")

    # Create callback with notifier
    def callback(article):
        on_new_article(article, notifier)

    # Start collection
    stats = collector.collect_realtime_news(
        tickers=tickers,
        poll_interval=poll_interval,
        callback=callback,
        duration_minutes=duration_minutes,
    )

    # Display final statistics
    logger.info("\n" + "=" * 60)
    logger.info("Collection Statistics")
    logger.info("=" * 60)
    logger.info(f"Total articles: {stats.total_articles}")
    logger.info(f"Duration: {stats.duration_seconds:.0f} seconds")

    logger.info("\nSentiment Distribution:")
    for sentiment, count in stats.sentiment_distribution.items():
        percentage = (count / stats.total_articles * 100) if stats.total_articles > 0 else 0
        logger.info(f"  {sentiment.capitalize()}: {count} ({percentage:.1f}%)")

    logger.info("\nTop 10 Most Active Tickers:")
    sorted_tickers = sorted(stats.articles_per_ticker.items(), key=lambda x: x[1], reverse=True)
    for ticker, count in sorted_tickers[:10]:
        logger.info(f"  {ticker}: {count} articles")


def main():
    """Main entry point."""
    # Load environment
    load_dotenv()

    # Setup logging
    setup_logging()

    logger.info("=" * 60)
    logger.info("kkaak News Collector")
    logger.info("=" * 60)

    # Load configuration
    try:
        config_loader = ConfigLoader()
        stocks = config_loader.load_stocks()
        tickers = [stock.ticker for stock in stocks]

        logger.info(f"Loaded {len(tickers)} tickers from config")
        logger.info(f"Tickers: {', '.join(tickers)}")

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize Massive API client
    api_key = os.getenv("MASSIVE_API_KEY")
    if not api_key:
        logger.error("MASSIVE_API_KEY not found in environment")
        logger.error("Please set MASSIVE_API_KEY in .env file")
        sys.exit(1)

    try:
        collector = MassiveNewsCollector(api_key=api_key, verbose=False)
        logger.info("Massive API client initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Massive client: {e}")
        sys.exit(1)

    # Initialize Discord notifier (optional)
    notifier = None
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_webhook:
        try:
            notifier = DiscordNotifier(discord_webhook)
            logger.info("Discord notifier initialized")
        except Exception as e:
            logger.warning(f"Discord notifier not available: {e}")

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Collect US stock market news")
    parser.add_argument(
        "--mode",
        choices=["historical", "realtime", "both"],
        default="both",
        help="Collection mode (default: both)",
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Hours to look back for historical data (default: 24)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Poll interval in seconds for realtime mode (default: 60)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duration in minutes for realtime mode (default: indefinite)",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Specific tickers to monitor (default: all from config)",
    )

    args = parser.parse_args()

    # Override tickers if specified
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
        logger.info(f"Using specified tickers: {', '.join(tickers)}")

    # Run collection
    try:
        if args.mode in ["historical", "both"]:
            collect_historical(collector, tickers, args.hours)

        if args.mode in ["realtime", "both"]:
            if args.mode == "both":
                logger.info("\n" + "=" * 60)

            collect_realtime(collector, tickers, args.interval, args.duration, notifier)

    except KeyboardInterrupt:
        logger.info("\nCollection stopped by user")

    except Exception as e:
        logger.error(f"Collection error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    logger.info("\nCollection completed successfully")


if __name__ == "__main__":
    main()
