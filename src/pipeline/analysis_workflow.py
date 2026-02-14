"""
Analysis Workflow - Template Method Pattern

Abstracts common workflow between pre-market and realtime analysis,
eliminating ~70% code duplication.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger


class AnalysisWorkflow(ABC):
    """
    분석 워크플로우 기본 클래스 (Template Method Pattern)

    공통 워크플로우:
    1. 뉴스 수집
    2. 가격 조회
    3. LLM 분석
    4. 시그널 생성
    5. 포지션 업데이트
    6. 알림 전송
    """

    def __init__(
        self,
        news_collector,
        price_collector,
        llm_agent,
        signal_manager,
        position_tracker,
        discord_notifier,
        tickers: List[str],
        pipeline_config: Dict,
    ):
        self.news_collector = news_collector
        self.price_collector = price_collector
        self.llm_agent = llm_agent
        self.signal_manager = signal_manager
        self.position_tracker = position_tracker
        self.discord = discord_notifier
        self.tickers = tickers
        self.config = pipeline_config

    def run(self) -> None:
        """Main workflow execution (Template Method)"""
        from ..utils.error_handler import ErrorContext

        self._log_header()

        with ErrorContext(
            self.get_operation_name(),
            discord=self.discord,
            retry_info=self.get_retry_info()
        ):
            # 1. Collect news
            news_articles = self.collect_news()
            if not news_articles:
                logger.warning("뉴스 없음 - 분석 중단")
                self._handle_no_news()
                return

            logger.info(f"뉴스 {len(news_articles)}개 수집 완료")

            # 2. Fetch prices
            current_prices = self._fetch_prices()
            logger.info(f"{len(current_prices)}개 종목 가격 조회 완료")

            # 3. LLM analysis
            analysis_result = self._analyze_news(news_articles, current_prices)
            logger.success(
                f"분석 완료. 시그널: {len(analysis_result.ticker_analyses)}개, "
                f"비용: ${analysis_result.cost_usd:.4f}"
            )

            # 4. Generate signals
            signals = self._generate_signals(analysis_result, current_prices)
            summary = self.signal_manager.get_summary(signals)
            logger.info(
                f"시그널 생성 완료: "
                f"매수 {summary['buy']}개, 매도 {summary['sell']}개, 홀드 {summary['hold']}개"
            )

            # 5. Update positions
            changes = self.position_tracker.update_positions(signals)
            actionable_changes = self.position_tracker.get_actionable_changes(changes)

            if actionable_changes:
                logger.info(f"실행 가능한 포지션 변경 {len(actionable_changes)}개 감지")

            # 6. Send notifications
            self.send_notifications(
                signals=signals,
                analysis_result=analysis_result,
                actionable_changes=actionable_changes,
                news_articles=news_articles,
            )

            logger.success(f"✓ {self.get_operation_name()} 완료")

    # Abstract methods (서브클래스가 구현)

    @abstractmethod
    def get_operation_name(self) -> str:
        """작업 이름 반환"""
        pass

    @abstractmethod
    def get_retry_info(self) -> str:
        """재시도 정보 반환"""
        pass

    @abstractmethod
    def collect_news(self) -> List:
        """뉴스 수집 (모드별로 다름)"""
        pass

    @abstractmethod
    def send_notifications(
        self,
        signals: Dict,
        analysis_result,
        actionable_changes: Dict,
        news_articles: List,
    ) -> None:
        """알림 전송 (모드별로 다름)"""
        pass

    @abstractmethod
    def get_analysis_mode(self) -> str:
        """분석 모드 반환 ('pre_market' or 'realtime')"""
        pass

    # Hook methods (선택적 오버라이드)

    def _log_header(self) -> None:
        """헤더 로깅"""
        logger.info("=" * 70)
        logger.info(f"🔔 {self.get_operation_name()}")
        logger.info("=" * 70)

    def _handle_no_news(self) -> None:
        """뉴스 없을 때 처리"""
        self.discord.send_error(
            error_message=f"⚠️ {self.get_operation_name()}: 뉴스를 찾을 수 없습니다",
            context="뉴스 없음"
        )

    # Concrete methods (공통 로직)

    def _fetch_prices(self) -> Dict[str, float]:
        """가격 조회"""
        logger.info("현재 가격 조회 중...")
        quotes = self.price_collector.get_quotes(self.tickers)
        return {ticker: quote.current_price for ticker, quote in quotes.items()}

    def _analyze_news(self, news_articles: List, current_prices: Dict):
        """LLM 뉴스 분석"""
        logger.info("GPT-4o mini로 뉴스 분석 중...")

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

        return self.llm_agent.analyze_news(
            news_articles=news_dicts,
            current_prices=current_prices,
            mode=self.get_analysis_mode(),
            watchlist=self.tickers,
            **self.get_analysis_kwargs()
        )

    def _generate_signals(self, analysis_result, current_prices: Dict) -> Dict:
        """시그널 생성"""
        logger.info("트레이딩 시그널 생성 중...")

        signals = self.signal_manager.generate_signals(
            analysis_result=analysis_result,
            mode=self.get_analysis_mode(),
            previous_signals=self.get_previous_signals(),
            current_prices=current_prices,
        )

        self.signal_manager.save_signals(signals)
        return signals

    def get_analysis_kwargs(self) -> Dict:
        """LLM 분석 추가 인자"""
        return {}

    def get_previous_signals(self) -> Optional[Dict]:
        """이전 시그널 조회"""
        return None


class PreMarketAnalysisWorkflow(AnalysisWorkflow):
    """장전 분석 워크플로우"""

    def get_operation_name(self) -> str:
        return "장전 분석"

    def get_retry_info(self) -> str:
        return "다음 분석: 내일 09:00 ET"

    def get_analysis_mode(self) -> str:
        return "pre_market"

    def collect_news(self) -> List:
        """장전 뉴스 수집"""
        config = self.config["premarket"]
        logger.info(f"장전 시장 뉴스 수집 중 (최근 {config['news_lookback_hours']}시간)...")
        return self.news_collector.fetch_latest_market_news(
            hours_back=config["news_lookback_hours"],
            limit=config["news_limit"],
        )

    def get_analysis_kwargs(self) -> Dict:
        return {"time_to_open": "30 minutes"}

    def send_notifications(self, signals, analysis_result, actionable_changes, news_articles):
        """장전 리포트 전송"""
        logger.info("Discord 알림 전송 중...")

        discord_signals = [
            {
                "ticker": ticker,
                "action": signal["action"],
                "confidence": signal["confidence"],
                "reasoning": signal["reasoning"],
            }
            for ticker, signal in signals.items()
        ]

        self.discord.send_premarket_report(
            signals=discord_signals,
            news_summary=analysis_result.market_summary,
        )


class RealtimeAnalysisWorkflow(AnalysisWorkflow):
    """실시간 분석 워크플로우"""

    def __init__(self, *args, previous_prices: Optional[Dict] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous_prices = previous_prices
        self._current_prices: Optional[Dict[str, float]] = None

    def get_operation_name(self) -> str:
        return "실시간 분석"

    def get_retry_info(self) -> str:
        interval = self.config["realtime"]["interval_minutes"]
        return f"다음 분석: {interval}분 후"

    def get_analysis_mode(self) -> str:
        return "realtime"

    def collect_news(self) -> List:
        """실시간 뉴스 수집"""
        config = self.config["realtime"]
        logger.info(f"최근 시장 뉴스 수집 중 (최근 {config['news_lookback_hours']}시간)...")

        news_articles = self.news_collector.fetch_latest_market_news(
            hours_back=config["news_lookback_hours"],
            limit=config["news_limit"],
        )

        # 최근 N분 이내 뉴스만 필터링
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(minutes=config["news_cutoff_minutes"])
        recent_news = [
            article for article in news_articles
            if article.published_utc >= cutoff_time
        ]

        logger.info(f"최근 {config['news_cutoff_minutes']}분 이내 기사 {len(recent_news)}개 발견")
        return recent_news

    def _handle_no_news(self) -> None:
        """뉴스 없을 때 - 조용히 넘어감"""
        logger.info("최근 뉴스 없음. 분석 생략.")

    def _fetch_prices(self) -> Dict[str, float]:
        """가격 조회 및 캐싱"""
        self._current_prices = super()._fetch_prices()
        return self._current_prices

    def get_analysis_kwargs(self) -> Dict:
        return {
            "previous_prices": self.previous_prices,
            "market_status": "OPEN",
            "time_window": "30 minutes",
        }

    def get_previous_signals(self) -> Optional[Dict]:
        """보수적 필터링을 위한 이전 시그널"""
        return self.signal_manager.get_latest_signals()

    def get_current_prices(self) -> Optional[Dict[str, float]]:
        """현재 가격 반환 (previous_prices 업데이트용)"""
        return self._current_prices

    def send_notifications(self, signals, analysis_result, actionable_changes, news_articles):
        """실시간 시그널 전송 (변경사항만)"""
        if not actionable_changes:
            logger.info("실행 가능한 변경사항 없음 - 알림 생략")
            return

        logger.info("변경사항에 대한 Discord 알림 전송 중...")

        quotes = self.price_collector.get_quotes(list(actionable_changes.keys()))

        for ticker, change in actionable_changes.items():
            quote = quotes.get(ticker)
            price_data = None
            if quote:
                price_data = {
                    "current": quote.current_price,
                    "change_percent": quote.percent_change,
                }

            ticker_news = [n for n in news_articles if ticker in n.tickers]
            news_title = ticker_news[0].title if ticker_news else None
            news_url = ticker_news[0].article_url if ticker_news else None

            self.discord.send_realtime_signal(
                ticker=ticker,
                action=change["new_action"],
                confidence=change["new_confidence"],
                reasoning=change["reasoning"][:200],
                price_data=price_data,
                news_title=news_title,
                news_url=news_url,
            )

            logger.info(f"{ticker} 알림 전송 완료")
