"""
Configuration Loader

Loads configuration from YAML files.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

from ..data.models import StockConfig


class ConfigLoader:
    """Loads configuration from YAML files."""

    def __init__(self, config_dir: Path = None):
        """
        Initialize config loader.

        Args:
            config_dir: Path to config directory (defaults to ./config)
        """
        if config_dir is None:
            # Default to config directory in project root
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config"

        self.config_dir = Path(config_dir)

        if not self.config_dir.exists():
            raise FileNotFoundError(f"Config directory not found: {self.config_dir}")

        logger.info(f"Config directory: {self.config_dir}")

    def load_stocks(self) -> List[StockConfig]:
        """
        Load stock configurations from stocks.yaml.

        Returns:
            List of StockConfig objects
        """
        stocks_file = self.config_dir / "stocks.yaml"

        if not stocks_file.exists():
            raise FileNotFoundError(f"stocks.yaml not found: {stocks_file}")

        with open(stocks_file, "r") as f:
            data = yaml.safe_load(f)

        stocks = []
        for stock_data in data.get("stocks", []):
            stocks.append(StockConfig(**stock_data))

        logger.info(f"Loaded {len(stocks)} stocks from config")
        return stocks

    def load_trading_rules(self) -> Dict[str, Any]:
        """
        Load trading rules from trading_rules.yaml.

        Returns:
            Dictionary of trading rules
        """
        rules_file = self.config_dir / "trading_rules.yaml"

        if not rules_file.exists():
            raise FileNotFoundError(f"trading_rules.yaml not found: {rules_file}")

        with open(rules_file, "r") as f:
            rules = yaml.safe_load(f)

        logger.info("Loaded trading rules from config")
        return rules

    def load_pipeline_config(self) -> Dict[str, Any]:
        """
        파이프라인 설정을 trading_rules.yaml에서 로드

        Returns:
            파이프라인 설정 딕셔너리:
            - premarket: 장전 분석 설정
            - realtime: 실시간 분석 설정
            - scheduler: 스케줄러 설정
        """
        rules = self.load_trading_rules()
        pipeline_config = rules.get("pipeline", {})

        if not pipeline_config:
            logger.warning("파이프라인 설정 없음, 기본값 사용")
            # 기본값 반환
            pipeline_config = {
                "premarket": {
                    "schedule_time": "09:00",
                    "news_lookback_hours": 24,
                    "news_limit": 100,
                    "schedule_window_minutes": 5,
                },
                "realtime": {
                    "interval_minutes": 20,
                    "news_lookback_hours": 1,
                    "news_limit": 50,
                    "news_cutoff_minutes": 35,
                },
                "scheduler": {
                    "check_interval_seconds": 60,
                },
            }

        logger.info("파이프라인 설정 로드 완료")
        return pipeline_config

    def load_constants(self) -> Dict[str, Any]:
        """
        Load constants from trading_rules.yaml.

        Returns:
            Dictionary of constants
        """
        rules = self.load_trading_rules()
        return rules.get("constants", {})

    def get_constant(self, path: str, default: Any = None) -> Any:
        """
        Get a constant value by dot-notation path.

        Args:
            path: Dot-notation path (e.g., "llm_pricing.cost_per_1m_input_tokens")
            default: Default value if not found

        Returns:
            Constant value

        Examples:
            >>> loader = ConfigLoader()
            >>> loader.get_constant("separator_length", 70)
            70
            >>> loader.get_constant("llm_pricing.cost_per_1m_input_tokens", 0.15)
            0.15
        """
        constants = self.load_constants()
        keys = path.split(".")
        value = constants

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_tickers(self, priority: int = None) -> List[str]:
        """
        Get list of ticker symbols.

        Args:
            priority: Filter by priority level (None = all)

        Returns:
            List of ticker symbols
        """
        stocks = self.load_stocks()

        if priority is not None:
            stocks = [s for s in stocks if s.priority == priority]

        return [s.ticker for s in stocks]

    def get_high_priority_tickers(self) -> List[str]:
        """
        Get high priority (priority=1) ticker symbols.

        Returns:
            List of high priority ticker symbols
        """
        return self.get_tickers(priority=1)

    def get_stocks_by_sector(self, sector: str) -> List[StockConfig]:
        """
        Get stocks filtered by sector.

        Args:
            sector: Sector name (e.g., "Technology", "ETF")

        Returns:
            List of StockConfig objects in the sector
        """
        stocks = self.load_stocks()
        return [s for s in stocks if s.sector.lower() == sector.lower()]


def load_stocks() -> List[Dict[str, Any]]:
    """
    Helper function to load stocks as dictionaries.

    Returns:
        List of stock dictionaries
    """
    loader = ConfigLoader()
    stocks = loader.load_stocks()

    # Convert to dict format
    return [
        {
            "ticker": stock.ticker,
            "name": stock.name,
            "sector": stock.sector,
            "priority": stock.priority,
        }
        for stock in stocks
    ]


def test_config_loader():
    """Test configuration loading."""
    print("\n" + "="*60)
    print("Testing Configuration Loader")
    print("="*60 + "\n")

    try:
        loader = ConfigLoader()

        # Load all stocks
        stocks = loader.load_stocks()
        print(f"Total stocks loaded: {len(stocks)}\n")

        # Show all stocks
        print("All stocks:")
        for stock in stocks:
            print(f"  {stock.ticker:8s} - {stock.name:40s} [{stock.sector}] (Priority: {stock.priority})")

        # Get high priority tickers
        print("\nHigh priority tickers (priority=1):")
        high_priority = loader.get_high_priority_tickers()
        print(f"  {', '.join(high_priority)}")

        # Get stocks by sector
        print("\nTechnology stocks:")
        tech_stocks = loader.get_stocks_by_sector("Technology")
        for stock in tech_stocks:
            print(f"  {stock.ticker:8s} - {stock.name}")

        print("\nETF stocks:")
        etf_stocks = loader.get_stocks_by_sector("ETF")
        for stock in etf_stocks:
            print(f"  {stock.ticker:8s} - {stock.name}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_config_loader()
