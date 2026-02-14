"""
트레이딩 스케줄러 (한국 시간)

장전 및 실시간 트레이딩 분석 스케줄링 및 실행
한국 표준시(KST) 기준으로 미국 시장 트레이딩 진행
"""

import time
from datetime import datetime, time as dt_time, timedelta
from typing import Callable, Optional, Dict, Any
from zoneinfo import ZoneInfo
from loguru import logger


class TradingScheduler:
    """트레이딩 파이프라인 스케줄러 (KST 기준)"""

    # 타임존
    KST_TIMEZONE = ZoneInfo("Asia/Seoul")
    ET_TIMEZONE = ZoneInfo("America/New_York")

    # 미국 시장 시간 (ET, 내부 계산용)
    PRE_MARKET_START_ET = dt_time(4, 0)   # 오전 4:00 ET
    MARKET_OPEN_ET = dt_time(9, 30)       # 오전 9:30 ET
    MARKET_CLOSE_ET = dt_time(16, 0)      # 오후 4:00 PM ET
    AFTER_HOURS_END_ET = dt_time(20, 0)   # 오후 8:00 PM ET

    def __init__(
        self,
        pre_market_callback: Optional[Callable] = None,
        realtime_callback: Optional[Callable] = None,
        post_market_callback: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None,
        discord_notifier: Optional[Any] = None,
        test_mode: bool = False,
    ):
        """
        트레이딩 스케줄러 초기화

        Args:
            pre_market_callback: 장전 분석 콜백 함수
            realtime_callback: 실시간 분석 콜백 함수
            post_market_callback: 장후 백테스팅 콜백 함수
            config: 파이프라인 설정 (없으면 기본값 사용)
            discord_notifier: Discord 알림 객체 (상태 알림용)
            test_mode: True면 스케줄 무시하고 즉시 실행
        """
        self.pre_market_callback = pre_market_callback
        self.realtime_callback = realtime_callback
        self.post_market_callback = post_market_callback
        self.discord = discord_notifier
        self.test_mode = test_mode

        # 설정 로드 (기본값 제공)
        self.config = config or self._get_default_config()

        # 스케줄 설정 파싱
        premarket_time_str = self.config["premarket"]["schedule_time"]
        hour, minute = map(int, premarket_time_str.split(":"))
        self.PRE_MARKET_ANALYSIS_TIME_ET = dt_time(hour, minute)

        self.SCHEDULE_WINDOW_MINUTES = self.config["premarket"]["schedule_window_minutes"]
        self.REALTIME_INTERVAL_MINUTES = self.config["realtime"]["interval_minutes"]
        self.CHECK_INTERVAL_SECONDS = self.config["scheduler"]["check_interval_seconds"]

        self.is_running = False
        self.pre_market_done_today = False
        self.post_market_done_today = False
        self.last_realtime_run: Optional[datetime] = None
        self.market_holiday_notified_today = False
        self.market_open_notified_today = False

        logger.info("트레이딩 스케줄러 초기화 완료 (한국 시간)")

    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            "premarket": {
                "schedule_time": "09:00",
                "schedule_window_minutes": 5,
            },
            "realtime": {
                "interval_minutes": 20,
            },
            "scheduler": {
                "check_interval_seconds": 60,
            },
        }

    def get_current_time_kst(self) -> datetime:
        """Get current time in KST timezone."""
        return datetime.now(self.KST_TIMEZONE)

    def get_current_time_et(self) -> datetime:
        """Get current time in ET timezone."""
        return datetime.now(self.ET_TIMEZONE)

    def is_market_day(self, dt_et: Optional[datetime] = None) -> bool:
        """
        시장 개장일인지 확인 (ET 기준 평일)

        Args:
            dt_et: 확인할 ET 시간 (기본값: 현재)

        Returns:
            미국 동부시간 기준 평일(월-금)이면 True
        """
        if dt_et is None:
            dt_et = self.get_current_time_et()

        # 0 = 월요일, 6 = 일요일
        return dt_et.weekday() < 5

    def is_market_open(self, dt_et: Optional[datetime] = None) -> bool:
        """
        현재 시장이 열려있는지 확인

        Args:
            dt_et: 확인할 ET 시간 (기본값: 현재)

        Returns:
            시장 개장 중이면 True
        """
        if dt_et is None:
            dt_et = self.get_current_time_et()

        if not self.is_market_day(dt_et):
            return False

        current_time = dt_et.time()
        return self.MARKET_OPEN_ET <= current_time < self.MARKET_CLOSE_ET

    def is_pre_market_time(self, dt_et: Optional[datetime] = None) -> bool:
        """
        프리마켓 시간인지 확인

        Args:
            dt_et: 확인할 ET 시간 (기본값: 현재)

        Returns:
            프리마켓 시간이면 True
        """
        if dt_et is None:
            dt_et = self.get_current_time_et()

        if not self.is_market_day(dt_et):
            return False

        current_time = dt_et.time()
        return self.PRE_MARKET_START_ET <= current_time < self.MARKET_OPEN_ET

    def should_run_pre_market_analysis(self) -> bool:
        """
        장전 분석을 지금 실행해야 하는지 확인

        Returns:
            장전 분석 실행 시간이면 True
        """
        now_et = self.get_current_time_et()

        # 개장일이 아니면 실행 안 함
        if not self.is_market_day(now_et):
            return False

        # 오늘 이미 실행했으면 실행 안 함
        if self.pre_market_done_today:
            # 장 시작 후 플래그 리셋
            if now_et.time() >= self.MARKET_OPEN_ET:
                self.pre_market_done_today = False
            return False

        # 실행 시간인지 확인
        current_time = now_et.time()

        # PRE_MARKET_ANALYSIS_TIME_ET에 실행 (예: 9:00 AM ET)
        # 설정된 윈도우 시간 내에서 실행 허용
        time_diff_minutes = (
            current_time.hour * 60 + current_time.minute
            - (self.PRE_MARKET_ANALYSIS_TIME_ET.hour * 60 + self.PRE_MARKET_ANALYSIS_TIME_ET.minute)
        )

        return 0 <= time_diff_minutes < self.SCHEDULE_WINDOW_MINUTES

    def should_run_realtime_analysis(self) -> bool:
        """
        실시간 분석을 지금 실행해야 하는지 확인

        Returns:
            실시간 분석 실행 시간이면 True
        """
        now_et = self.get_current_time_et()

        # 시장이 열려있어야 함
        if not self.is_market_open(now_et):
            return False

        # 인터벌 확인
        if self.last_realtime_run is None:
            # 장 시작 후 첫 실행
            return True

        # 충분한 시간이 지났는지 확인
        minutes_since_last = (now_et - self.last_realtime_run).total_seconds() / 60

        return minutes_since_last >= self.REALTIME_INTERVAL_MINUTES

    def should_run_post_market_analysis(self) -> bool:
        """
        장후 백테스팅을 지금 실행해야 하는지 확인

        Returns:
            장후 백테스팅 실행 시간이면 True
        """
        now_et = self.get_current_time_et()

        # 개장일이 아니면 실행 안 함
        if not self.is_market_day(now_et):
            return False

        # 오늘 이미 실행했으면 실행 안 함
        if self.post_market_done_today:
            # 자정 지나면 플래그 리셋
            if now_et.time().hour == 0 and now_et.time().minute < 5:
                self.post_market_done_today = False
            return False

        # 장 마감 후 10분 뒤에 실행 (16:10 ET)
        current_time = now_et.time()
        post_market_time = dt_time(16, 10)  # 장 마감 10분 후

        # 16:10 ~ 16:15 사이에 실행
        time_diff_minutes = (
            current_time.hour * 60 + current_time.minute
            - (post_market_time.hour * 60 + post_market_time.minute)
        )

        return 0 <= time_diff_minutes < 5

    def run_pre_market_analysis(self) -> bool:
        """
        장전 분석 실행

        Returns:
            성공 시 True
        """
        if not self.pre_market_callback:
            logger.warning("장전 분석 콜백이 설정되지 않음")
            return False

        try:
            now_kst = self.get_current_time_kst()
            now_et = self.get_current_time_et()
            logger.info(f"🔔 장전 분석 실행 중: {now_kst.strftime('%H:%M:%S')} KST ({now_et.strftime('%H:%M:%S')} ET)...")

            # 콜백 실행
            self.pre_market_callback()

            # 오늘 실행 완료 표시
            self.pre_market_done_today = True

            logger.success("✓ 장전 분석 완료")
            return True

        except Exception as e:
            logger.error(f"장전 분석 실패: {e}")
            return False

    def run_realtime_analysis(self) -> bool:
        """
        실시간 분석 실행

        Returns:
            성공 시 True
        """
        if not self.realtime_callback:
            logger.warning("실시간 분석 콜백이 설정되지 않음")
            return False

        try:
            now_kst = self.get_current_time_kst()
            now_et = self.get_current_time_et()
            logger.info(f"🚨 실시간 분석 실행 중: {now_kst.strftime('%H:%M:%S')} KST ({now_et.strftime('%H:%M:%S')} ET)...")

            # 콜백 실행
            self.realtime_callback()

            # 마지막 실행 시간 업데이트 (ET 기준)
            self.last_realtime_run = now_et

            logger.success("✓ 실시간 분석 완료")
            return True

        except Exception as e:
            logger.error(f"실시간 분석 실패: {e}")
            return False

    def run_post_market_analysis(self) -> bool:
        """
        장후 백테스팅 실행

        Returns:
            성공 시 True
        """
        if not self.post_market_callback:
            logger.warning("장후 백테스팅 콜백이 설정되지 않음")
            return False

        try:
            now_kst = self.get_current_time_kst()
            now_et = self.get_current_time_et()
            logger.info(f"📊 장후 백테스팅 실행 중: {now_kst.strftime('%H:%M:%S')} KST ({now_et.strftime('%H:%M:%S')} ET)...")

            # 콜백 실행
            self.post_market_callback()

            # 오늘 실행 완료 표시
            self.post_market_done_today = True

            logger.success("✓ 장후 백테스팅 완료")
            return True

        except Exception as e:
            logger.error(f"장후 백테스팅 실패: {e}")
            return False

    def start(self, run_forever: bool = True) -> None:
        """
        스케줄러 시작

        Args:
            run_forever: True면 무한 실행, False면 한 번만 실행
        """
        self.is_running = True

        logger.info("=" * 70)
        logger.info("🐦‍⬛ 까악 트레이딩 파이프라인 시작 (한국 시간)")
        logger.info("=" * 70)

        now_kst = self.get_current_time_kst()
        now_et = self.get_current_time_et()

        logger.info(f"현재 시각 (KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"현재 시각 (ET):  {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"개장일: {self.is_market_day()}")
        logger.info(f"장 개장: {self.is_market_open()}")
        logger.info(f"프리마켓: {self.is_pre_market_time()}")

        logger.info("\n스케줄 (서머타임 자동 반영):")
        logger.info(f"  • 장전 분석: {self.PRE_MARKET_ANALYSIS_TIME_ET.strftime('%H:%M')} ET = 약 23:00 KST (표준시) / 22:00 KST (서머타임)")
        logger.info(f"  • 실시간 분석: 장중 매 {self.REALTIME_INTERVAL_MINUTES}분")
        logger.info(f"  • 시장 시간: 23:30-06:00 KST (표준시) / 22:30-05:00 KST (서머타임)")
        logger.info("=" * 70 + "\n")

        # Discord 시작 알림 전송
        if self.discord and not self.test_mode:
            try:
                next_action, time_until_next, _ = self.get_next_action_info()
                self.discord.send_startup_message(
                    current_time_kst=now_kst.strftime('%Y-%m-%d %H:%M:%S'),
                    current_time_et=now_et.strftime('%Y-%m-%d %H:%M:%S'),
                    is_market_day=self.is_market_day(),
                    next_action=next_action,
                    time_until_next=time_until_next
                )
            except Exception as e:
                logger.warning(f"시작 알림 전송 실패: {e}")

        # 테스트 모드 - 즉시 실행
        if self.test_mode:
            logger.info("테스트 모드 - 즉시 실행")

            if self.pre_market_callback:
                logger.info("\n[테스트] 장전 분석 실행 중...")
                self.run_pre_market_analysis()

            if self.realtime_callback:
                logger.info("\n[테스트] 실시간 분석 실행 중...")
                self.run_realtime_analysis()

            if self.post_market_callback:
                logger.info("\n[테스트] 장후 백테스팅 실행 중...")
                self.run_post_market_analysis()

            logger.info("\n테스트 모드 완료")
            return

        # 일반 모드 - 스케줄에 따라 실행
        try:
            while self.is_running:
                now_et = self.get_current_time_et()

                # 휴장일 알림 (하루에 한 번만)
                if not self.is_market_day(now_et):
                    if not self.market_holiday_notified_today:
                        if self.discord:
                            try:
                                now_kst = self.get_current_time_kst()
                                # 다음 개장일 계산
                                days_until = (7 - now_et.weekday()) % 7 or 1
                                next_market = now_et + timedelta(days=days_until)
                                next_market_str = next_market.strftime('%Y-%m-%d (%A)')

                                self.discord.send_market_holiday(
                                    current_time_kst=now_kst.strftime('%Y-%m-%d %H:%M:%S'),
                                    current_time_et=now_et.strftime('%Y-%m-%d %H:%M:%S'),
                                    next_market_day=next_market_str
                                )
                                self.market_holiday_notified_today = True
                            except Exception as e:
                                logger.warning(f"휴장일 알림 전송 실패: {e}")
                    # 자정 지나면 플래그 리셋
                    if now_et.time().hour == 0 and now_et.time().minute < 5:
                        self.market_holiday_notified_today = False
                else:
                    # 개장일이면 플래그 리셋
                    self.market_holiday_notified_today = False

                # 장 시작 알림 (장 시작 후 5분 이내 한 번만)
                if self.is_market_open(now_et) and not self.market_open_notified_today:
                    current_time = now_et.time()
                    open_minutes = (current_time.hour - self.MARKET_OPEN_ET.hour) * 60 + \
                                  (current_time.minute - self.MARKET_OPEN_ET.minute)

                    if 0 <= open_minutes <= 5:
                        if self.discord:
                            try:
                                now_kst = self.get_current_time_kst()
                                plan = f"• 실시간 분석: 매 {self.REALTIME_INTERVAL_MINUTES}분마다 뉴스 체크\n"
                                plan += f"• 장 마감: {self.MARKET_CLOSE_ET.strftime('%H:%M')} ET까지\n"
                                plan += "• 중요 뉴스 발생 시 즉시 알림 전송"

                                self.discord.send_market_open_plan(
                                    current_time_kst=now_kst.strftime('%Y-%m-%d %H:%M:%S'),
                                    current_time_et=now_et.strftime('%Y-%m-%d %H:%M:%S'),
                                    plan=plan
                                )
                                self.market_open_notified_today = True
                            except Exception as e:
                                logger.warning(f"장 시작 알림 전송 실패: {e}")

                # 장 마감 후 플래그 리셋
                if not self.is_market_open(now_et):
                    self.market_open_notified_today = False

                # 장전 분석 체크
                if self.should_run_pre_market_analysis():
                    self.run_pre_market_analysis()

                # 실시간 분석 체크
                if self.should_run_realtime_analysis():
                    self.run_realtime_analysis()

                # 장후 백테스팅 체크
                if self.should_run_post_market_analysis():
                    self.run_post_market_analysis()

                # 다음 체크까지 대기 (설정된 간격)
                time.sleep(self.CHECK_INTERVAL_SECONDS)

                if not run_forever:
                    break

        except KeyboardInterrupt:
            logger.info("\n🛑 사용자에 의해 스케줄러 중지")
            self.stop()

    def stop(self) -> None:
        """스케줄러 중지"""
        self.is_running = False
        logger.info("스케줄러 중지됨")

    def get_next_action_info(self) -> tuple[str, str, int]:
        """
        다음 예정 동작과 남은 시간 계산

        Returns:
            (동작명, 시간 문자열, 남은 분) 튜플
        """
        now_et = self.get_current_time_et()

        # 개장일이 아니면 다음 개장일 찾기
        if not self.is_market_day(now_et):
            # 다음 평일까지 일수 계산
            days_until_monday = (7 - now_et.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 1  # 일요일이면 월요일까지
            elif now_et.weekday() >= 5:  # 토요일 또는 일요일
                days_until_monday = (7 - now_et.weekday()) % 7 or 1

            next_market = now_et.replace(hour=self.PRE_MARKET_ANALYSIS_TIME_ET.hour,
                                         minute=self.PRE_MARKET_ANALYSIS_TIME_ET.minute,
                                         second=0, microsecond=0)
            next_market = next_market + timedelta(days=days_until_monday)
            minutes_until = int((next_market - now_et).total_seconds() / 60)

            if minutes_until < 60:
                time_str = f"{minutes_until}분 후"
            elif minutes_until < 1440:
                hours = minutes_until // 60
                mins = minutes_until % 60
                time_str = f"{hours}시간 {mins}분 후" if mins > 0 else f"{hours}시간 후"
            else:
                days = minutes_until // 1440
                time_str = f"{days}일 후"

            return "장전 분석 (다음 개장)", time_str, minutes_until

        # 개장일인 경우
        current_time = now_et.time()

        # 장전 분석 전
        if current_time < self.PRE_MARKET_ANALYSIS_TIME_ET and not self.pre_market_done_today:
            target = now_et.replace(hour=self.PRE_MARKET_ANALYSIS_TIME_ET.hour,
                                   minute=self.PRE_MARKET_ANALYSIS_TIME_ET.minute,
                                   second=0, microsecond=0)
            minutes_until = int((target - now_et).total_seconds() / 60)
            hours = minutes_until // 60
            mins = minutes_until % 60
            time_str = f"{hours}시간 {mins}분 후" if mins > 0 else f"{hours}시간 후"
            return "장전 분석", time_str, minutes_until

        # 장 시작 전
        if current_time < self.MARKET_OPEN_ET:
            target = now_et.replace(hour=self.MARKET_OPEN_ET.hour,
                                   minute=self.MARKET_OPEN_ET.minute,
                                   second=0, microsecond=0)
            minutes_until = int((target - now_et).total_seconds() / 60)
            if minutes_until < 60:
                time_str = f"{minutes_until}분 후"
            else:
                hours = minutes_until // 60
                mins = minutes_until % 60
                time_str = f"{hours}시간 {mins}분 후" if mins > 0 else f"{hours}시간 후"
            return "장 시작 (실시간 분석)", time_str, minutes_until

        # 장중
        if self.is_market_open(now_et):
            if self.last_realtime_run:
                next_run = self.last_realtime_run + timedelta(minutes=self.REALTIME_INTERVAL_MINUTES)
                minutes_until = int((next_run - now_et).total_seconds() / 60)
                time_str = f"{minutes_until}분 후"
            else:
                time_str = "곧"
                minutes_until = 0
            return "실시간 분석", time_str, minutes_until

        # 장 마감 후
        tomorrow = now_et + timedelta(days=1)
        # 내일이 주말이면 다음 월요일로
        if tomorrow.weekday() >= 5:
            days_until_monday = (7 - tomorrow.weekday()) % 7 or 1
            tomorrow = tomorrow + timedelta(days=days_until_monday)

        target = tomorrow.replace(hour=self.PRE_MARKET_ANALYSIS_TIME_ET.hour,
                                 minute=self.PRE_MARKET_ANALYSIS_TIME_ET.minute,
                                 second=0, microsecond=0)
        minutes_until = int((target - now_et).total_seconds() / 60)
        hours = minutes_until // 60
        time_str = f"{hours}시간 후" if hours < 24 else f"{hours // 24}일 후"
        return "장전 분석 (다음 개장)", time_str, minutes_until

    def get_status(self) -> dict:
        """
        현재 스케줄러 상태 조회

        Returns:
            상태 딕셔너리
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
