"""
Discord Notification Module

Sends trading signals and reports to Discord via webhook.
"""

from datetime import datetime
from typing import Any

import requests
from loguru import logger


class DiscordNotifier:
    """Discord webhook notification handler."""

    def __init__(self, webhook_url: str):
        """
        Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url

    def _send_message(self, content: str = "", embeds: list[dict[str, Any]] = None) -> bool:
        """
        Send a message to Discord.

        Args:
            content: Plain text content
            embeds: List of Discord embed objects

        Returns:
            True if successful, False otherwise
        """
        payload = {}

        if content:
            payload["content"] = content

        if embeds:
            payload["embeds"] = embeds

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("✅ Discord 알림 전송 완료")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"🚨 Discord webhook 전송 실패: {e}")
            return False

    def send_test_message(self) -> bool:
        """
        테스트 메시지 전송 (webhook 연결 확인)

        Returns:
            성공 여부
        """
        content = "🐦‍⬛ **까악, 돈을 벌어다 주는 까마귀!**\n\n"
        content += "Discord webhook 연결이 정상적으로 완료되었습니다.\n"
        content += "이제 까악이 좋은 소식을 물어다 드릴 준비가 되었어요! 💰"

        return self._send_message(content=content)

    def send_premarket_report(
        self, signals: list[dict[str, Any]], news_summary: str | None = None
    ) -> bool:
        """
        장전 분석 리포트 전송

        Args:
            signals: 시그널 딕셔너리 리스트
                - ticker: 종목 심볼
                - action: buy/sell/hold
                - confidence: 0.0-1.0
                - reasoning: 분석 이유
                - technical: 선택적 기술 지표 (rsi, macd)
            news_summary: 오늘의 주요 뉴스 요약

        Returns:
            성공 여부
        """
        # 액션별로 시그널 분류
        buy_signals = [s for s in signals if s["action"] == "buy" and s["confidence"] >= 0.75]
        sell_signals = [s for s in signals if s["action"] == "sell" and s["confidence"] >= 0.75]
        hold_count = len([s for s in signals if s["action"] == "hold" or s["confidence"] < 0.75])

        # 메시지 작성
        now = datetime.now()
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += f"🔔 **장전 리포트** | {now.strftime('%Y-%m-%d %H:%M')} ET\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # BUY 시그널 (신뢰도 높은 것만)
        if buy_signals:
            content += "📈 **매수 시그널** (High Confidence)\n\n"
            for s in sorted(buy_signals, key=lambda x: x["confidence"], reverse=True)[:5]:
                content += f"**{s['ticker']}** `{int(s['confidence'] * 100)}%`\n"
                content += f"└─ {s['reasoning'][:80]}\n"
                # 기술 지표 있으면 추가
                if "technical" in s and s["technical"]:
                    tech = s["technical"]
                    content += (
                        f"   📊 RSI: {tech.get('rsi', 'N/A')} | MACD: {tech.get('macd', 'N/A')}\n"
                    )
                content += "\n"

        # SELL 시그널
        if sell_signals:
            content += "📉 **매도 시그널**\n\n"
            for s in sorted(sell_signals, key=lambda x: x["confidence"], reverse=True)[:5]:
                content += f"**{s['ticker']}** `{int(s['confidence'] * 100)}%`\n"
                content += f"└─ {s['reasoning'][:80]}\n"
                # 기술 지표 있으면 추가
                if "technical" in s and s["technical"]:
                    tech = s["technical"]
                    content += (
                        f"   📊 RSI: {tech.get('rsi', 'N/A')} | MACD: {tech.get('macd', 'N/A')}\n"
                    )
                content += "\n"

        # HOLD 요약
        if hold_count > 0:
            content += f"⏸️ **홀드**: {hold_count}개 종목\n\n"

        # 뉴스 요약 추가
        if news_summary:
            content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            content += f"💡 **오늘의 시장 이슈**\n\n{news_summary[:250]}\n"

        return self._send_message(content=content)

    def send_realtime_signal(
        self,
        ticker: str,
        action: str,
        confidence: float,
        reasoning: str,
        price_data: dict[str, Any] | None = None,
        news_title: str | None = None,
        news_url: str | None = None,
    ) -> bool:
        """
        실시간 트레이딩 시그널 전송

        Args:
            ticker: 종목 심볼
            action: buy/sell/hold
            confidence: 신뢰도 (0.0-1.0)
            reasoning: 분석 이유
            price_data: 가격 정보 (current, change_percent, rsi, macd, volume)
            news_title: 뉴스 헤드라인
            news_url: 뉴스 링크

        Returns:
            성공 여부
        """
        # 액션별 이모지
        action_emoji = {"buy": "📈", "sell": "📉", "hold": "⏸️"}
        emoji = action_emoji.get(action.lower(), "🚨")

        # 액션 한글 표시
        action_kr = {"buy": "매수", "sell": "매도", "hold": "홀드"}
        action_text = action_kr.get(action.lower(), action.upper())

        # 메시지 작성
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += f"🚨 **긴급 시그널** | {emoji} **{action_text.upper()}**\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        content += f"**{ticker}** `확신도 {int(confidence * 100)}%`\n\n"

        # 뉴스 제목 (인용 형태)
        if news_title:
            content += f'💬 *"{news_title}"*\n\n'

        # 현재 상태
        if price_data:
            content += "📊 **현재 상태**\n\n"
            if "current" in price_data:
                change = price_data.get("change_percent", 0)
                change_emoji = "📈" if change > 0 else "📉"
                content += (
                    f"💵 가격: **${price_data['current']:.2f}** {change_emoji} `{change:+.2f}%`\n"
                )

            tech_parts = []
            if "rsi" in price_data:
                tech_parts.append(f"RSI {price_data['rsi']:.1f}")
            if "macd" in price_data:
                tech_parts.append(f"MACD {price_data['macd']:+.2f}")
            if tech_parts:
                content += f"📈 지표: {' | '.join(tech_parts)}\n"

            if "volume" in price_data:
                vol = price_data["volume"]
                if isinstance(vol, dict) and "current" in vol and "avg_ratio" in vol:
                    content += f"📊 거래량: {vol['current']} `평균 대비 {vol['avg_ratio']:+.0f}%`\n"
            content += "\n"

        # 분석 이유
        content += f"💡 **분석**\n\n{reasoning}\n"

        # 뉴스 링크
        if news_url:
            content += f"\n🔗 [뉴스 원문 보기]({news_url})"

        return self._send_message(content=content)

    def send_postmarket_summary(
        self,
        total_signals: int,
        buy_count: int,
        sell_count: int,
        hold_count: int,
        breaking_signals: int = 0,
        buy_tickers: list[str] | None = None,
        sell_tickers: list[str] | None = None,
        virtual_return: float | None = None,
    ) -> bool:
        """
        장후 일일 요약 리포트 전송

        Args:
            total_signals: 오늘 생성된 총 시그널 수
            buy_count: BUY 시그널 개수
            sell_count: SELL 시그널 개수
            hold_count: HOLD 시그널 개수
            breaking_signals: 긴급 시그널 개수
            buy_tickers: BUY 종목 리스트
            sell_tickers: SELL 종목 리스트
            virtual_return: 가상 수익률 (참고용)

        Returns:
            성공 여부
        """
        # 메시지 작성
        today = datetime.now().strftime("%Y-%m-%d")
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += f"📊 **장후 요약** | {today}\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 까악 활동 요약
        content += "🐦‍⬛ **오늘의 까악 활동**\n\n"
        content += f"📌 총 시그널: **{total_signals}개**\n"
        content += f"   ├─ 📈 매수: {buy_count}개\n"
        content += f"   ├─ 📉 매도: {sell_count}개\n"
        content += f"   └─ ⏸️ 홀드: {hold_count}개\n"
        if breaking_signals > 0:
            content += f"\n🚨 긴급 시그널: {breaking_signals}개\n"
        content += "\n"

        # BUY/SELL 종목
        if buy_tickers and len(buy_tickers) > 0:
            ticker_str = ", ".join(buy_tickers[:8])
            if len(buy_tickers) > 8:
                ticker_str += f" 외 {len(buy_tickers) - 8}개"
            content += f"📈 **매수 종목**\n{ticker_str}\n\n"

        if sell_tickers and len(sell_tickers) > 0:
            ticker_str = ", ".join(sell_tickers[:8])
            if len(sell_tickers) > 8:
                ticker_str += f" 외 {len(sell_tickers) - 8}개"
            content += f"📉 **매도 종목**\n{ticker_str}\n\n"

        # 가상 수익률 (참고용)
        if virtual_return is not None:
            content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            return_emoji = "📈" if virtual_return > 0 else "📉"
            content += "💰 **가상 수익률** (참고용)\n\n"
            content += "오늘 시그널대로 투자했다면\n"
            content += f"{return_emoji} **{virtual_return:+.2f}%** 수익\n\n"

        # 마무리 메시지
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "내일도 까악이 좋은 소식 물어올게요! 🐦‍⬛💰"

        return self._send_message(content=content)

    def send_error(
        self, error_message: str, retry_info: str | None = None, context: str | None = None
    ) -> bool:
        """
        에러 알림 전송

        Args:
            error_message: 에러 메시지
            retry_info: 재시도 정보 (예: "다음 시도: 5분 후")
            context: 상세 정보

        Returns:
            성공 여부
        """
        content = "⚠️ **[시스템 알림]**\n\n"
        content += f"{error_message}\n"

        if retry_info:
            content += f"\n{retry_info}\n"

        if context:
            content += f"\n**상세 정보**: {context[:200]}\n"

        content += "\n까악이 잠시 날개를 쉬고 있어요. 곧 돌아올게요! 🐦‍⬛"

        return self._send_message(content=content)

    def send_startup_message(
        self,
        current_time_kst: str,
        current_time_et: str,
        is_market_day: bool,
        next_action: str | None = None,
        time_until_next: str | None = None,
    ) -> bool:
        """
        프로그램 시작 알림

        Args:
            current_time_kst: 현재 시각 (KST)
            current_time_et: 현재 시각 (ET)
            is_market_day: 오늘이 개장일인지 여부
            next_action: 다음 예정 동작 (예: "장전 분석")
            time_until_next: 다음 동작까지 남은 시간 (예: "2시간 30분 후")

        Returns:
            성공 여부
        """
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "🐦‍⬛ **까악 시스템 시작**\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        content += "까악, 돈을 벌어다 주는 까마귀가\n날개를 펼쳤어요!\n\n"

        content += "⏰ **현재 시각**\n"
        content += f"KST: {current_time_kst}\n"
        content += f"ET:  {current_time_et}\n\n"

        if is_market_day:
            content += "📅 **오늘은 개장일**\n\n"
            if next_action and time_until_next:
                content += "📍 다음 일정\n"
                content += f"   {next_action}\n"
                content += f"   ⏳ {time_until_next}\n"
        else:
            content += "🌙 **오늘은 휴장일**\n\n"
            content += "까악이 오늘은 쉬면서\n내일을 준비할게요.\n"
            if next_action and time_until_next:
                content += f"\n📅 다음 개장\n   ⏳ {time_until_next}\n"

        content += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "좋은 소식 찾으면 바로 알려드릴게요! 💰"

        return self._send_message(content=content)

    def send_shutdown_message(self, current_time_kst: str, reason: str = "정상 종료") -> bool:
        """
        프로그램 종료 알림

        Args:
            current_time_kst: 현재 시각 (KST)
            reason: 종료 사유

        Returns:
            성공 여부
        """
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "🐦‍⬛ **까악 시스템 종료**\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        content += f"⏰ 종료 시각\n   {current_time_kst}\n\n"
        content += f"📌 종료 사유\n   {reason}\n\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "까악이 잠시 날개를 접었어요.\n"
        content += "다시 시작하면 알려드릴게요! 👋"

        return self._send_message(content=content)

    def send_market_holiday(
        self, current_time_kst: str, current_time_et: str, next_market_day: str | None = None
    ) -> bool:
        """
        장 휴장일 알림

        Args:
            current_time_kst: 현재 시각 (KST)
            current_time_et: 현재 시각 (ET)
            next_market_day: 다음 개장일

        Returns:
            성공 여부
        """
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "🌙 **오늘은 휴장일**\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        content += "⏰ 현재 시각\n"
        content += f"KST: {current_time_kst}\n"
        content += f"ET:  {current_time_et}\n\n"
        content += "미국 증시가 오늘은 쉬는 날이에요.\n"
        content += "까악도 날개를 쉬면서\n다음 개장일을 준비할게요! 🐦‍⬛\n"

        if next_market_day:
            content += f"\n📅 다음 개장\n   {next_market_day}\n"

        content += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "내일 다시 만나요! 💤"

        return self._send_message(content=content)

    def send_status_update(
        self,
        current_time_kst: str,
        current_time_et: str,
        market_status: str,
        next_action: str | None = None,
        time_until_next: str | None = None,
        last_action: str | None = None,
        stats: dict[str, Any] | None = None,
    ) -> bool:
        """
        주기적 상태 업데이트

        Args:
            current_time_kst: 현재 시각 (KST)
            current_time_et: 현재 시각 (ET)
            market_status: 시장 상태 ("개장 전", "장중", "장 마감", "휴장")
            next_action: 다음 예정 동작
            time_until_next: 다음 동작까지 남은 시간
            last_action: 마지막으로 실행한 동작
            stats: 통계 정보 (선택)

        Returns:
            성공 여부
        """
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "🐦‍⬛ **까악 상태 업데이트**\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        content += f"⏰ {current_time_kst}\n   (ET: {current_time_et})\n\n"
        content += f"📊 시장 상태: **{market_status}**\n\n"

        if last_action:
            content += f"✅ 최근 활동\n   {last_action}\n\n"

        if next_action and time_until_next:
            content += f"⏳ 다음 일정\n   {next_action}\n   ({time_until_next})\n\n"

        if stats:
            content += "📈 **오늘의 활동**\n"
            if "signals_generated" in stats:
                content += f"   ├─ 시그널: {stats['signals_generated']}개\n"
            if "alerts_sent" in stats:
                content += f"   └─ 알림: {stats['alerts_sent']}개\n"
            content += "\n"

        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "까악이 계속 시장을 지켜보고 있어요! 👀"

        return self._send_message(content=content)

    def send_market_open_plan(
        self,
        current_time_kst: str,
        current_time_et: str,
        plan: str,
        monitored_tickers: list[str] | None = None,
    ) -> bool:
        """
        장 시작 시 오늘의 계획 알림

        Args:
            current_time_kst: 현재 시각 (KST)
            current_time_et: 현재 시각 (ET)
            plan: 오늘의 계획 설명
            monitored_tickers: 모니터링 중인 종목 리스트

        Returns:
            성공 여부
        """
        content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "🔔 **장 시작! 오늘의 계획**\n"
        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        content += f"⏰ {current_time_kst}\n   (ET: {current_time_et})\n\n"
        content += f"📋 **오늘의 일정**\n\n{plan}\n\n"

        if monitored_tickers:
            ticker_str = ", ".join(monitored_tickers[:10])
            if len(monitored_tickers) > 10:
                ticker_str += f" 외 {len(monitored_tickers) - 10}개"
            content += f"👀 **모니터링 종목**\n{ticker_str}\n\n"

        content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        content += "까악이 오늘도 열심히 소식 찾아볼게요! 💪"

        return self._send_message(content=content)


# 테스트 함수
def test_discord_webhook(webhook_url: str):
    """
    Discord webhook 연결 테스트

    Args:
        webhook_url: Discord webhook URL
    """
    notifier = DiscordNotifier(webhook_url)

    print("🐦‍⬛ Discord webhook 연결 테스트 중...")
    success = notifier.send_test_message()

    if success:
        print("✅ 테스트 메시지 전송 완료!")
        print("\n📨 실시간 시그널 메시지 테스트 중...")

        # 샘플 시그널 테스트
        notifier.send_realtime_signal(
            ticker="NVDA",
            action="buy",
            confidence=0.85,
            reasoning="AI 칩 수요 급증으로 단기 급등 예상. 경쟁사 대비 기술적 우위 확보. 데이터센터 매출 증가.",
            price_data={
                "current": 191.17,
                "change_percent": 2.5,
                "rsi": 65.2,
                "macd": 1.8,
                "volume": {"current": "1.2M", "avg_ratio": 150},
            },
            news_title="Nvidia announces breakthrough in AI chip technology",
            news_url="https://example.com/news",
        )
        print("✅ 시그널 메시지 전송 완료!")

        print("\n📊 장전 리포트 테스트 중...")
        notifier.send_premarket_report(
            signals=[
                {
                    "ticker": "NVDA",
                    "action": "buy",
                    "confidence": 0.85,
                    "reasoning": "AI 칩 신기술 발표로 긍정적 전망. GPU 시장 점유율 확대 중.",
                    "technical": {"rsi": 65, "macd": 1.8},
                },
                {
                    "ticker": "META",
                    "action": "sell",
                    "confidence": 0.76,
                    "reasoning": "규제 리스크 증가. 광고 매출 둔화 우려.",
                    "technical": {"rsi": 72, "macd": -0.5},
                },
            ],
            news_summary="AI 칩 수요 급증, 금리 동결 전망, 기술주 강세 예상",
        )
        print("✅ 장전 리포트 전송 완료!")
    else:
        print("❌ 테스트 메시지 전송 실패. Webhook URL을 확인해주세요.")


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print("❌ 오류: .env 파일에 DISCORD_WEBHOOK_URL이 없습니다")
        print("💡 .env 파일에 Discord webhook URL을 설정해주세요")
    else:
        test_discord_webhook(webhook_url)
