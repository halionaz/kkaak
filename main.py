#!/usr/bin/env python3
"""
KKAAK Trading Pipeline

Main entry point for the trading signal generation system.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dotenv import load_dotenv
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.data.news_collector import MassiveNewsCollector
from src.data.price_collector import FinnhubPriceCollector
from src.analysis.llm_agent import LLMAgent
from src.pipeline.signal_manager import SignalManager
from src.pipeline.position_tracker import PositionTracker
from src.pipeline.scheduler import TradingScheduler
from src.notification.discord_notifier import DiscordNotifier
from src.utils.config_loader import load_stocks


class TradingPipeline:
    """Main trading pipeline orchestrator."""

    def __init__(
        self,
        massive_api_key: str,
        finnhub_api_key: str,
        openai_api_key: str,
        discord_webhook_url: str,
    ):
        """
        Initialize trading pipeline.

        Args:
            massive_api_key: Massive API key
            finnhub_api_key: Finnhub API key
            openai_api_key: OpenAI API key
            discord_webhook_url: Discord webhook URL
        """
        # Load monitored stocks
        self.stocks = load_stocks()
        self.tickers = [stock["ticker"] for stock in self.stocks]

        logger.info(f"Monitoring {len(self.tickers)} stocks: {', '.join(self.tickers)}")

        # Initialize components
        self.news_collector = MassiveNewsCollector(api_key=massive_api_key)
        self.price_collector = FinnhubPriceCollector(api_key=finnhub_api_key)
        self.llm_agent = LLMAgent(api_key=openai_api_key)
        self.signal_manager = SignalManager()
        self.position_tracker = PositionTracker()
        self.discord = DiscordNotifier(webhook_url=discord_webhook_url)

        # Cache for prices (for comparison)
        self.previous_prices: Dict[str, float] = {}

        logger.success("Trading pipeline initialized")

    def run_pre_market_analysis(self) -> None:
        """
        Execute pre-market analysis.

        Workflow:
        1. Fetch overnight news (last 24 hours)
        2. Get current prices
        3. Analyze with LLM (pre_market mode)
        4. Generate signals
        5. Update positions
        6. Send Discord notification
        """
        logger.info("=" * 70)
        logger.info("🔔 PRE-MARKET ANALYSIS")
        logger.info("=" * 70)

        try:
            # 1. Fetch overnight news
            logger.info("Fetching overnight news (last 24 hours)...")
            news_articles = self.news_collector.fetch_latest_for_tickers(
                tickers=self.tickers,
                hours_back=24,
                limit_per_ticker=10,
            )

            if not news_articles:
                logger.warning("No news articles found")
                self.discord.send_error(
                    error_message="⚠️ Pre-market analysis: No news found",
                    context="Last 24 hours"
                )
                return

            logger.info(f"Fetched {len(news_articles)} news articles")

            # 2. Get current prices
            logger.info("Fetching current prices...")
            quotes = self.price_collector.get_quotes(self.tickers)
            current_prices = {
                ticker: quote.current_price
                for ticker, quote in quotes.items()
            }

            logger.info(f"Fetched prices for {len(current_prices)} tickers")

            # 3. Analyze with LLM
            logger.info("Analyzing news with GPT-4o mini...")

            # Convert NewsArticle objects to dicts
            news_dicts = [
                {
                    "id": article.id,
                    "title": article.title,
                    "description": article.description,
                    "published_utc": article.published_utc.isoformat(),
                    "tickers": article.tickers,
                }
                for article in news_articles
            ]

            analysis_result = self.llm_agent.analyze_news(
                news_articles=news_dicts,
                current_prices=current_prices,
                mode="pre_market",
                time_to_open="30 minutes",
            )

            logger.success(
                f"Analysis complete. "
                f"Signals: {len(analysis_result.ticker_analyses)}, "
                f"Cost: ${analysis_result.cost_usd:.4f}"
            )

            # 4. Generate signals
            logger.info("Generating trading signals...")
            signals = self.signal_manager.generate_signals(
                analysis_result=analysis_result,
                mode="pre_market",
            )

            # Save signals
            self.signal_manager.save_signals(signals)

            # Get summary
            summary = self.signal_manager.get_summary(signals)

            logger.info(
                f"Signals generated: "
                f"BUY {summary['buy']}, "
                f"SELL {summary['sell']}, "
                f"HOLD {summary['hold']}"
            )

            # 5. Update positions
            logger.info("Updating positions...")
            changes = self.position_tracker.update_positions(signals)

            actionable_changes = self.position_tracker.get_actionable_changes(changes)

            if actionable_changes:
                logger.info(f"Detected {len(actionable_changes)} actionable position changes")

            # 6. Send Discord notification
            logger.info("Sending Discord notification...")

            # Prepare signals for Discord
            discord_signals = []
            for ticker, signal in signals.items():
                discord_signals.append({
                    "ticker": ticker,
                    "action": signal["action"],
                    "confidence": signal["confidence"],
                    "reasoning": signal["reasoning"],
                })

            # Send pre-market report
            self.discord.send_premarket_report(
                signals=discord_signals,
                news_summary=analysis_result.market_summary,
            )

            logger.success("✓ Pre-market analysis completed successfully")

        except Exception as e:
            logger.error(f"Pre-market analysis failed: {e}")
            import traceback
            traceback.print_exc()

            # Send error notification
            self.discord.send_error(
                error_message="🚨 Pre-market analysis failed",
                context=str(e),
                retry_info="다음 분석: 내일 08:30 ET"
            )

    def run_realtime_analysis(self) -> None:
        """
        Execute realtime analysis.

        Workflow:
        1. Fetch recent news (last 30 minutes)
        2. Get current prices
        3. Compare with previous prices
        4. Analyze with LLM (realtime mode)
        5. Generate signals (conservative filtering)
        6. Detect position changes
        7. Send Discord notifications (changes only)
        """
        logger.info("=" * 70)
        logger.info("🚨 REALTIME ANALYSIS")
        logger.info("=" * 70)

        try:
            # 1. Fetch recent news
            logger.info("Fetching recent news (last 30 minutes)...")

            # Use 35 minutes to ensure we don't miss anything
            news_articles = self.news_collector.fetch_latest_for_tickers(
                tickers=self.tickers,
                hours_back=1,  # 1 hour window
                limit_per_ticker=5,
            )

            # Filter to last 35 minutes
            now = datetime.utcnow()
            cutoff_time = now - timedelta(minutes=35)
            recent_news = [
                article for article in news_articles
                if article.published_utc >= cutoff_time
            ]

            logger.info(f"Found {len(recent_news)} recent articles")

            # If no news, skip analysis (no changes expected)
            if not recent_news:
                logger.info("No recent news. Skipping analysis.")
                return

            # 2. Get current prices
            logger.info("Fetching current prices...")
            quotes = self.price_collector.get_quotes(self.tickers)
            current_prices = {
                ticker: quote.current_price
                for ticker, quote in quotes.items()
            }

            logger.info(f"Fetched prices for {len(current_prices)} tickers")

            # 3. Get previous prices (for comparison)
            previous_prices = self.previous_prices.copy() if self.previous_prices else None

            # Update previous prices cache
            self.previous_prices = current_prices.copy()

            # 4. Analyze with LLM
            logger.info("Analyzing news with GPT-4o mini...")

            # Convert NewsArticle objects to dicts
            news_dicts = [
                {
                    "id": article.id,
                    "title": article.title,
                    "description": article.description,
                    "published_utc": article.published_utc.isoformat(),
                    "tickers": article.tickers,
                }
                for article in recent_news
            ]

            analysis_result = self.llm_agent.analyze_news(
                news_articles=news_dicts,
                current_prices=current_prices,
                previous_prices=previous_prices,
                mode="realtime",
                market_status="OPEN",
                time_window="30 minutes",
            )

            logger.success(
                f"Analysis complete. "
                f"Signals: {len(analysis_result.ticker_analyses)}, "
                f"Cost: ${analysis_result.cost_usd:.4f}"
            )

            # 5. Generate signals (with conservative filtering)
            logger.info("Generating trading signals (conservative mode)...")

            # Load previous signals for conservative filtering
            previous_signals = self.signal_manager.get_latest_signals()

            signals = self.signal_manager.generate_signals(
                analysis_result=analysis_result,
                mode="realtime",
                previous_signals=previous_signals,
            )

            # Save signals
            self.signal_manager.save_signals(signals)

            # 6. Update positions and detect changes
            logger.info("Updating positions...")
            changes = self.position_tracker.update_positions(signals)

            actionable_changes = self.position_tracker.get_actionable_changes(changes)

            if not actionable_changes:
                logger.info("No actionable changes detected")
                return

            logger.info(f"Detected {len(actionable_changes)} actionable position changes")

            # 7. Send Discord notifications (changes only)
            logger.info("Sending Discord notifications for changes...")

            for ticker, change in actionable_changes.items():
                # Get current quote
                quote = quotes.get(ticker)

                # Prepare price data
                price_data = None
                if quote:
                    price_data = {
                        "current": quote.current_price,
                        "change_percent": quote.percent_change,
                    }

                # Get news title if available
                ticker_news = [n for n in recent_news if ticker in n.tickers]
                news_title = ticker_news[0].title if ticker_news else None
                news_url = ticker_news[0].article_url if ticker_news else None

                # Send realtime signal
                self.discord.send_realtime_signal(
                    ticker=ticker,
                    action=change["new_action"],
                    confidence=change["new_confidence"],
                    reasoning=change["reasoning"][:200],
                    price_data=price_data,
                    news_title=news_title,
                    news_url=news_url,
                )

                logger.info(f"Sent notification for {ticker}")

            logger.success("✓ Realtime analysis completed successfully")

        except Exception as e:
            logger.error(f"Realtime analysis failed: {e}")
            import traceback
            traceback.print_exc()

            # Send error notification
            self.discord.send_error(
                error_message="🚨 Realtime analysis failed",
                context=str(e),
                retry_info="다음 분석: 30분 후"
            )


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    logger.info("=" * 70)
    logger.info("🐦‍⬛ KKAAK - Trading Signal Bot")
    logger.info("=" * 70)

    # Check required environment variables
    required_vars = [
        "MASSIVE_API_KEY",
        "FINNHUB_API_KEY",
        "OPENAI_API_KEY",
        "DISCORD_WEBHOOK_URL",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        logger.info("\nPlease ensure you have:")
        logger.info("1. Created a .env file (copy from .env.example)")
        logger.info("2. Added all required API keys to .env")
        logger.info("\nRequired keys:")
        for var in required_vars:
            logger.info(f"   - {var}")
        sys.exit(1)

    # Initialize pipeline
    pipeline = TradingPipeline(
        massive_api_key=os.getenv("MASSIVE_API_KEY"),
        finnhub_api_key=os.getenv("FINNHUB_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
    )

    # Check if test mode
    test_mode = "--test" in sys.argv

    # Initialize scheduler
    scheduler = TradingScheduler(
        pre_market_callback=pipeline.run_pre_market_analysis,
        realtime_callback=pipeline.run_realtime_analysis,
        test_mode=test_mode,
    )

    # Start scheduler
    try:
        scheduler.start(run_forever=not test_mode)

    except KeyboardInterrupt:
        logger.info("\n🛑 Pipeline stopped by user")
        scheduler.stop()

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
