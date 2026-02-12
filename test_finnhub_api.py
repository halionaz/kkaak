#!/usr/bin/env python3
"""
Finnhub API Connection Test

Quick test script to verify Finnhub API connectivity and functionality.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.data.price_collector import FinnhubPriceCollector
from src.utils.config_loader import ConfigLoader


def test_api_connection(api_key: str):
    """Test basic API connection."""
    print("\n" + "="*70)
    print("FINNHUB API CONNECTION TEST")
    print("="*70 + "\n")

    try:
        print("1. Initializing Finnhub API client...")
        collector = FinnhubPriceCollector(api_key=api_key)
        print("   ✓ Client initialized successfully\n")

        print("2. Fetching current quotes...")
        test_tickers = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL"]

        quotes = collector.get_quotes(test_tickers)

        if not quotes:
            print("   ⚠️  No quotes received. Please check your API key.")
            return False

        print(f"   ✓ Fetched {len(quotes)} quotes\n")

        # Display quotes
        print("3. Current Market Quotes:\n")
        print("-"*70)

        for ticker, quote in sorted(quotes.items()):
            change_symbol = "▲" if quote.change >= 0 else "▼"
            change_color = "+" if quote.change >= 0 else ""

            print(f"\n{ticker:6s}: ${quote.current_price:8.2f} "
                  f"{change_symbol} {change_color}{quote.change:.2f} "
                  f"({change_color}{quote.percent_change:.2f}%)")
            print(f"        Open: ${quote.open:.2f} | "
                  f"High: ${quote.high:.2f} | "
                  f"Low: ${quote.low:.2f}")
            print(f"        Previous Close: ${quote.previous_close:.2f}")

        print("\n" + "-"*70)

        # Statistics
        print("\n4. Statistics:\n")

        total_volume = sum(q.high - q.low for q in quotes.values())
        avg_change = sum(q.percent_change for q in quotes.values()) / len(quotes)

        positive_count = sum(1 for q in quotes.values() if q.change > 0)
        negative_count = sum(1 for q in quotes.values() if q.change < 0)

        print(f"   Average change: {avg_change:+.2f}%")
        print(f"   Positive: {positive_count} | Negative: {negative_count}")
        print(f"   Market sentiment: {'📈 Bullish' if avg_change > 0 else '📉 Bearish'}")

        print("\n" + "="*70)
        print("✓ API CONNECTION TEST PASSED")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_websocket_connection(api_key: str):
    """Test WebSocket connection."""
    print("\n" + "="*70)
    print("WEBSOCKET CONNECTION TEST")
    print("="*70 + "\n")

    try:
        print("1. Initializing WebSocket collector...")
        collector = FinnhubPriceCollector(api_key=api_key)
        print("   ✓ Collector initialized\n")

        print("2. Testing WebSocket connection (10 seconds)...")
        test_tickers = ["AAPL", "NVDA"]

        update_count = [0]  # Use list to allow modification in closure

        def on_update(price):
            update_count[0] += 1
            print(f"   [{price.timestamp.strftime('%H:%M:%S')}] "
                  f"{price.ticker}: ${price.price:.2f} (Vol: {price.volume:,})")

        stats = collector.collect_realtime_prices(
            tickers=test_tickers,
            callback=on_update,
            duration_minutes=10/60  # 10 seconds
        )

        print("\n3. WebSocket Statistics:\n")
        print(f"   Total updates: {stats.total_updates}")
        print(f"   Duration: {stats.duration_seconds:.1f} seconds")

        if stats.updates_per_second:
            print(f"   Updates/second: {stats.updates_per_second:.2f}")

        print(f"   Errors: {stats.connection_errors}")

        if stats.total_updates > 0:
            print("\n   Updates per ticker:")
            for ticker, count in sorted(stats.updates_per_ticker.items()):
                print(f"   • {ticker}: {count} updates")

        print("\n" + "="*70)

        if stats.total_updates > 0:
            print("✓ WEBSOCKET TEST PASSED")
        else:
            print("⚠️  WEBSOCKET TEST COMPLETED (No updates received - market may be closed)")

        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ WEBSOCKET TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_config_loader():
    """Test configuration loading."""
    print("\n" + "="*70)
    print("CONFIGURATION TEST")
    print("="*70 + "\n")

    try:
        print("1. Loading configuration...")
        loader = ConfigLoader()
        print("   ✓ ConfigLoader initialized\n")

        print("2. Loading stocks from config/stocks.yaml...")
        stocks = loader.load_stocks()
        print(f"   ✓ Loaded {len(stocks)} stocks\n")

        print("3. Stock List:\n")

        # Group by priority
        high_priority = [s for s in stocks if s.priority == 1]
        medium_priority = [s for s in stocks if s.priority == 2]

        print(f"   High Priority (Priority 1): {len(high_priority)} stocks")
        for stock in high_priority:
            print(f"   • {stock.ticker:8s} - {stock.name:40s} [{stock.sector}]")

        print(f"\n   Medium Priority (Priority 2): {len(medium_priority)} stocks")
        for stock in medium_priority:
            print(f"   • {stock.ticker:8s} - {stock.name:40s} [{stock.sector}]")

        print("\n" + "="*70)
        print("✓ CONFIGURATION TEST PASSED")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ CONFIGURATION TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner."""
    # Load environment variables
    load_dotenv()

    print("\n" + "="*70)
    print("KKAAK FINNHUB TEST SUITE")
    print("="*70)

    # Check environment variables
    api_key = os.getenv("FINNHUB_API_KEY")

    if not api_key:
        print("\n✗ ERROR: FINNHUB_API_KEY not found in environment")
        print("\nPlease ensure you have:")
        print("1. Created a .env file (copy from .env.example)")
        print("2. Added your Finnhub API key to .env:")
        print("   FINNHUB_API_KEY=your_api_key_here")
        print("\nGet your free API key from: https://finnhub.io/register\n")
        sys.exit(1)

    # Run tests
    results = []

    # Test 1: Configuration
    results.append(("Configuration", test_config_loader()))

    # Test 2: API Connection
    results.append(("Finnhub API", test_api_connection(api_key)))

    # Test 3: WebSocket Connection
    results.append(("WebSocket", test_websocket_connection(api_key)))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name:20s}: {status}")

    all_passed = all(result[1] for result in results)

    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL TESTS PASSED - System is ready to use!")
        print("="*70 + "\n")
        print("Next steps:")
        print("  1. Snapshot: python collect_prices.py --mode snapshot")
        print("  2. WebSocket: python collect_prices.py --mode websocket --duration 5")
        print("  3. Polling: python collect_prices.py --mode polling --interval 5 --duration 5")
        print()
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED - Please fix the issues above")
        print("="*70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
