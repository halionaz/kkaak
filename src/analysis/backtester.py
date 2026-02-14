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


@dataclass
class Trade:
    """거래 기록"""
    ticker: str
    action: str  # buy, sell
    price: float
    shares: int
    timestamp: datetime
    signal_confidence: float
    reasoning: str


@dataclass
class BacktestResult:
    """백테스팅 결과"""
    initial_capital: float
    final_capital: float
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
        initial_capital: float = 10000.0,
        max_position_size: float = 0.2,  # 한 종목당 최대 20%
        commission: float = 0.0,  # 수수료 (0% = 무시)
    ):
        """
        백테스터 초기화

        Args:
            initial_capital: 초기 자본
            max_position_size: 한 종목당 최대 투자 비율 (0.0-1.0)
            commission: 거래 수수료 비율
        """
        self.initial_capital = initial_capital
        self.max_position_size = max_position_size
        self.commission = commission

        # 시뮬레이션 상태
        self.cash = initial_capital
        self.portfolio: Dict[str, Dict] = {}  # {ticker: {shares, avg_price, entry_time}}
        self.trades: List[Trade] = []

        logger.info(f"백테스터 초기화: 초기자본 ${initial_capital:,.0f}")

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
        """매수 처리"""
        # 이미 보유 중이면 추가 매수 안 함 (단순화)
        if ticker in self.portfolio:
            logger.debug(f"{ticker} 이미 보유 중 - 추가 매수 생략")
            return None

        # 투자 금액 계산 (신뢰도 기반 가중치)
        # 신뢰도가 높을수록 더 많이 투자
        # confidence 0.7 → 14% (0.7 * 0.2)
        # confidence 0.8 → 16%
        # confidence 0.9 → 18%
        # confidence 1.0 → 20%
        position_size = min(confidence * self.max_position_size, self.max_position_size)
        investment = self.cash * position_size

        if investment < price:
            logger.debug(f"{ticker} 매수 불가: 현금 부족 (필요: ${price:.2f}, 보유: ${investment:.2f})")
            return None

        # 주식 수 계산
        shares = int(investment / price)
        if shares == 0:
            return None

        cost = shares * price * (1 + self.commission)

        # 매수 실행
        self.cash -= cost
        self.portfolio[ticker] = {
            "shares": shares,
            "avg_price": price,
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
        )
        self.trades.append(trade)

        logger.info(
            f"매수: {ticker} x{shares}주 @ ${price:.2f} "
            f"(투자: ${cost:.2f}, 잔액: ${self.cash:.2f})"
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

        # 매도 실행
        proceeds = shares * price * (1 - self.commission)
        self.cash += proceeds

        # 수익률 계산
        pnl = (price - avg_price) * shares
        pnl_pct = (price / avg_price - 1) * 100

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
        )
        self.trades.append(trade)

        logger.info(
            f"매도: {ticker} x{shares}주 @ ${price:.2f} "
            f"(수익: ${pnl:+.2f} / {pnl_pct:+.2f}%, 잔액: ${self.cash:.2f})"
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
        # 미실현 손익 계산
        unrealized_pnl = self.calculate_unrealized_pnl(closing_prices)

        # 보유 포지션 평가
        positions_at_close = {}
        for ticker, position in self.portfolio.items():
            if ticker in closing_prices:
                current_price = closing_prices[ticker]
                shares = position["shares"]
                avg_price = position["avg_price"]
                market_value = shares * current_price
                pnl = (current_price - avg_price) * shares
                pnl_pct = (current_price / avg_price - 1) * 100

                positions_at_close[ticker] = {
                    "shares": shares,
                    "avg_price": avg_price,
                    "current_price": current_price,
                    "market_value": market_value,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                }

        # 최종 자본 = 현금 + 보유 종목 시가총액
        portfolio_value = sum(pos["market_value"] for pos in positions_at_close.values())
        final_capital = self.cash + portfolio_value

        # 수익률 계산
        total_return_usd = final_capital - self.initial_capital
        total_return_pct = (final_capital / self.initial_capital - 1) * 100

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
                pnl = (trade.price - buy_trade.price) * trade.shares
                pnl_pct = (trade.price / buy_trade.price - 1) * 100

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
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                    }

        total_closed_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_closed_trades * 100) if total_closed_trades > 0 else 0.0

        result = BacktestResult(
            initial_capital=self.initial_capital,
            final_capital=final_capital,
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
            f"초기자본 ${self.initial_capital:,.0f} → "
            f"최종자본 ${final_capital:,.0f} "
            f"({total_return_pct:+.2f}%)"
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
    backtester = Backtester(initial_capital=10000.0)

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
