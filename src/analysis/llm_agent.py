"""
LLM Agent

OpenAI GPT-4o mini integration for news analysis.
"""

import json
import uuid
from datetime import UTC, datetime

from loguru import logger
from openai import OpenAI

from ..utils.config_loader import ConfigLoader
from .models import AnalysisResult, RiskLevel, TickerAnalysis, TradingSignal
from .prompt_templates import PromptTemplates


class LLMAgent:
    """GPT-4o mini agent for analyzing news and generating trading signals."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4096,
        temperature: float = 0.1,
        config_loader: ConfigLoader | None = None,
    ):
        """Initialize LLM agent.

        Args:
            api_key: OpenAI API key
            model: Model name (default: gpt-4o-mini)
            max_tokens: Maximum tokens in response
            temperature: Temperature for sampling (lower = more deterministic)
            config_loader: Optional config loader (creates new one if not provided)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Load token pricing from config
        if config_loader is None:
            config_loader = ConfigLoader()

        self.COST_PER_1M_INPUT_TOKENS = config_loader.get_constant(
            "llm_pricing.cost_per_1m_input_tokens", 0.15
        )
        self.COST_PER_1M_OUTPUT_TOKENS = config_loader.get_constant(
            "llm_pricing.cost_per_1m_output_tokens", 0.60
        )

        logger.info(f"Initialized LLM agent with model: {model}")

    def analyze_news(
        self,
        news_articles: list[dict],
        current_prices: dict[str, float],
        mode: str = "pre_market",
        previous_prices: dict[str, float] | None = None,
        watchlist: list[str] | None = None,
        **kwargs,
    ) -> AnalysisResult:
        """Analyze news articles and generate trading signals.

        Args:
            news_articles: List of news articles (as dicts)
            current_prices: Current prices for tickers
            mode: Analysis mode ('pre_market' or 'realtime')
            previous_prices: Previous prices for comparison (realtime only)
            watchlist: List of ticker symbols to analyze (optional)
            **kwargs: Additional arguments passed to prompt builder

        Returns:
            AnalysisResult with trading signals and insights
        """
        logger.info(f"Analyzing {len(news_articles)} articles in {mode} mode")

        # Build prompt based on mode
        if mode == "pre_market":
            user_prompt = PromptTemplates.build_pre_market_prompt(
                news_articles=news_articles,
                current_prices=current_prices,
                watchlist=watchlist,
                **kwargs,
            )
        elif mode == "realtime":
            user_prompt = PromptTemplates.build_realtime_prompt(
                news_articles=news_articles,
                current_prices=current_prices,
                previous_prices=previous_prices,
                watchlist=watchlist,
                **kwargs,
            )
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'pre_market' or 'realtime'")

        # Call OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PromptTemplates.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},  # Ensure JSON output
            )

            # Extract response
            content = response.choices[0].message.content
            usage = response.usage

            logger.info(
                f"LLM response received. Tokens: {usage.total_tokens} "
                f"(input: {usage.prompt_tokens}, output: {usage.completion_tokens})"
            )

            # Parse JSON response
            analysis_data = json.loads(content)

            # Calculate cost
            cost_usd = self._calculate_cost(
                usage.prompt_tokens,
                usage.completion_tokens,
            )

            # Build AnalysisResult
            result = self._build_analysis_result(
                analysis_data=analysis_data,
                news_articles=news_articles,
                tokens_used=usage.total_tokens,
                cost_usd=cost_usd,
            )

            logger.success(
                f"Analysis complete. Signals: {len(result.ticker_analyses)}, Cost: ${cost_usd:.4f}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response content: {content}")
            raise

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            raise

    def _build_analysis_result(
        self,
        analysis_data: dict,
        news_articles: list[dict],
        tokens_used: int,
        cost_usd: float,
    ) -> AnalysisResult:
        """Build AnalysisResult from LLM response data."""

        # Parse ticker analyses
        ticker_analyses = []
        for ticker_data in analysis_data.get("ticker_analyses", []):
            try:
                analysis = TickerAnalysis(
                    ticker=ticker_data["ticker"],
                    signal=TradingSignal(ticker_data["signal"]),
                    sentiment=ticker_data["sentiment"],
                    confidence=ticker_data["confidence"],
                    expected_impact=ticker_data["expected_impact"],
                    impact_magnitude=ticker_data["impact_magnitude"],
                    key_points=ticker_data.get("key_points", []),
                    risk_factors=ticker_data.get("risk_factors", []),
                    reasoning=ticker_data["reasoning"],
                )
                ticker_analyses.append(analysis)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse ticker analysis: {e}")
                continue

        # Build result
        result = AnalysisResult(
            analysis_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            model=self.model,
            market_sentiment=analysis_data.get("market_sentiment", "neutral"),
            market_summary=analysis_data.get("market_summary", ""),
            ticker_analyses=ticker_analyses,
            top_opportunities=analysis_data.get("top_opportunities", []),
            top_risks=analysis_data.get("top_risks", []),
            priority_tickers=analysis_data.get("priority_tickers", []),
            avoid_tickers=analysis_data.get("avoid_tickers", []),
            overall_risk_level=RiskLevel(analysis_data.get("overall_risk_level", "medium")),
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            news_count=len(news_articles),
            news_ids=[article.get("id", "") for article in news_articles],
        )

        return result

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for the API call."""
        input_cost = (input_tokens / 1_000_000) * self.COST_PER_1M_INPUT_TOKENS
        output_cost = (output_tokens / 1_000_000) * self.COST_PER_1M_OUTPUT_TOKENS
        return input_cost + output_cost

    def batch_analyze(
        self,
        news_batches: list[list[dict]],
        current_prices: dict[str, float],
        mode: str = "pre_market",
        **kwargs,
    ) -> list[AnalysisResult]:
        """Analyze multiple batches of news articles.

        Useful for processing large amounts of news while staying within token limits.

        Args:
            news_batches: List of news article batches
            current_prices: Current prices for tickers
            mode: Analysis mode
            **kwargs: Additional arguments

        Returns:
            List of AnalysisResult objects
        """
        logger.info(f"Batch analyzing {len(news_batches)} batches")

        results = []
        total_cost = 0.0

        for idx, batch in enumerate(news_batches, 1):
            logger.info(f"Processing batch {idx}/{len(news_batches)} ({len(batch)} articles)")

            try:
                result = self.analyze_news(
                    news_articles=batch,
                    current_prices=current_prices,
                    mode=mode,
                    **kwargs,
                )
                results.append(result)
                total_cost += result.cost_usd or 0.0

            except Exception as e:
                logger.error(f"Batch {idx} failed: {e}")
                continue

        logger.success(
            f"Batch analysis complete. {len(results)}/{len(news_batches)} successful. "
            f"Total cost: ${total_cost:.4f}"
        )

        return results

    @staticmethod
    def create_news_batches(
        news_articles: list[dict],
        batch_size: int = 20,
    ) -> list[list[dict]]:
        """Split news articles into batches.

        Args:
            news_articles: List of news articles
            batch_size: Maximum articles per batch

        Returns:
            List of article batches
        """
        batches = []
        for i in range(0, len(news_articles), batch_size):
            batch = news_articles[i : i + batch_size]
            batches.append(batch)

        logger.info(f"Created {len(batches)} batches from {len(news_articles)} articles")
        return batches
