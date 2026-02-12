#!/usr/bin/env python3
"""
Pipeline Test Script

Test the complete trading pipeline with sample data.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from main import TradingPipeline


def test_pre_market_analysis():
    """Test pre-market analysis."""
    logger.info("=" * 70)
    logger.info("TEST: PRE-MARKET ANALYSIS")
    logger.info("=" * 70)

    # Load environment
    load_dotenv()

    # Check API keys
    required_keys = ["MASSIVE_API_KEY", "FINNHUB_API_KEY", "OPENAI_API_KEY", "DISCORD_WEBHOOK_URL"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]

    if missing_keys:
        logger.error(f"Missing API keys: {', '.join(missing_keys)}")
        logger.info("Please set up your .env file with all required API keys")
        return False

    try:
        # Initialize pipeline
        pipeline = TradingPipeline(
            massive_api_key=os.getenv("MASSIVE_API_KEY"),
            finnhub_api_key=os.getenv("FINNHUB_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        )

        # Run pre-market analysis
        pipeline.run_pre_market_analysis()

        logger.success("✓ Pre-market analysis test passed")
        return True

    except Exception as e:
        logger.error(f"✗ Pre-market analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_realtime_analysis():
    """Test realtime analysis."""
    logger.info("=" * 70)
    logger.info("TEST: REALTIME ANALYSIS")
    logger.info("=" * 70)

    # Load environment
    load_dotenv()

    # Check API keys
    required_keys = ["MASSIVE_API_KEY", "FINNHUB_API_KEY", "OPENAI_API_KEY", "DISCORD_WEBHOOK_URL"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]

    if missing_keys:
        logger.error(f"Missing API keys: {', '.join(missing_keys)}")
        logger.info("Please set up your .env file with all required API keys")
        return False

    try:
        # Initialize pipeline
        pipeline = TradingPipeline(
            massive_api_key=os.getenv("MASSIVE_API_KEY"),
            finnhub_api_key=os.getenv("FINNHUB_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        )

        # Run realtime analysis
        pipeline.run_realtime_analysis()

        logger.success("✓ Realtime analysis test passed")
        return True

    except Exception as e:
        logger.error(f"✗ Realtime analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all pipeline tests."""
    logger.info("=" * 70)
    logger.info("🐦‍⬛ KKAAK Pipeline Test Suite")
    logger.info("=" * 70)

    results = []

    # Test pre-market analysis
    logger.info("\n")
    results.append(("Pre-Market Analysis", test_pre_market_analysis()))

    # Wait a bit between tests
    import time
    time.sleep(5)

    # Test realtime analysis
    logger.info("\n")
    results.append(("Realtime Analysis", test_realtime_analysis()))

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"  {test_name:25s}: {status}")

    all_passed = all(result[1] for result in results)

    logger.info("\n" + "=" * 70)
    if all_passed:
        logger.success("✓ ALL TESTS PASSED")
        logger.info("=" * 70)
        logger.info("\nYou can now run the main pipeline:")
        logger.info("  python main.py --test    # Test mode (run once)")
        logger.info("  python main.py           # Production mode (scheduled)")
        sys.exit(0)
    else:
        logger.error("✗ SOME TESTS FAILED")
        logger.info("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
