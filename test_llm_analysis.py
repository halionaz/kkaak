#!/usr/bin/env python3
"""
LLM Analysis Test

Test GPT-4o mini news analysis with sample data.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.analysis.llm_agent import LLMAgent
from src.analysis.models import TradingSignal


def load_sample_news(news_file: str = "data/news/news_20260212_222419.json") -> list:
    """Load sample news articles from file."""
    file_path = project_root / news_file

    if not file_path.exists():
        logger.error(f"News file not found: {file_path}")
        return []

    with open(file_path, encoding="utf-8") as f:
        articles = json.load(f)

    logger.info(f"Loaded {len(articles)} sample articles from {news_file}")
    return articles


def load_sample_prices(price_file: str = "data/prices/prices_20260212_224745.json") -> dict:
    """Load sample prices from file."""
    file_path = project_root / price_file

    if not file_path.exists():
        logger.warning(f"Price file not found: {file_path}. Using dummy prices.")
        # Return dummy prices for testing
        return {
            "AAPL": 275.50,
            "NVDA": 190.05,
            "AMD": 213.58,
            "GOOGL": 310.96,
            "MSFT": 404.37,
            "META": 668.69,
            "AMZN": 204.08,
            "TSLA": 428.27,
            "NFLX": 79.62,
            "ASML": 1435.63,
        }

    with open(file_path, encoding="utf-8") as f:
        price_data = json.load(f)

    # Extract current prices
    prices = {ticker: data["current_price"] for ticker, data in price_data.items()}

    logger.info(f"Loaded {len(prices)} prices from {price_file}")
    return prices


def test_pre_market_analysis(agent: LLMAgent):
    """Test pre-market analysis mode."""
    logger.info("=" * 70)
    logger.info("TEST: PRE-MARKET ANALYSIS")
    logger.info("=" * 70)

    # Load sample data
    news_articles = load_sample_news()
    current_prices = load_sample_prices()

    if not news_articles:
        logger.error("No news articles available for testing")
        return False

    # Limit to first 10 articles for testing
    news_articles = news_articles[:10]

    try:
        # Run analysis
        logger.info(f"Analyzing {len(news_articles)} articles...")
        result = agent.analyze_news(
            news_articles=news_articles,
            current_prices=current_prices,
            mode="pre_market",
            time_to_open="30 minutes",
        )

        # Display results
        logger.info("\n" + "-" * 70)
        logger.info("ANALYSIS RESULTS")
        logger.info("-" * 70)

        logger.info(f"\nMarket Sentiment: {result.market_sentiment.upper()}")
        logger.info(f"Market Summary: {result.market_summary}")
        logger.info(f"Risk Level: {result.overall_risk_level.value.upper()}")

        logger.info(f"\n📊 Ticker Signals ({len(result.ticker_analyses)}):\n")
        for analysis in result.ticker_analyses:
            signal_emoji = {
                TradingSignal.STRONG_BUY: "🚀",
                TradingSignal.BUY: "📈",
                TradingSignal.HOLD: "⏸️",
                TradingSignal.SELL: "📉",
                TradingSignal.STRONG_SELL: "🔻",
            }

            logger.info(
                f"{signal_emoji.get(analysis.signal, '•')} {analysis.ticker:8s} "
                f"| {analysis.signal.value:12s} "
                f"| Confidence: {analysis.confidence:.2f} "
                f"| {analysis.sentiment.upper()}"
            )
            logger.info(f"   Reasoning: {analysis.reasoning[:100]}...")

        logger.info("\n💡 Top Opportunities:")
        for idx, opp in enumerate(result.top_opportunities, 1):
            logger.info(f"   {idx}. {opp}")

        logger.info("\n⚠️  Top Risks:")
        for idx, risk in enumerate(result.top_risks, 1):
            logger.info(f"   {idx}. {risk}")

        logger.info(f"\n🎯 Priority Tickers: {', '.join(result.priority_tickers)}")
        logger.info(f"🚫 Avoid Tickers: {', '.join(result.avoid_tickers)}")

        logger.info("\n💰 Cost Analysis:")
        logger.info(f"   Tokens Used: {result.tokens_used:,}")
        logger.info(f"   Cost: ${result.cost_usd:.4f}")

        logger.info("\n" + "=" * 70)
        logger.success("✓ PRE-MARKET ANALYSIS TEST PASSED")
        logger.info("=" * 70 + "\n")

        return True

    except Exception as e:
        logger.error(f"✗ PRE-MARKET ANALYSIS TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_batch_analysis(agent: LLMAgent):
    """Test batch analysis mode."""
    logger.info("=" * 70)
    logger.info("TEST: BATCH ANALYSIS")
    logger.info("=" * 70)

    # Load sample data
    news_articles = load_sample_news()
    current_prices = load_sample_prices()

    if not news_articles:
        logger.error("No news articles available for testing")
        return False

    # Limit to first 15 articles
    news_articles = news_articles[:15]

    try:
        # Create batches (5 articles per batch)
        batches = LLMAgent.create_news_batches(news_articles, batch_size=5)

        logger.info(f"Created {len(batches)} batches")

        # Run batch analysis
        results = agent.batch_analyze(
            news_batches=batches,
            current_prices=current_prices,
            mode="pre_market",
        )

        # Display summary
        logger.info("\n" + "-" * 70)
        logger.info("BATCH ANALYSIS SUMMARY")
        logger.info("-" * 70)

        total_signals = sum(len(r.ticker_analyses) for r in results)
        total_cost = sum(r.cost_usd or 0.0 for r in results)
        total_tokens = sum(r.tokens_used or 0 for r in results)

        logger.info(f"\nBatches Processed: {len(results)}/{len(batches)}")
        logger.info(f"Total Signals: {total_signals}")
        logger.info(f"Total Tokens: {total_tokens:,}")
        logger.info(f"Total Cost: ${total_cost:.4f}")

        for idx, result in enumerate(results, 1):
            logger.info(
                f"\nBatch {idx}: {len(result.ticker_analyses)} signals, "
                f"{result.tokens_used:,} tokens, ${result.cost_usd:.4f}"
            )

        logger.info("\n" + "=" * 70)
        logger.success("✓ BATCH ANALYSIS TEST PASSED")
        logger.info("=" * 70 + "\n")

        return True

    except Exception as e:
        logger.error(f"✗ BATCH ANALYSIS TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_json_parsing(agent: LLMAgent):
    """Test JSON response parsing."""
    logger.info("=" * 70)
    logger.info("TEST: JSON RESPONSE PARSING")
    logger.info("=" * 70)

    # Load minimal sample
    news_articles = load_sample_news()[:3]
    current_prices = load_sample_prices()

    try:
        result = agent.analyze_news(
            news_articles=news_articles,
            current_prices=current_prices,
            mode="pre_market",
        )

        # Validate result structure
        assert result.market_sentiment in ["bullish", "bearish", "neutral"]
        assert result.market_summary
        assert result.overall_risk_level
        assert isinstance(result.ticker_analyses, list)
        assert isinstance(result.top_opportunities, list)
        assert isinstance(result.top_risks, list)
        assert result.tokens_used > 0
        assert result.cost_usd > 0

        logger.success("✓ All JSON fields validated successfully")

        logger.info("\n" + "=" * 70)
        logger.success("✓ JSON PARSING TEST PASSED")
        logger.info("=" * 70 + "\n")

        return True

    except AssertionError as e:
        logger.error(f"✗ JSON PARSING TEST FAILED: Validation error: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ JSON PARSING TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    # Load environment
    load_dotenv()

    logger.info("\n" + "=" * 70)
    logger.info("KKAAK LLM ANALYSIS TEST SUITE")
    logger.info("=" * 70)

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("✗ ERROR: OPENAI_API_KEY not found in environment")
        logger.info("\nPlease ensure you have:")
        logger.info("1. Created a .env file (copy from .env.example)")
        logger.info("2. Added your OpenAI API key to .env:")
        logger.info("   OPENAI_API_KEY=your_api_key_here")
        logger.info("\nGet your API key from: https://platform.openai.com/api-keys\n")
        sys.exit(1)

    # Initialize agent
    logger.info("\nInitializing LLM agent with model: gpt-4o-mini")
    agent = LLMAgent(api_key=api_key)

    # Run tests
    results = []

    results.append(("JSON Parsing", test_json_parsing(agent)))
    results.append(("Pre-Market Analysis", test_pre_market_analysis(agent)))
    results.append(("Batch Analysis", test_batch_analysis(agent)))

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70 + "\n")

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"  {test_name:25s}: {status}")

    all_passed = all(result[1] for result in results)

    logger.info("\n" + "=" * 70)
    if all_passed:
        logger.success("✓ ALL TESTS PASSED - LLM Analysis System Ready!")
        logger.info("=" * 70 + "\n")
        logger.info("Next steps:")
        logger.info("  1. Integrate with news collector")
        logger.info("  2. Add real-time price streaming")
        logger.info("  3. Implement trading signal executor")
        logger.info("")
        sys.exit(0)
    else:
        logger.error("✗ SOME TESTS FAILED - Please fix the issues above")
        logger.info("=" * 70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
