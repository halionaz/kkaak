"""
Signal Manager

Generates and manages trading signals from LLM analysis.
"""

import json
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from src.analysis.models import AnalysisResult, TradingSignal
from src.data.models import StockQuote


class TradingAction(str, Enum):
    """Trading action enum (simplified from TradingSignal)."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SignalManager:
    """Manages trading signal generation and history."""

    # Signal mapping: TradingSignal → TradingAction
    SIGNAL_MAPPING = {
        TradingSignal.STRONG_BUY: TradingAction.BUY,
        TradingSignal.BUY: TradingAction.BUY,
        TradingSignal.HOLD: TradingAction.HOLD,
        TradingSignal.SELL: TradingAction.SELL,
        TradingSignal.STRONG_SELL: TradingAction.SELL,
    }

    # Conservative thresholds
    MIN_CONFIDENCE = 0.7  # Minimum confidence to act on a signal
    HIGH_CONFIDENCE = 0.8  # Threshold for strong signals (buy ↔ sell changes)

    def __init__(self, signals_dir: str = "data/signals"):
        """
        Initialize signal manager.

        Args:
            signals_dir: Directory to save signal history
        """
        self.signals_dir = Path(signals_dir)
        self.signals_dir.mkdir(parents=True, exist_ok=True)

        # Current signals
        self.current_signals: Dict[str, Dict] = {}

        logger.info("SignalManager initialized")

    def generate_signals(
        self,
        analysis_result: AnalysisResult,
        mode: str = "pre_market",
        previous_signals: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Dict]:
        """
        Generate trading signals from LLM analysis.

        Args:
            analysis_result: LLM analysis result
            mode: "pre_market" or "realtime"
            previous_signals: Previous signals for conservative update logic

        Returns:
            Dictionary of signals: {ticker: signal_dict}
        """
        signals = {}

        for ticker_analysis in analysis_result.ticker_analyses:
            ticker = ticker_analysis.ticker

            # Map TradingSignal to TradingAction
            action = self.SIGNAL_MAPPING.get(
                ticker_analysis.signal,
                TradingAction.HOLD
            )

            # Apply conservative filtering
            confidence = ticker_analysis.confidence

            # Low confidence → HOLD
            if confidence < self.MIN_CONFIDENCE:
                action = TradingAction.HOLD
                logger.debug(
                    f"{ticker}: Low confidence ({confidence:.2f}) → HOLD"
                )

            # Conservative update logic for realtime mode
            if mode == "realtime" and previous_signals:
                action = self._apply_conservative_filter(
                    ticker=ticker,
                    new_action=action,
                    new_confidence=confidence,
                    previous_signals=previous_signals,
                )

            # Create signal
            signal = {
                "ticker": ticker,
                "action": action.value,
                "confidence": confidence,
                "sentiment": ticker_analysis.sentiment,
                "reasoning": ticker_analysis.reasoning,
                "key_points": ticker_analysis.key_points,
                "risk_factors": ticker_analysis.risk_factors,
                "expected_impact": ticker_analysis.expected_impact,
                "impact_magnitude": ticker_analysis.impact_magnitude,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": mode,
            }

            signals[ticker] = signal

        # Store current signals
        self.current_signals = signals

        logger.info(
            f"Generated {len(signals)} signals "
            f"(BUY: {self._count_action(signals, TradingAction.BUY)}, "
            f"SELL: {self._count_action(signals, TradingAction.SELL)}, "
            f"HOLD: {self._count_action(signals, TradingAction.HOLD)})"
        )

        return signals

    def _apply_conservative_filter(
        self,
        ticker: str,
        new_action: TradingAction,
        new_confidence: float,
        previous_signals: Dict[str, Dict],
    ) -> TradingAction:
        """
        Apply conservative filtering for signal updates.

        Conservative rules:
        1. BUY ↔ SELL requires HIGH_CONFIDENCE (0.8+)
        2. If confidence drops, prefer HOLD
        3. Maintain previous signal if new confidence is marginal

        Args:
            ticker: Stock ticker
            new_action: New action from analysis
            new_confidence: New confidence score
            previous_signals: Previous signals

        Returns:
            Filtered action
        """
        # No previous signal → accept new signal if confident
        if ticker not in previous_signals:
            return new_action

        prev_signal = previous_signals[ticker]
        prev_action = TradingAction(prev_signal["action"])
        prev_confidence = prev_signal.get("confidence", 0.0)

        # Same action → accept
        if new_action == prev_action:
            return new_action

        # BUY ↔ SELL requires high confidence
        if (
            (prev_action == TradingAction.BUY and new_action == TradingAction.SELL)
            or (prev_action == TradingAction.SELL and new_action == TradingAction.BUY)
        ):
            if new_confidence < self.HIGH_CONFIDENCE:
                logger.info(
                    f"{ticker}: {prev_action.value} ↔ {new_action.value} "
                    f"requires high confidence (got {new_confidence:.2f} < {self.HIGH_CONFIDENCE}). "
                    f"Keeping {prev_action.value}"
                )
                return prev_action

        # Confidence dropped significantly → HOLD
        if new_confidence < prev_confidence - 0.1:
            logger.info(
                f"{ticker}: Confidence dropped "
                f"({prev_confidence:.2f} → {new_confidence:.2f}). "
                f"Moving to HOLD"
            )
            return TradingAction.HOLD

        # Accept new action if confidence is sufficient
        return new_action

    def save_signals(
        self,
        signals: Dict[str, Dict],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Save signals to file.

        Args:
            signals: Signals dictionary
            filename: Optional filename (default: signals_YYYYMMDD_HHMMSS.json)

        Returns:
            Path to saved file
        """
        if filename is None:
            filename = f"signals_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self.signals_dir / filename

        # Add metadata
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "signal_count": len(signals),
            "signals": signals,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(signals)} signals to {filepath}")

        return filepath

    def load_signals(self, filename: str) -> Dict[str, Dict]:
        """
        Load signals from file.

        Args:
            filename: Filename or path to signals file

        Returns:
            Signals dictionary
        """
        filepath = Path(filename)
        if not filepath.is_absolute():
            filepath = self.signals_dir / filename

        if not filepath.exists():
            logger.warning(f"Signals file not found: {filepath}")
            return {}

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        signals = data.get("signals", {})
        logger.info(f"Loaded {len(signals)} signals from {filepath}")

        return signals

    def get_latest_signals(self) -> Optional[Dict[str, Dict]]:
        """
        Get the latest saved signals.

        Returns:
            Latest signals dictionary or None if no signals found
        """
        signal_files = sorted(self.signals_dir.glob("signals_*.json"), reverse=True)

        if not signal_files:
            logger.info("No previous signals found")
            return None

        latest_file = signal_files[0]
        return self.load_signals(latest_file.name)

    def get_changed_signals(
        self,
        current_signals: Dict[str, Dict],
        previous_signals: Dict[str, Dict],
    ) -> Dict[str, Dict]:
        """
        Get signals that have changed from previous.

        Args:
            current_signals: Current signals
            previous_signals: Previous signals

        Returns:
            Dictionary of changed signals with change info
        """
        changed = {}

        for ticker, current in current_signals.items():
            # New ticker
            if ticker not in previous_signals:
                changed[ticker] = {
                    **current,
                    "change_type": "new",
                    "previous_action": None,
                }
                continue

            prev = previous_signals[ticker]

            # Action changed
            if current["action"] != prev["action"]:
                changed[ticker] = {
                    **current,
                    "change_type": "action_changed",
                    "previous_action": prev["action"],
                }
                continue

            # Confidence changed significantly (>10%)
            conf_change = abs(current["confidence"] - prev.get("confidence", 0.0))
            if conf_change > 0.1:
                changed[ticker] = {
                    **current,
                    "change_type": "confidence_changed",
                    "previous_action": prev["action"],
                    "confidence_change": conf_change,
                }

        logger.info(f"Found {len(changed)} changed signals")

        return changed

    @staticmethod
    def _count_action(signals: Dict[str, Dict], action: TradingAction) -> int:
        """Count signals with specific action."""
        return sum(1 for s in signals.values() if s["action"] == action.value)

    def get_summary(self, signals: Dict[str, Dict]) -> Dict:
        """
        Get summary statistics for signals.

        Args:
            signals: Signals dictionary

        Returns:
            Summary dictionary
        """
        buy_signals = [
            s for s in signals.values()
            if s["action"] == TradingAction.BUY.value
        ]
        sell_signals = [
            s for s in signals.values()
            if s["action"] == TradingAction.SELL.value
        ]
        hold_signals = [
            s for s in signals.values()
            if s["action"] == TradingAction.HOLD.value
        ]

        # High confidence signals
        high_conf_buy = [
            s for s in buy_signals
            if s["confidence"] >= self.HIGH_CONFIDENCE
        ]
        high_conf_sell = [
            s for s in sell_signals
            if s["confidence"] >= self.HIGH_CONFIDENCE
        ]

        return {
            "total": len(signals),
            "buy": len(buy_signals),
            "sell": len(sell_signals),
            "hold": len(hold_signals),
            "high_confidence_buy": len(high_conf_buy),
            "high_confidence_sell": len(high_conf_sell),
            "buy_tickers": [s["ticker"] for s in buy_signals],
            "sell_tickers": [s["ticker"] for s in sell_signals],
            "high_conf_buy_tickers": [s["ticker"] for s in high_conf_buy],
            "high_conf_sell_tickers": [s["ticker"] for s in high_conf_sell],
        }
