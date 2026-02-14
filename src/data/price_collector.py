"""
Price Collector Module

Collects real-time US stock market prices and volumes using Finnhub API.
"""

import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

from loguru import logger

try:
    import finnhub
    import websocket

    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False
    logger.warning(
        "finnhub-python library not installed. Run: pip install finnhub-python websocket-client"
    )

from .models import PriceCollectionStats, StockPrice, StockQuote


class FinnhubPriceCollector:
    """Collects real-time stock prices from Finnhub API."""

    def __init__(self, api_key: str):
        """
        Initialize Finnhub price collector.

        Args:
            api_key: Finnhub API key
        """
        if not FINNHUB_AVAILABLE:
            raise ImportError(
                "finnhub-python library is required. Install it with: pip install finnhub-python websocket-client"
            )

        self.api_key = api_key
        self.client = finnhub.Client(api_key=api_key)

        # WebSocket state
        self.ws: websocket.WebSocketApp | None = None
        self.ws_thread: threading.Thread | None = None
        self.is_connected = False
        self.subscribed_tickers: list[str] = []

        # Callbacks
        self.on_price_update: Callable[[StockPrice], None] | None = None

        # Statistics
        self.stats = PriceCollectionStats()

        logger.info("FinnhubPriceCollector initialized")

    def get_quote(self, ticker: str) -> StockQuote | None:
        """
        Get current quote for a ticker (REST API).

        Args:
            ticker: Stock ticker symbol

        Returns:
            StockQuote object or None if failed
        """
        try:
            quote_data = self.client.quote(ticker)

            # Check if valid data
            if not quote_data or quote_data.get("c") == 0:
                logger.warning(f"No data available for {ticker}")
                return None

            quote = StockQuote(
                ticker=ticker,
                c=quote_data["c"],  # current price
                d=quote_data["d"],  # change
                dp=quote_data["dp"],  # percent change
                h=quote_data["h"],  # high
                l=quote_data["l"],  # low
                o=quote_data["o"],  # open
                pc=quote_data["pc"],  # previous close
            )

            return quote

        except Exception as e:
            logger.error(f"Failed to get quote for {ticker}: {e}")
            return None

    def get_quotes(self, tickers: list[str]) -> dict[str, StockQuote]:
        """
        Get current quotes for multiple tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dictionary mapping ticker to StockQuote
        """
        quotes = {}

        for ticker in tickers:
            quote = self.get_quote(ticker)
            if quote:
                quotes[ticker] = quote
                logger.debug(f"{ticker}: ${quote.current_price:.2f} ({quote.percent_change:+.2f}%)")

        return quotes

    def start_websocket(
        self, tickers: list[str], callback: Callable[[StockPrice], None] | None = None
    ):
        """
        Start WebSocket connection for real-time price updates.

        Args:
            tickers: List of ticker symbols to subscribe
            callback: Optional callback function(StockPrice) for each update
        """
        if self.is_connected:
            logger.warning("WebSocket already connected")
            return

        self.subscribed_tickers = tickers
        self.on_price_update = callback

        # Create WebSocket connection
        ws_url = f"wss://ws.finnhub.io?token={self.api_key}"

        def on_message(ws, message):
            """Handle incoming WebSocket message."""
            try:
                data = json.loads(message)

                # Check message type
                if data.get("type") == "trade":
                    # Process trade data
                    for trade in data.get("data", []):
                        price_update = StockPrice(
                            ticker=trade["s"],
                            price=trade["p"],
                            volume=trade["v"],
                            timestamp=datetime.fromtimestamp(trade["t"] / 1000),
                            trade_conditions=trade.get("c", []),
                        )

                        # Update statistics
                        self.stats.add_update(price_update.ticker)

                        # Call callback if provided
                        if self.on_price_update:
                            try:
                                self.on_price_update(price_update)
                            except Exception as e:
                                logger.error(f"Callback error for {price_update.ticker}: {e}")

                elif data.get("type") == "ping":
                    # Respond to ping
                    logger.debug("Received ping")

                elif data.get("type") == "error":
                    logger.error(f"WebSocket error: {data.get('msg')}")
                    self.stats.add_error()

            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                self.stats.add_error()

        def on_error(ws, error):
            """Handle WebSocket error."""
            logger.error(f"WebSocket error: {error}")
            self.stats.add_error()

        def on_close(ws, close_status_code, close_msg):
            """Handle WebSocket close."""
            logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
            self.is_connected = False

        def on_open(ws):
            """Handle WebSocket open."""
            logger.info("WebSocket connection established")
            self.is_connected = True

            # Subscribe to tickers
            for ticker in self.subscribed_tickers:
                subscribe_msg = json.dumps({"type": "subscribe", "symbol": ticker})
                ws.send(subscribe_msg)
                logger.info(f"Subscribed to {ticker}")

        # Create WebSocket app
        self.ws = websocket.WebSocketApp(
            ws_url, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open
        )

        # Run WebSocket in separate thread
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()

        logger.info(f"WebSocket started for {len(tickers)} tickers")

    def stop_websocket(self):
        """Stop WebSocket connection."""
        if not self.is_connected:
            logger.warning("WebSocket not connected")
            return

        # Unsubscribe from tickers
        if self.ws:
            for ticker in self.subscribed_tickers:
                unsubscribe_msg = json.dumps({"type": "unsubscribe", "symbol": ticker})
                try:
                    self.ws.send(unsubscribe_msg)
                    logger.debug(f"Unsubscribed from {ticker}")
                except Exception as e:
                    logger.error(f"Failed to unsubscribe from {ticker}: {e}")

            # Close connection
            self.ws.close()

        # Wait for thread to finish
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)

        self.is_connected = False
        self.stats.finish()

        logger.info("WebSocket stopped")

    def collect_realtime_prices(
        self,
        tickers: list[str],
        callback: Callable[[StockPrice], None] | None = None,
        duration_minutes: int | None = None,
    ) -> PriceCollectionStats:
        """
        Collect real-time prices using WebSocket.

        Args:
            tickers: List of ticker symbols to monitor
            callback: Optional callback function(StockPrice) for each update
            duration_minutes: Run for specified minutes (None = indefinite)

        Returns:
            PriceCollectionStats with collection statistics
        """
        self.stats = PriceCollectionStats()

        logger.info(f"Starting real-time price collection for {len(tickers)} tickers")

        if duration_minutes:
            logger.info(f"Duration: {duration_minutes} minutes")
        else:
            logger.info("Duration: Indefinite (press Ctrl+C to stop)")

        try:
            # Start WebSocket
            self.start_websocket(tickers, callback)

            # Wait for specified duration or indefinitely
            if duration_minutes:
                time.sleep(duration_minutes * 60)
                logger.info(f"Collection duration reached: {duration_minutes} minutes")
            else:
                # Wait indefinitely (until Ctrl+C)
                while True:
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Collection stopped by user")

        finally:
            # Stop WebSocket
            self.stop_websocket()

        return self.stats

    def poll_prices(
        self,
        tickers: list[str],
        interval_seconds: int = 5,
        callback: Callable[[dict[str, StockQuote]], None] | None = None,
        duration_minutes: int | None = None,
    ) -> PriceCollectionStats:
        """
        Poll prices using REST API (alternative to WebSocket).

        Args:
            tickers: List of ticker symbols to monitor
            interval_seconds: Seconds between polls
            callback: Optional callback function(quotes_dict) for each poll
            duration_minutes: Run for specified minutes (None = indefinite)

        Returns:
            PriceCollectionStats with collection statistics
        """
        self.stats = PriceCollectionStats()
        start_time = datetime.now(UTC)

        logger.info(f"Starting price polling for {len(tickers)} tickers")
        logger.info(f"Poll interval: {interval_seconds}s")

        if duration_minutes:
            logger.info(f"Duration: {duration_minutes} minutes")
        else:
            logger.info("Duration: Indefinite (press Ctrl+C to stop)")

        try:
            while True:
                # Check if we should stop
                if duration_minutes:
                    elapsed = (datetime.now(UTC) - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        logger.info(f"Collection duration reached: {elapsed:.1f} minutes")
                        break

                # Fetch quotes
                quotes = self.get_quotes(tickers)

                # Update statistics
                for ticker in quotes:
                    self.stats.add_update(ticker)

                # Call callback if provided
                if callback and quotes:
                    try:
                        callback(quotes)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

                # Wait before next poll
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("Collection stopped by user")

        finally:
            self.stats.finish()

        return self.stats


def test_price_collection(api_key: str, tickers: list[str], use_websocket: bool = True):
    """
    Test price collection functionality.

    Args:
        api_key: Finnhub API key
        tickers: List of tickers to test
        use_websocket: Use WebSocket (True) or REST polling (False)
    """
    print(f"\n{'=' * 60}")
    print("Testing Finnhub Price Collector")
    print(f"{'=' * 60}\n")

    collector = FinnhubPriceCollector(api_key=api_key)

    # Test REST API - Get quotes
    print(f"Fetching current quotes for: {', '.join(tickers)}\n")
    quotes = collector.get_quotes(tickers)

    print(f"{'=' * 60}")
    print("Current Market Quotes")
    print(f"{'=' * 60}\n")

    for ticker, quote in quotes.items():
        print(
            f"{ticker:6s}: ${quote.current_price:8.2f} "
            f"({quote.percent_change:+6.2f}%) "
            f"Vol: {quote.high:.2f}H / {quote.low:.2f}L"
        )

    print(f"\n{'=' * 60}\n")

    # Test real-time updates
    if use_websocket:
        print("Testing WebSocket real-time updates (30 seconds)...\n")

        def on_update(price: StockPrice):
            print(
                f"[{price.timestamp.strftime('%H:%M:%S')}] "
                f"{price.ticker:6s}: ${price.price:8.2f} "
                f"(Vol: {price.volume:,})"
            )

        stats = collector.collect_realtime_prices(
            tickers=tickers,
            callback=on_update,
            duration_minutes=0.5,  # 30 seconds
        )

        print(f"\n{'=' * 60}")
        print("WebSocket Collection Statistics")
        print(f"{'=' * 60}\n")
        print(f"Total updates: {stats.total_updates}")
        print(f"Duration: {stats.duration_seconds:.1f} seconds")
        print(f"Updates/second: {stats.updates_per_second:.2f}" if stats.updates_per_second else "")
        print(f"Errors: {stats.connection_errors}")

        print("\nUpdates per ticker:")
        for ticker, count in sorted(stats.updates_per_ticker.items()):
            print(f"  {ticker:6s}: {count} updates")

    else:
        print("Testing REST API polling (30 seconds, 5s interval)...\n")

        def on_poll(quotes_dict: dict[str, StockQuote]):
            timestamp = datetime.now(UTC).strftime("%H:%M:%S")
            print(f"[{timestamp}] Poll update:")
            for ticker, quote in quotes_dict.items():
                print(f"  {ticker:6s}: ${quote.current_price:8.2f} ({quote.percent_change:+6.2f}%)")

        stats = collector.poll_prices(
            tickers=tickers,
            interval_seconds=5,
            callback=on_poll,
            duration_minutes=0.5,  # 30 seconds
        )

        print(f"\n{'=' * 60}")
        print("REST Polling Statistics")
        print(f"{'=' * 60}\n")
        print(f"Total updates: {stats.total_updates}")
        print(f"Duration: {stats.duration_seconds:.1f} seconds")
        print(f"Polls: {stats.total_updates // len(tickers)}")


if __name__ == "__main__":
    import os
    import sys

    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    api_key = os.getenv("FINNHUB_API_KEY")

    if not api_key:
        print("Error: FINNHUB_API_KEY not found in .env file")
        print("Please set your Finnhub API key in .env file")
        sys.exit(1)

    # Test tickers
    test_tickers = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL"]

    try:
        # Test WebSocket
        test_price_collection(api_key, test_tickers, use_websocket=True)

        print("\n" + "=" * 60 + "\n")

        # Test REST polling
        # test_price_collection(api_key, test_tickers, use_websocket=False)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
