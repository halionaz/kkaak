#!/usr/bin/env python3
"""
Massive API Connection Test

Quick test script to verify Massive API connectivity and functionality.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.data.news_collector import MassiveNewsCollector
from src.utils.config_loader import ConfigLoader


def test_api_connection(api_key: str):
    """Test basic API connection."""
    print("\n" + "=" * 70)
    print("MASSIVE API CONNECTION TEST")
    print("=" * 70 + "\n")

    try:
        print("1. Initializing Massive API client...")
        collector = MassiveNewsCollector(api_key=api_key, verbose=False)
        print("   ✓ Client initialized successfully\n")

        print("2. Fetching latest news (last 6 hours)...")
        test_tickers = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL"]

        articles = collector.fetch_news(tickers=test_tickers, limit=10, order="desc")

        print(f"   ✓ Fetched {len(articles)} articles\n")

        if not articles:
            print("   ⚠️  No articles found. This might be normal if there's no recent news.")
            print("      Try increasing the time range or checking different tickers.\n")
            return True

        # Display sample articles
        print("3. Sample Articles:\n")
        print("-" * 70)

        for i, article in enumerate(articles[:5], 1):
            print(f"\n{i}. {article.title}")
            print(f"   Published: {article.published_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"   Tickers: {', '.join(article.tickers) if article.tickers else 'None'}")
            print(f"   Sentiment: {article.overall_sentiment}")

            if article.description:
                desc = (
                    article.description[:100] + "..."
                    if len(article.description) > 100
                    else article.description
                )
                print(f"   Summary: {desc}")

            print(f"   URL: {article.article_url}")

        print("\n" + "-" * 70)

        # Statistics
        print("\n4. Statistics:\n")

        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        ticker_counts = {}

        for article in articles:
            sentiment_counts[article.overall_sentiment] += 1
            for ticker in article.tickers:
                ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1

        print("   Sentiment Distribution:")
        for sentiment, count in sentiment_counts.items():
            percentage = (count / len(articles) * 100) if articles else 0
            bar = "█" * int(percentage / 5)
            print(f"   • {sentiment.capitalize():8s}: {count:2d} ({percentage:5.1f}%) {bar}")

        if ticker_counts:
            print("\n   Most Mentioned Tickers:")
            sorted_tickers = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)
            for ticker, count in sorted_tickers[:10]:
                print(f"   • {ticker:6s}: {count:2d} articles")

        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def test_config_loader():
    """Test configuration loading."""
    print("\n" + "=" * 70)
    print("CONFIGURATION TEST")
    print("=" * 70 + "\n")

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

        # Sector distribution
        print("\n4. Sector Distribution:\n")
        sector_counts = {}
        for stock in stocks:
            sector_counts[stock.sector] = sector_counts.get(stock.sector, 0) + 1

        for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {sector:15s}: {count:2d} stocks")

        print("\n" + "=" * 70)
        print("✓ CONFIGURATION TEST PASSED")
        print("=" * 70 + "\n")

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

    print("\n" + "=" * 70)
    print("KKAAK SYSTEM TEST SUITE")
    print("=" * 70)

    # Check environment variables
    api_key = os.getenv("MASSIVE_API_KEY")

    if not api_key:
        print("\n✗ ERROR: MASSIVE_API_KEY not found in environment")
        print("\nPlease ensure you have:")
        print("1. Created a .env file (copy from .env.example)")
        print("2. Added your Massive API key to .env:")
        print("   MASSIVE_API_KEY=your_api_key_here")
        print("\nGet your API key from: https://massive.com/dashboard/api-keys\n")
        sys.exit(1)

    # Run tests
    results = []

    # Test 1: Configuration
    results.append(("Configuration", test_config_loader()))

    # Test 2: API Connection
    results.append(("Massive API", test_api_connection(api_key)))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70 + "\n")

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name:20s}: {status}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED - System is ready to use!")
        print("=" * 70 + "\n")
        print("Next steps:")
        print("  1. Run: python collect_news.py --mode historical --hours 24")
        print("  2. Or run: python collect_news.py --mode realtime --interval 60")
        print()
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED - Please fix the issues above")
        print("=" * 70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
