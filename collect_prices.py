#!/usr/bin/env python3
"""
Real-time Price Collection Script

Collects US stock market prices and volumes using Finnhub API.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.data.price_collector import FinnhubPriceCollector
from src.utils.config_loader import ConfigLoader
from src.notification.discord_notifier import DiscordNotifier


def setup_logging():
    """Configure logging."""
    log_dir = project_root / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"price_collection_{datetime.now().strftime('%Y%m%d')}.log"

    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level=os.getenv("LOG_LEVEL", "INFO")
    )

    # Add file handler
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {message}",
        level="DEBUG",
        rotation="100 MB"
    )


def save_quotes_to_file(quotes, tickers):
    """
    Save quotes to JSON file.

    Args:
        quotes: Dictionary of StockQuote objects
        tickers: List of ticker symbols
    """
    output_dir = project_root / "data" / "prices"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"prices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Convert to dict
    quotes_data = {
        ticker: quote.model_dump() for ticker, quote in quotes.items()
    }

    with open(output_file, "w") as f:
        json.dump(quotes_data, f, indent=2, default=str)

    logger.info(f"Saved quotes to: {output_file}")


def on_price_update(price, notifier=None, price_cache=None):
    """
    Callback function for price updates.

    Args:
        price: StockPrice object
        notifier: Optional DiscordNotifier
        price_cache: Optional dict to track price changes
    """
    logger.info(
        f"[{price.timestamp.strftime('%H:%M:%S')}] "
        f"{price.ticker:6s}: ${price.price:8.2f} (Vol: {price.volume:,})"
    )

    # Track significant price changes
    if price_cache is not None:
        if price.ticker in price_cache:
            prev_price = price_cache[price.ticker]
            change_pct = ((price.price - prev_price) / prev_price) * 100

            # Send Discord notification for significant changes (>1%)
            if notifier and abs(change_pct) >= 1.0:
                try:
                    action = "📈 UP" if change_pct > 0 else "📉 DOWN"
                    notifier.send_realtime_signal(
                        ticker=price.ticker,
                        action=action,
                        confidence=min(abs(change_pct) / 5.0, 1.0),
                        reasoning=f"Price moved {change_pct:+.2f}% to ${price.price:.2f}",
                        news_title=f"{price.ticker} significant price movement"
                    )
                except Exception as e:
                    logger.error(f"Failed to send Discord notification: {e}")

        price_cache[price.ticker] = price.price


def collect_snapshot(collector: FinnhubPriceCollector, tickers: list):
    """
    Collect a single snapshot of current prices.

    Args:
        collector: FinnhubPriceCollector instance
        tickers: List of ticker symbols
    """
    logger.info(f"Fetching price snapshot for {len(tickers)} tickers...")

    quotes = collector.get_quotes(tickers)

    logger.info(f"Received {len(quotes)} quotes")

    # Display quotes
    logger.info("\n" + "="*60)
    logger.info("Current Market Quotes")
    logger.info("="*60)

    for ticker, quote in sorted(quotes.items()):
        logger.info(
            f"{ticker:6s}: ${quote.current_price:8.2f} "
            f"({quote.percent_change:+6.2f}%) "
            f"[O:{quote.open:.2f} H:{quote.high:.2f} L:{quote.low:.2f}]"
        )

    logger.info("="*60)

    # Save to file
    if quotes:
        save_quotes_to_file(quotes, tickers)


def collect_websocket(
    collector: FinnhubPriceCollector,
    tickers: list,
    duration_minutes: int = None,
    notifier: DiscordNotifier = None
):
    """
    Collect real-time prices using WebSocket.

    Args:
        collector: FinnhubPriceCollector instance
        tickers: List of ticker symbols
        duration_minutes: Duration in minutes (None = indefinite)
        notifier: Optional Discord notifier
    """
    logger.info(f"Starting WebSocket price collection...")
    logger.info(f"Monitoring {len(tickers)} tickers")

    if duration_minutes:
        logger.info(f"Duration: {duration_minutes} minutes")
    else:
        logger.info("Duration: Indefinite (press Ctrl+C to stop)")

    # Price cache for tracking changes
    price_cache = {}

    # Create callback with notifier
    def callback(price):
        on_price_update(price, notifier, price_cache)

    # Start collection
    stats = collector.collect_realtime_prices(
        tickers=tickers,
        callback=callback,
        duration_minutes=duration_minutes
    )

    # Display final statistics
    logger.info("\n" + "="*60)
    logger.info("Collection Statistics")
    logger.info("="*60)
    logger.info(f"Total updates: {stats.total_updates}")
    logger.info(f"Duration: {stats.duration_seconds:.0f} seconds")

    if stats.updates_per_second:
        logger.info(f"Updates/second: {stats.updates_per_second:.2f}")

    logger.info(f"Connection errors: {stats.connection_errors}")

    logger.info("\nUpdates per ticker:")
    sorted_tickers = sorted(
        stats.updates_per_ticker.items(),
        key=lambda x: x[1],
        reverse=True
    )
    for ticker, count in sorted_tickers:
        logger.info(f"  {ticker:6s}: {count} updates")


def collect_polling(
    collector: FinnhubPriceCollector,
    tickers: list,
    interval: int = 5,
    duration_minutes: int = None
):
    """
    Collect prices using REST API polling.

    Args:
        collector: FinnhubPriceCollector instance
        tickers: List of ticker symbols
        interval: Seconds between polls
        duration_minutes: Duration in minutes (None = indefinite)
    """
    logger.info(f"Starting REST API price polling...")
    logger.info(f"Monitoring {len(tickers)} tickers")
    logger.info(f"Poll interval: {interval}s")

    if duration_minutes:
        logger.info(f"Duration: {duration_minutes} minutes")
    else:
        logger.info("Duration: Indefinite (press Ctrl+C to stop)")

    # Callback for each poll
    def callback(quotes):
        timestamp = datetime.utcnow().strftime('%H:%M:%S')
        logger.info(f"\n[{timestamp}] Price Update:")
        for ticker, quote in sorted(quotes.items()):
            logger.info(
                f"  {ticker:6s}: ${quote.current_price:8.2f} "
                f"({quote.percent_change:+6.2f}%)"
            )

    # Start polling
    stats = collector.poll_prices(
        tickers=tickers,
        interval_seconds=interval,
        callback=callback,
        duration_minutes=duration_minutes
    )

    # Display final statistics
    logger.info("\n" + "="*60)
    logger.info("Collection Statistics")
    logger.info("="*60)
    logger.info(f"Total updates: {stats.total_updates}")
    logger.info(f"Duration: {stats.duration_seconds:.0f} seconds")
    logger.info(f"Total polls: {stats.total_updates // len(tickers) if tickers else 0}")


def main():
    """Main entry point."""
    # Load environment
    load_dotenv()

    # Setup logging
    setup_logging()

    logger.info("="*60)
    logger.info("kkaak Price Collector (Finnhub)")
    logger.info("="*60)

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

    # Initialize Finnhub API client
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        logger.error("FINNHUB_API_KEY not found in environment")
        logger.error("Please set FINNHUB_API_KEY in .env file")
        logger.error("Get your free API key from: https://finnhub.io/register")
        sys.exit(1)

    try:
        collector = FinnhubPriceCollector(api_key=api_key)
        logger.info("Finnhub API client initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Finnhub client: {e}")
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
    parser = argparse.ArgumentParser(description="Collect US stock market prices")
    parser.add_argument(
        "--mode",
        choices=["snapshot", "websocket", "polling"],
        default="websocket",
        help="Collection mode (default: websocket)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Poll interval in seconds for polling mode (default: 5)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Duration in minutes (default: indefinite)"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Specific tickers to monitor (default: all from config)"
    )

    args = parser.parse_args()

    # Override tickers if specified
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
        logger.info(f"Using specified tickers: {', '.join(tickers)}")

    # Run collection
    try:
        if args.mode == "snapshot":
            collect_snapshot(collector, tickers)

        elif args.mode == "websocket":
            collect_websocket(collector, tickers, args.duration, notifier)

        elif args.mode == "polling":
            collect_polling(collector, tickers, args.interval, args.duration)

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
