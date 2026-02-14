"""
Position Tracker

Tracks current trading positions and manages position changes.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel
from loguru import logger

from .signal_manager import TradingAction


class Position(BaseModel):
    """Trading position model."""
    ticker: str
    action: str  # buy, sell, hold
    entry_date: datetime
    entry_confidence: float
    last_updated: datetime
    current_confidence: float
    signal_count: int = 1  # Number of times this signal was generated
    reasoning: Optional[str] = None


class PositionTracker:
    """Tracks and manages trading positions."""

    def __init__(self, positions_file: str = "data/signals/positions.json"):
        """
        Initialize position tracker.

        Args:
            positions_file: Path to positions file
        """
        self.positions_file = Path(positions_file)
        self.positions: Dict[str, Position] = {}

        # Load existing positions
        self.load_positions()

        logger.info("PositionTracker initialized")

    def update_positions(
        self,
        signals: Dict[str, Dict],
        save: bool = True,
    ) -> Dict[str, Dict]:
        """
        Update positions based on new signals.

        Args:
            signals: New signals dictionary
            save: Whether to save positions to file

        Returns:
            Dictionary of position changes
        """
        changes = {}
        now = datetime.now(timezone.utc)

        for ticker, signal in signals.items():
            action = signal["action"]
            confidence = signal["confidence"]
            reasoning = signal.get("reasoning", "")

            # Check if position exists
            if ticker in self.positions:
                position = self.positions[ticker]

                # Position unchanged
                if position.action == action:
                    # Update confidence and signal count
                    position.last_updated = now
                    position.current_confidence = confidence
                    position.signal_count += 1
                    continue

                # Position changed
                changes[ticker] = {
                    "ticker": ticker,
                    "change_type": "position_changed",
                    "old_action": position.action,
                    "new_action": action,
                    "old_confidence": position.current_confidence,
                    "new_confidence": confidence,
                    "reasoning": reasoning,
                    "days_held": (now - position.entry_date).days,
                }

                # Update position
                position.action = action
                position.entry_date = now
                position.entry_confidence = confidence
                position.last_updated = now
                position.current_confidence = confidence
                position.signal_count = 1
                position.reasoning = reasoning

                logger.info(
                    f"{ticker}: Position changed "
                    f"{changes[ticker]['old_action']} → {action}"
                )

            else:
                # New position
                position = Position(
                    ticker=ticker,
                    action=action,
                    entry_date=now,
                    entry_confidence=confidence,
                    last_updated=now,
                    current_confidence=confidence,
                    signal_count=1,
                    reasoning=reasoning,
                )
                self.positions[ticker] = position

                changes[ticker] = {
                    "ticker": ticker,
                    "change_type": "new_position",
                    "old_action": None,
                    "new_action": action,
                    "old_confidence": None,
                    "new_confidence": confidence,
                    "reasoning": reasoning,
                }

                logger.info(f"{ticker}: New position → {action}")

        if save:
            self.save_positions()

        logger.info(f"Updated positions. {len(changes)} changes detected")

        return changes

    def get_positions_by_action(self, action: TradingAction) -> List[Position]:
        """
        Get all positions with specific action.

        Args:
            action: Trading action to filter by

        Returns:
            List of positions
        """
        return [
            p for p in self.positions.values()
            if p.action == action.value
        ]

    def get_position(self, ticker: str) -> Optional[Position]:
        """
        Get position for a ticker.

        Args:
            ticker: Stock ticker

        Returns:
            Position or None if not found
        """
        return self.positions.get(ticker)

    def save_positions(self) -> None:
        """Save positions to file."""
        self.positions_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert positions to dict
        positions_dict = {
            ticker: position.model_dump(mode="json")
            for ticker, position in self.positions.items()
        }

        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "position_count": len(self.positions),
            "positions": positions_dict,
        }

        with open(self.positions_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        logger.debug(f"Saved {len(self.positions)} positions to {self.positions_file}")

    def load_positions(self) -> None:
        """Load positions from file."""
        if not self.positions_file.exists():
            logger.info("No existing positions file found")
            return

        try:
            with open(self.positions_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            positions_dict = data.get("positions", {})

            # Convert dict to Position objects
            self.positions = {}
            for ticker, pos_data in positions_dict.items():
                # Convert ISO strings back to datetime (timezone-aware)
                if isinstance(pos_data.get("entry_date"), str):
                    entry_date = datetime.fromisoformat(pos_data["entry_date"])
                    # Ensure timezone-aware
                    if entry_date.tzinfo is None:
                        entry_date = entry_date.replace(tzinfo=timezone.utc)
                    pos_data["entry_date"] = entry_date

                if isinstance(pos_data.get("last_updated"), str):
                    last_updated = datetime.fromisoformat(pos_data["last_updated"])
                    # Ensure timezone-aware
                    if last_updated.tzinfo is None:
                        last_updated = last_updated.replace(tzinfo=timezone.utc)
                    pos_data["last_updated"] = last_updated

                self.positions[ticker] = Position(**pos_data)

            logger.info(f"Loaded {len(self.positions)} positions from {self.positions_file}")

        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
            self.positions = {}

    def get_summary(self) -> Dict:
        """
        Get summary statistics for current positions.

        Returns:
            Summary dictionary
        """
        buy_positions = self.get_positions_by_action(TradingAction.BUY)
        sell_positions = self.get_positions_by_action(TradingAction.SELL)
        hold_positions = self.get_positions_by_action(TradingAction.HOLD)

        return {
            "total": len(self.positions),
            "buy": len(buy_positions),
            "sell": len(sell_positions),
            "hold": len(hold_positions),
            "buy_tickers": [p.ticker for p in buy_positions],
            "sell_tickers": [p.ticker for p in sell_positions],
            "hold_tickers": [p.ticker for p in hold_positions],
        }

    def get_actionable_changes(self, changes: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Filter changes to get actionable position changes.

        Actionable changes:
        - New BUY or SELL positions
        - Position changes from HOLD to BUY/SELL
        - Position changes from BUY ↔ SELL

        Args:
            changes: Position changes from update_positions()

        Returns:
            Filtered actionable changes
        """
        actionable = {}

        for ticker, change in changes.items():
            actionable_change = self._evaluate_change(change)
            if actionable_change:
                actionable[ticker] = actionable_change

        logger.info(f"Filtered to {len(actionable)} actionable changes")
        return actionable

    def _evaluate_change(self, change: Dict) -> Optional[Dict]:
        """
        Evaluate if a single change is actionable.

        Args:
            change: Position change dictionary

        Returns:
            Actionable change dictionary or None
        """
        # Guard clause: 새 포지션
        if change["change_type"] == "new_position":
            return self._handle_new_position(change)

        # Guard clause: 포지션 변경
        if change["change_type"] == "position_changed":
            return self._handle_position_changed(change)

        return None

    def _handle_new_position(self, change: Dict) -> Optional[Dict]:
        """
        Handle new position evaluation.

        Args:
            change: Position change dictionary

        Returns:
            Change if actionable (BUY or SELL), None otherwise
        """
        new_action = change["new_action"]

        # BUY or SELL만 실행 가능
        if new_action in [TradingAction.BUY.value, TradingAction.SELL.value]:
            return change

        return None

    def _handle_position_changed(self, change: Dict) -> Optional[Dict]:
        """
        Handle position change evaluation.

        Args:
            change: Position change dictionary

        Returns:
            Change if actionable, None otherwise
        """
        old_action = change.get("old_action")
        new_action = change["new_action"]

        # Case 1: HOLD → BUY/SELL
        if old_action == TradingAction.HOLD.value:
            if new_action in [TradingAction.BUY.value, TradingAction.SELL.value]:
                return change

        # Case 2: BUY ↔ SELL
        if self._is_buy_sell_reversal(old_action, new_action):
            return change

        # Case 3: BUY/SELL → HOLD (position closed)
        if new_action == TradingAction.HOLD.value:
            if old_action in [TradingAction.BUY.value, TradingAction.SELL.value]:
                return {**change, "change_type": "position_closed"}

        return None

    def _is_buy_sell_reversal(self, old_action: str, new_action: str) -> bool:
        """
        Check if action represents BUY ↔ SELL reversal.

        Args:
            old_action: Previous action
            new_action: New action

        Returns:
            True if reversal, False otherwise
        """
        return (
            (old_action == TradingAction.BUY.value and new_action == TradingAction.SELL.value)
            or (old_action == TradingAction.SELL.value and new_action == TradingAction.BUY.value)
        )
