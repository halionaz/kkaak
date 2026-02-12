"""
Trading Scheduler (Korea Time)

Schedules and executes pre-market and real-time trading analysis.
Runs on Korea Standard Time (KST) for US market trading.
"""

import time
from datetime import datetime, time as dt_time
from typing import Callable, Optional
from zoneinfo import ZoneInfo
from loguru import logger


class TradingScheduler:
    """Scheduler for trading pipeline execution (KST-based)."""

    # Timezones
    KST_TIMEZONE = ZoneInfo("Asia/Seoul")
    ET_TIMEZONE = ZoneInfo("America/New_York")

    # US Market hours in ET (for internal calculation)
    PRE_MARKET_START_ET = dt_time(4, 0)  # 4:00 AM ET
    MARKET_OPEN_ET = dt_time(9, 30)  # 9:30 AM ET
    MARKET_CLOSE_ET = dt_time(16, 0)  # 4:00 PM ET
    AFTER_HOURS_END_ET = dt_time(20, 0)  # 8:00 PM ET

    # Our schedule in ET (will be displayed in KST to user)
    PRE_MARKET_ANALYSIS_TIME_ET = dt_time(9, 0)  # 9:00 AM ET = 23:00 KST (EST) / 22:00 KST (EDT)
    REALTIME_INTERVAL_MINUTES = 2.5  # 2.5 minutes interval (TEST MODE)

    def __init__(
        self,
        pre_market_callback: Optional[Callable] = None,
        realtime_callback: Optional[Callable] = None,
        test_mode: bool = False,
    ):
        """
        Initialize trading scheduler.

        Args:
            pre_market_callback: Function to call for pre-market analysis
            realtime_callback: Function to call for realtime analysis
            test_mode: If True, run immediately without waiting for schedule
        """
        self.pre_market_callback = pre_market_callback
        self.realtime_callback = realtime_callback
        self.test_mode = test_mode

        self.is_running = False
        self.pre_market_done_today = False
        self.last_realtime_run: Optional[datetime] = None

        logger.info("TradingScheduler initialized (Korea Time)")

    def get_current_time_kst(self) -> datetime:
        """Get current time in KST timezone."""
        return datetime.now(self.KST_TIMEZONE)

    def get_current_time_et(self) -> datetime:
        """Get current time in ET timezone."""
        return datetime.now(self.ET_TIMEZONE)

    def is_market_day(self, dt_et: Optional[datetime] = None) -> bool:
        """
        Check if it's a market day (weekday in ET).

        Args:
            dt_et: Datetime in ET to check (default: now)

        Returns:
            True if weekday (Mon-Fri) in US Eastern Time
        """
        if dt_et is None:
            dt_et = self.get_current_time_et()

        # 0 = Monday, 6 = Sunday
        return dt_et.weekday() < 5

    def is_market_open(self, dt_et: Optional[datetime] = None) -> bool:
        """
        Check if market is currently open.

        Args:
            dt_et: Datetime in ET to check (default: now)

        Returns:
            True if market is open
        """
        if dt_et is None:
            dt_et = self.get_current_time_et()

        if not self.is_market_day(dt_et):
            return False

        current_time = dt_et.time()
        return self.MARKET_OPEN_ET <= current_time < self.MARKET_CLOSE_ET

    def is_pre_market_time(self, dt_et: Optional[datetime] = None) -> bool:
        """
        Check if it's pre-market time.

        Args:
            dt_et: Datetime in ET to check (default: now)

        Returns:
            True if in pre-market hours
        """
        if dt_et is None:
            dt_et = self.get_current_time_et()

        if not self.is_market_day(dt_et):
            return False

        current_time = dt_et.time()
        return self.PRE_MARKET_START_ET <= current_time < self.MARKET_OPEN_ET

    def should_run_pre_market_analysis(self) -> bool:
        """
        Check if pre-market analysis should run now.

        Returns:
            True if it's time for pre-market analysis
        """
        now_et = self.get_current_time_et()

        # Not a market day
        if not self.is_market_day(now_et):
            return False

        # Already done today
        if self.pre_market_done_today:
            # Reset flag after market opens
            if now_et.time() >= self.MARKET_OPEN_ET:
                self.pre_market_done_today = False
            return False

        # Check if it's time
        current_time = now_et.time()

        # Run at PRE_MARKET_ANALYSIS_TIME_ET (9:00 AM ET = 23:00 KST / 22:00 KST)
        # Allow 5 minute window
        time_diff_minutes = (
            current_time.hour * 60 + current_time.minute
            - (self.PRE_MARKET_ANALYSIS_TIME_ET.hour * 60 + self.PRE_MARKET_ANALYSIS_TIME_ET.minute)
        )

        return 0 <= time_diff_minutes < 5

    def should_run_realtime_analysis(self) -> bool:
        """
        Check if realtime analysis should run now.

        Returns:
            True if it's time for realtime analysis
        """
        now_et = self.get_current_time_et()

        # Market must be open
        if not self.is_market_open(now_et):
            return False

        # Check interval
        if self.last_realtime_run is None:
            # First run after market opens
            return True

        # Check if enough time passed
        minutes_since_last = (now_et - self.last_realtime_run).total_seconds() / 60

        return minutes_since_last >= self.REALTIME_INTERVAL_MINUTES

    def run_pre_market_analysis(self) -> bool:
        """
        Execute pre-market analysis.

        Returns:
            True if successful
        """
        if not self.pre_market_callback:
            logger.warning("No pre-market callback configured")
            return False

        try:
            now_kst = self.get_current_time_kst()
            now_et = self.get_current_time_et()
            logger.info(f"🔔 Running PRE-MARKET analysis at {now_kst.strftime('%H:%M:%S')} KST ({now_et.strftime('%H:%M:%S')} ET)...")

            # Execute callback
            self.pre_market_callback()

            # Mark as done
            self.pre_market_done_today = True

            logger.success("✓ Pre-market analysis completed")
            return True

        except Exception as e:
            logger.error(f"Pre-market analysis failed: {e}")
            return False

    def run_realtime_analysis(self) -> bool:
        """
        Execute realtime analysis.

        Returns:
            True if successful
        """
        if not self.realtime_callback:
            logger.warning("No realtime callback configured")
            return False

        try:
            now_kst = self.get_current_time_kst()
            now_et = self.get_current_time_et()
            logger.info(f"🚨 Running REALTIME analysis at {now_kst.strftime('%H:%M:%S')} KST ({now_et.strftime('%H:%M:%S')} ET)...")

            # Execute callback
            self.realtime_callback()

            # Update last run time (in ET)
            self.last_realtime_run = now_et

            logger.success("✓ Realtime analysis completed")
            return True

        except Exception as e:
            logger.error(f"Realtime analysis failed: {e}")
            return False

    def start(self, run_forever: bool = True) -> None:
        """
        Start the scheduler.

        Args:
            run_forever: If True, run indefinitely. If False, run once.
        """
        self.is_running = True

        logger.info("=" * 70)
        logger.info("🐦‍⬛ KKAAK Trading Pipeline Started (Korea Time)")
        logger.info("=" * 70)

        now_kst = self.get_current_time_kst()
        now_et = self.get_current_time_et()

        logger.info(f"Current time (KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"Current time (ET):  {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"Market day: {self.is_market_day()}")
        logger.info(f"Market open: {self.is_market_open()}")
        logger.info(f"Pre-market time: {self.is_pre_market_time()}")

        logger.info("\nSchedule (자동으로 서머타임 반영):")
        logger.info(f"  • Pre-market analysis: {self.PRE_MARKET_ANALYSIS_TIME_ET.strftime('%H:%M')} ET = 약 23:00 KST (표준시) / 22:00 KST (서머타임)")
        logger.info(f"  • Realtime analysis: Every {self.REALTIME_INTERVAL_MINUTES} min during market hours")
        logger.info(f"  • Market hours: 23:30-06:00 KST (표준시) / 22:30-05:00 KST (서머타임)")
        logger.info("=" * 70 + "\n")

        # Test mode - run immediately
        if self.test_mode:
            logger.info("TEST MODE - Running immediately")

            if self.pre_market_callback:
                logger.info("\n[TEST] Running pre-market analysis...")
                self.run_pre_market_analysis()

            if self.realtime_callback:
                logger.info("\n[TEST] Running realtime analysis...")
                self.run_realtime_analysis()

            logger.info("\nTest mode complete")
            return

        # Normal mode - run on schedule
        try:
            while self.is_running:
                # Check pre-market analysis
                if self.should_run_pre_market_analysis():
                    self.run_pre_market_analysis()

                # Check realtime analysis
                if self.should_run_realtime_analysis():
                    self.run_realtime_analysis()

                # Sleep before next check (check every minute)
                time.sleep(60)

                if not run_forever:
                    break

        except KeyboardInterrupt:
            logger.info("\n🛑 Scheduler stopped by user")
            self.stop()

    def stop(self) -> None:
        """Stop the scheduler."""
        self.is_running = False
        logger.info("Scheduler stopped")

    def get_status(self) -> dict:
        """
        Get current scheduler status.

        Returns:
            Status dictionary
        """
        now_kst = self.get_current_time_kst()
        now_et = self.get_current_time_et()

        return {
            "running": self.is_running,
            "current_time_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "current_time_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "is_market_day": self.is_market_day(),
            "is_market_open": self.is_market_open(),
            "is_pre_market": self.is_pre_market_time(),
            "pre_market_done_today": self.pre_market_done_today,
            "last_realtime_run": (
                self.last_realtime_run.astimezone(self.KST_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S %Z")
                if self.last_realtime_run
                else None
            ),
        }
