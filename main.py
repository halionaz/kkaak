#!/usr/bin/env python3
"""
KKAAK Trading Pipeline

Main entry point for the trading signal generation system.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
from dotenv import load_dotenv
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.data.news_collector import MassiveNewsCollector
from src.data.price_collector import FinnhubPriceCollector
from src.analysis.llm_agent import LLMAgent
from src.analysis.backtester import run_daily_backtest
from src.pipeline.signal_manager import SignalManager
from src.pipeline.position_tracker import PositionTracker
from src.pipeline.scheduler import TradingScheduler
from src.notification.discord_notifier import DiscordNotifier
from src.utils.config_loader import load_stocks, ConfigLoader


class TradingPipeline:
    """메인 트레이딩 파이프라인 오케스트레이터"""

    def __init__(
        self,
        massive_api_key: str,
        finnhub_api_key: str,
        openai_api_key: str,
        discord_webhook_url: str,
    ):
        """
        트레이딩 파이프라인 초기화

        Args:
            massive_api_key: Massive API 키
            finnhub_api_key: Finnhub API 키
            openai_api_key: OpenAI API 키
            discord_webhook_url: Discord 웹훅 URL
        """
        # 파이프라인 설정 로드
        config_loader = ConfigLoader()
        self.pipeline_config = config_loader.load_pipeline_config()

        # 모니터링할 종목 로드
        self.stocks = load_stocks()
        self.tickers = [stock["ticker"] for stock in self.stocks]

        logger.info(f"모니터링 종목 {len(self.tickers)}개: {', '.join(self.tickers)}")

        # 컴포넌트 초기화
        self.news_collector = MassiveNewsCollector(api_key=massive_api_key)
        self.price_collector = FinnhubPriceCollector(api_key=finnhub_api_key)
        self.llm_agent = LLMAgent(api_key=openai_api_key)
        self.signal_manager = SignalManager()
        self.position_tracker = PositionTracker()
        self.discord = DiscordNotifier(webhook_url=discord_webhook_url)

        # 가격 비교를 위한 캐시
        self.previous_prices: Dict[str, float] = {}

        logger.success("트레이딩 파이프라인 초기화 완료")

    def run_pre_market_analysis(self) -> None:
        """장전 분석 실행"""
        from src.pipeline.analysis_workflow import PreMarketAnalysisWorkflow

        workflow = PreMarketAnalysisWorkflow(
            news_collector=self.news_collector,
            price_collector=self.price_collector,
            llm_agent=self.llm_agent,
            signal_manager=self.signal_manager,
            position_tracker=self.position_tracker,
            discord_notifier=self.discord,
            tickers=self.tickers,
            pipeline_config=self.pipeline_config,
        )
        workflow.run()

    def run_realtime_analysis(self) -> None:
        """실시간 분석 실행"""
        from src.pipeline.analysis_workflow import RealtimeAnalysisWorkflow

        workflow = RealtimeAnalysisWorkflow(
            news_collector=self.news_collector,
            price_collector=self.price_collector,
            llm_agent=self.llm_agent,
            signal_manager=self.signal_manager,
            position_tracker=self.position_tracker,
            discord_notifier=self.discord,
            tickers=self.tickers,
            pipeline_config=self.pipeline_config,
            previous_prices=self.previous_prices.copy() if self.previous_prices else None,
        )
        workflow.run()

        # 가격 캐시 업데이트
        current_prices = workflow.get_current_prices()
        if current_prices:
            self.previous_prices = current_prices

    def run_post_market_analysis(self) -> None:
        """
        장후 백테스팅 실행

        워크플로우:
        1. 장 마감 가격 조회
        2. 오늘의 시그널로 백테스팅 실행
        3. 결과를 Discord로 전송
        """
        logger.info("=" * 70)
        logger.info("📊 장후 백테스팅")
        logger.info("=" * 70)

        try:
            # 1. 장 마감 가격 조회
            logger.info("장 마감 가격 조회 중...")
            quotes = self.price_collector.get_quotes(self.tickers)
            closing_prices = {
                ticker: quote.current_price
                for ticker, quote in quotes.items()
            }

            logger.info(f"{len(closing_prices)}개 종목 가격 조회 완료")

            # 2. 백테스팅 실행
            logger.info("백테스팅 실행 중...")
            result = run_daily_backtest(
                signals_dir=self.signal_manager.signals_dir,
                current_prices=closing_prices,
            )

            if not result:
                logger.warning("백테스팅 실패: 오늘의 시그널 없음")
                return

            # 3. Discord 알림 전송
            logger.info("백테스팅 결과를 Discord로 전송 중...")

            # 실현 거래 통계
            buy_count = sum(1 for t in result.trades if t.action == "buy")
            sell_count = sum(1 for t in result.trades if t.action == "sell")

            # 보유 종목 리스트
            held_tickers = list(result.positions_at_close.keys()) if result.positions_at_close else []

            # 최고/최악 거래
            best_ticker = result.best_trade["ticker"] if result.best_trade else None
            best_return = result.best_trade["pnl_pct"] if result.best_trade else None
            worst_ticker = result.worst_trade["ticker"] if result.worst_trade else None
            worst_return = result.worst_trade["pnl_pct"] if result.worst_trade else None

            self.discord.send_postmarket_summary(
                total_signals=buy_count + sell_count,
                buy_count=buy_count,
                sell_count=sell_count,
                hold_count=len(held_tickers),
                breaking_signals=0,  # 실시간 시그널 개수 (별도 추적 필요)
                buy_tickers=[t.ticker for t in result.trades if t.action == "buy"],
                sell_tickers=[t.ticker for t in result.trades if t.action == "sell"],
                virtual_return=result.total_return_pct,
            )

            # 상세 백테스팅 결과 추가 전송
            self._send_backtest_details(result)

            logger.success("✓ 장후 백테스팅 완료")

        except Exception as e:
            logger.error(f"🚨 장후 백테스팅 실패: {e}")
            import traceback
            traceback.print_exc()

            # 에러 알림 전송
            self.discord.send_error(
                error_message="🚨 장후 백테스팅 실패",
                context=str(e),
                retry_info="다음 백테스팅: 내일 장 마감 후"
            )

    def _send_backtest_details(self, result) -> None:
        """
        백테스팅 상세 결과를 Discord로 전송

        Args:
            result: BacktestResult 객체
        """
        from src.analysis.backtester import BacktestResult

        content = "💰 **[백테스팅 상세 결과]**\n\n"

        # 총 수익률 (확신도 기반 금액 투자)
        emoji = "📈" if result.total_return_pct > 0 else "📉"
        content += f"{emoji} **총 수익률**: {result.total_return_pct:+.2f}% (${result.total_return_usd:+,.2f})\n"
        content += f"• 총 투자 금액: ${result.total_invested:,.0f}\n"
        content += f"• 매도 수익: ${result.total_proceeds:,.0f}\n"
        content += f"• 최종 가치: ${result.total_value:,.0f}\n\n"

        # 거래 통계
        content += "📊 **거래 통계**:\n"
        content += f"• 총 거래: {len(result.trades)}회\n"
        content += f"• 수익 거래: {result.winning_trades}회\n"
        content += f"• 손실 거래: {result.losing_trades}회\n"
        content += f"• 승률: {result.win_rate:.1f}%\n\n"

        # 최고/최악 거래
        if result.best_trade:
            best = result.best_trade
            content += f"🏆 **최고 거래**: {best['ticker']} ({best['pnl_pct']:+.2f}%, ${best['pnl']:+.2f})\n"

        if result.worst_trade:
            worst = result.worst_trade
            content += f"⚠️ **최악 거래**: {worst['ticker']} ({worst['pnl_pct']:+.2f}%, ${worst['pnl']:+.2f})\n"

        # 보유 포지션
        if result.positions_at_close:
            content += f"\n📦 **장 마감 시 보유 종목** ({len(result.positions_at_close)}개):\n"
            for ticker, pos in list(result.positions_at_close.items())[:5]:
                pnl_emoji = "📈" if pos['pnl'] > 0 else "📉"
                content += f"• {ticker}: {pnl_emoji} {pos['pnl_pct']:+.2f}% (${pos['pnl']:+.2f})\n"

            if len(result.positions_at_close) > 5:
                content += f"  (외 {len(result.positions_at_close) - 5}개)\n"

            content += f"\n💵 **미실현 손익**: ${result.unrealized_pnl:+,.2f}\n"

        content += "\n---\n"
        content += "💡 **투자 방식**: 시그널당 $1,000 × 확신도\n"
        content += "⚠️ 이는 가상 백테스팅 결과이며, 실제 거래와 다를 수 있습니다."

        # Discord 전송
        self.discord._send_message(content=content)


def main():
    """메인 진입점"""
    # 환경 변수 로드
    load_dotenv()

    logger.info("=" * 70)
    logger.info("🐦‍⬛ 까악 - 트레이딩 시그널 봇")
    logger.info("=" * 70)

    # 필수 환경 변수 확인
    required_vars = [
        "MASSIVE_API_KEY",
        "FINNHUB_API_KEY",
        "OPENAI_API_KEY",
        "DISCORD_WEBHOOK_URL",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"❌ 필수 환경 변수 누락: {', '.join(missing_vars)}")
        logger.info("\n다음을 확인하세요:")
        logger.info("1. .env 파일 생성 (.env.example에서 복사)")
        logger.info("2. .env에 모든 필수 API 키 추가")
        logger.info("\n필수 키:")
        for var in required_vars:
            logger.info(f"   - {var}")
        sys.exit(1)

    # 파이프라인 초기화
    pipeline = TradingPipeline(
        massive_api_key=os.getenv("MASSIVE_API_KEY"),
        finnhub_api_key=os.getenv("FINNHUB_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
    )

    # 테스트 모드 확인
    test_mode = "--test" in sys.argv

    # 스케줄러 초기화 (파이프라인 설정 전달)
    scheduler = TradingScheduler(
        pre_market_callback=pipeline.run_pre_market_analysis,
        realtime_callback=pipeline.run_realtime_analysis,
        post_market_callback=pipeline.run_post_market_analysis,
        config=pipeline.pipeline_config,
        discord_notifier=pipeline.discord,
        test_mode=test_mode,
    )

    # 스케줄러 시작
    try:
        scheduler.start(run_forever=not test_mode)

    except KeyboardInterrupt:
        logger.info("\n🛑 사용자에 의해 파이프라인 중지")
        scheduler.stop()

        # 종료 알림 전송
        try:
            now_kst = scheduler.get_current_time_kst()
            pipeline.discord.send_shutdown_message(
                current_time_kst=now_kst.strftime('%Y-%m-%d %H:%M:%S'),
                reason="사용자 중지"
            )
        except Exception as e:
            logger.warning(f"종료 알림 전송 실패: {e}")

    except Exception as e:
        logger.error(f"파이프라인 에러: {e}")
        import traceback
        traceback.print_exc()

        # 에러 종료 알림 전송
        try:
            now_kst = scheduler.get_current_time_kst()
            pipeline.discord.send_shutdown_message(
                current_time_kst=now_kst.strftime('%Y-%m-%d %H:%M:%S'),
                reason=f"에러 발생: {str(e)[:100]}"
            )
        except Exception as notify_error:
            logger.warning(f"종료 알림 전송 실패: {notify_error}")

        sys.exit(1)


if __name__ == "__main__":
    main()
