"""
Backtester

백테스팅 시스템: 하루 동안의 시그널을 기반으로 가상 포트폴리오 수익률 계산
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from ..utils.config_loader import ConfigLoader


@dataclass
class Trade:
    """거래 기록"""
    ticker: str
    action: str  # buy, sell
    price: float
    shares: float  # 소수점 주식 허용
    timestamp: datetime
    signal_confidence: float
    reasoning: str
    investment_amount: float  # 투자 금액


@dataclass
class BacktestResult:
    """백테스팅 결과"""
    total_invested: float  # 총 투자 금액
    total_proceeds: float  # 총 매도 수익
    total_value: float  # 총 가치 (매도 수익 + 보유 포지션)
    total_return_pct: float
    total_return_usd: float
    trades: List[Trade]
    winning_trades: int
    losing_trades: int
    win_rate: float
    best_trade: Optional[Dict]
    worst_trade: Optional[Dict]
    positions_at_close: Dict[str, Dict]  # 장 마감 시 보유 포지션
    unrealized_pnl: float  # 미실현 손익


class Backtester:
    """백테스팅 엔진"""

    def __init__(
        self,
        base_investment_per_signal: Optional[float] = None,
        commission: Optional[float] = None,
        config_loader: Optional[ConfigLoader] = None,
    ):
        """
        백테스터 초기화

        Args:
            base_investment_per_signal: 시그널당 기본 투자 금액 (None = config에서 로드)
            commission: 거래 수수료 비율 (None = config에서 로드)
            config_loader: Optional config loader (creates new one if not provided)
        """
        # Load from config if not provided
        if config_loader is None:
            config_loader = ConfigLoader()

        if base_investment_per_signal is None:
            base_investment_per_signal = config_loader.get_constant("backtester.base_investment_per_signal", 1000.0)
        if commission is None:
            commission = config_loader.get_constant("backtester.commission", 0.0)

        self.base_investment = base_investment_per_signal
        self.commission = commission

        # 시뮬레이션 상태 (무제한 자본 가정)
        self.portfolio: Dict[str, Dict] = {}  # {ticker: {shares, avg_price, investment_amount}}
        self.trades: List[Trade] = []
        self.total_invested = 0.0  # 총 투자 금액
        self.total_proceeds = 0.0  # 총 매도 수익

        logger.info(f"백테스터 초기화: 시그널당 기본투자 ${base_investment_per_signal:,.0f}")

    def process_signal(
        self,
        ticker: str,
        action: str,
        price: float,
        confidence: float,
        timestamp: datetime,
        reasoning: str = "",
    ) -> Optional[Trade]:
        """
        시그널 처리 (매수/매도 시뮬레이션)

        Args:
            ticker: 종목 심볼
            action: buy/sell/hold
            price: 시그널 발생 시점 가격
            confidence: 신뢰도
            timestamp: 시그널 발생 시각
            reasoning: 분석 이유

        Returns:
            거래가 발생하면 Trade 객체, 아니면 None
        """
        if action == "hold":
            return None

        if action == "buy":
            return self._process_buy(ticker, price, confidence, timestamp, reasoning)
        elif action == "sell":
            return self._process_sell(ticker, price, confidence, timestamp, reasoning)

        return None

    def _process_buy(
        self,
        ticker: str,
        price: float,
        confidence: float,
        timestamp: datetime,
        reasoning: str,
    ) -> Optional[Trade]:
        """매수 처리 (무제한 자본, 확신도 기반 금액 투자)"""
        # 이미 보유 중이면 추가 매수 안 함 (단순화)
        if ticker in self.portfolio:
            logger.debug(f"{ticker} 이미 보유 중 - 추가 매수 생략")
            return None

        # 투자 금액 = 기본 투자금 × 확신도
        # confidence 0.7 → $700, 0.85 → $850, 1.0 → $1000
        investment_amount = self.base_investment * confidence

        # 주식 수 계산 (소수점 허용)
        shares = investment_amount / price

        # 수수료 포함 실제 투자 금액
        cost = investment_amount * (1 + self.commission)

        # 매수 실행 (무제한 자본)
        self.total_invested += cost
        self.portfolio[ticker] = {
            "shares": shares,
            "avg_price": price,
            "investment_amount": cost,
            "entry_time": timestamp,
            "entry_confidence": confidence,
        }

        trade = Trade(
            ticker=ticker,
            action="buy",
            price=price,
            shares=shares,
            timestamp=timestamp,
            signal_confidence=confidence,
            reasoning=reasoning,
            investment_amount=cost,
        )
        self.trades.append(trade)

        logger.info(
            f"매수: {ticker} ${cost:,.2f} (= {shares:.4f}주 × ${price:.2f}, 확신도 {confidence:.1%})"
        )

        return trade

    def _process_sell(
        self,
        ticker: str,
        price: float,
        confidence: float,
        timestamp: datetime,
        reasoning: str,
    ) -> Optional[Trade]:
        """매도 처리"""
        # 보유하지 않은 종목은 매도 불가
        if ticker not in self.portfolio:
            logger.debug(f"{ticker} 미보유 - 매도 생략")
            return None

        position = self.portfolio[ticker]
        shares = position["shares"]
        avg_price = position["avg_price"]
        investment_amount = position["investment_amount"]

        # 매도 수익 (수수료 차감)
        proceeds = shares * price * (1 - self.commission)
        self.total_proceeds += proceeds

        # 수익/손실 계산
        pnl = proceeds - investment_amount
        pnl_pct = (pnl / investment_amount) * 100

        # 포지션 종료
        del self.portfolio[ticker]

        trade = Trade(
            ticker=ticker,
            action="sell",
            price=price,
            shares=shares,
            timestamp=timestamp,
            signal_confidence=confidence,
            reasoning=reasoning,
            investment_amount=proceeds,
        )
        self.trades.append(trade)

        logger.info(
            f"매도: {ticker} {shares:.4f}주 @ ${price:.2f} "
            f"(수익: ${pnl:+,.2f} / {pnl_pct:+.2f}%, 투자액: ${investment_amount:,.2f})"
        )

        return trade

    def calculate_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """
        미실현 손익 계산

        Args:
            current_prices: 현재 가격 딕셔너리

        Returns:
            미실현 손익 (USD)
        """
        unrealized = 0.0

        for ticker, position in self.portfolio.items():
            if ticker not in current_prices:
                logger.warning(f"{ticker} 현재 가격 없음 - 미실현 손익 계산 생략")
                continue

            current_price = current_prices[ticker]
            shares = position["shares"]
            avg_price = position["avg_price"]

            pnl = (current_price - avg_price) * shares
            unrealized += pnl

        return unrealized

    def finalize(self, closing_prices: Dict[str, float]) -> BacktestResult:
        """
        백테스팅 종료 및 결과 계산

        Args:
            closing_prices: 장 마감 가격

        Returns:
            백테스팅 결과
        """
        # 보유 포지션 평가
        positions_at_close = {}
        unrealized_total_value = 0.0
        unrealized_pnl = 0.0

        for ticker, position in self.portfolio.items():
            if ticker in closing_prices:
                current_price = closing_prices[ticker]
                shares = position["shares"]
                investment_amount = position["investment_amount"]
                avg_price = position["avg_price"]

                # 현재 시장 가치
                market_value = shares * current_price
                unrealized_total_value += market_value

                # 미실현 손익
                pnl = market_value - investment_amount
                unrealized_pnl += pnl
                pnl_pct = (pnl / investment_amount) * 100

                positions_at_close[ticker] = {
                    "shares": shares,
                    "avg_price": avg_price,
                    "investment_amount": investment_amount,
                    "current_price": current_price,
                    "market_value": market_value,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                }

        # 최종 가치 = 매도 수익 + 보유 포지션 시장가
        total_value = self.total_proceeds + unrealized_total_value

        # 총 수익/손실 = 최종 가치 - 총 투자 금액
        total_return_usd = total_value - self.total_invested
        total_return_pct = (total_return_usd / self.total_invested * 100) if self.total_invested > 0 else 0.0

        # 거래 분석
        winning_trades = 0
        losing_trades = 0
        best_trade = None
        worst_trade = None
        best_pnl = float('-inf')
        worst_pnl = float('inf')

        # 매수-매도 쌍 찾기
        buy_trades = {t.ticker: t for t in self.trades if t.action == "buy"}
        for trade in self.trades:
            if trade.action == "sell" and trade.ticker in buy_trades:
                buy_trade = buy_trades[trade.ticker]
                # 실제 투자금액 대비 수익
                pnl = trade.investment_amount - buy_trade.investment_amount
                pnl_pct = (pnl / buy_trade.investment_amount) * 100

                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1

                if pnl > best_pnl:
                    best_pnl = pnl
                    best_trade = {
                        "ticker": trade.ticker,
                        "buy_price": buy_trade.price,
                        "sell_price": trade.price,
                        "shares": trade.shares,
                        "investment": buy_trade.investment_amount,
                        "proceeds": trade.investment_amount,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                    }

                if pnl < worst_pnl:
                    worst_pnl = pnl
                    worst_trade = {
                        "ticker": trade.ticker,
                        "buy_price": buy_trade.price,
                        "sell_price": trade.price,
                        "shares": trade.shares,
                        "investment": buy_trade.investment_amount,
                        "proceeds": trade.investment_amount,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                    }

        total_closed_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_closed_trades * 100) if total_closed_trades > 0 else 0.0

        result = BacktestResult(
            total_invested=self.total_invested,
            total_proceeds=self.total_proceeds,
            total_value=total_value,
            total_return_pct=total_return_pct,
            total_return_usd=total_return_usd,
            trades=self.trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            best_trade=best_trade,
            worst_trade=worst_trade,
            positions_at_close=positions_at_close,
            unrealized_pnl=unrealized_pnl,
        )

        logger.success(
            f"백테스팅 완료: "
            f"총 투자 ${self.total_invested:,.0f} → "
            f"최종 가치 ${total_value:,.0f} "
            f"({total_return_pct:+.2f}%, ${total_return_usd:+,.2f})"
        )

        return result


def run_daily_backtest(
    signals_dir: Path,
    current_prices: Dict[str, float],
    date: Optional[datetime] = None,
) -> Optional[BacktestResult]:
    """
    하루 동안의 시그널로 백테스팅 실행

    Args:
        signals_dir: 시그널 파일 디렉토리
        current_prices: 장 마감 가격
        date: 백테스트할 날짜 (None이면 오늘)

    Returns:
        백테스팅 결과 또는 None (시그널 없음)
    """
    if date is None:
        date = datetime.now(timezone.utc)

    # 오늘 날짜의 시그널 파일 찾기
    date_str = date.strftime("%Y%m%d")
    signal_files = sorted(signals_dir.glob(f"signals_{date_str}_*.json"))

    if not signal_files:
        logger.warning(f"{date_str} 날짜의 시그널 파일 없음")
        return None

    logger.info(f"{len(signal_files)}개의 시그널 파일 발견")

    # 백테스터 초기화
    backtester = Backtester()

    # 모든 시그널 처리 (시간순)
    for signal_file in signal_files:
        with open(signal_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        signals = data.get("signals", {})
        timestamp = datetime.fromisoformat(data.get("generated_at"))

        for ticker, signal in signals.items():
            action = signal.get("action")
            confidence = signal.get("confidence", 0.0)
            reasoning = signal.get("reasoning", "")
            price = signal.get("price")

            # 가격 정보가 없으면 현재 가격 사용 (폴백)
            if price is None:
                price = current_prices.get(ticker)

            if price is None:
                logger.warning(f"{ticker} 가격 정보 없음 - 시그널 생략")
                continue

            # 시그널 처리
            backtester.process_signal(
                ticker=ticker,
                action=action,
                price=price,
                confidence=confidence,
                timestamp=timestamp,
                reasoning=reasoning,
            )

    # 백테스팅 결과 계산
    result = backtester.finalize(current_prices)

    return result
