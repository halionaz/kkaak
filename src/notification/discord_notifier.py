"""
Discord Notification Module

Sends trading signals and reports to Discord via webhook.
"""

import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
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

    def _send_message(self, content: str = "", embeds: List[Dict[str, Any]] = None) -> bool:
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
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("✅ Discord 알림 전송 완료")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"🚨 Discord webhook 전송 실패: {e}")
            return False

    def send_test_message(self) -> bool:
        """
        Send a test message to verify webhook connection.

        Returns:
            True if successful, False otherwise
        """
        content = "🐦‍⬛ **까악 봇 연결 성공!**\n\n"
        content += "Discord webhook 연결이 정상적으로 완료되었습니다.\n"
        content += "이제 까악이 좋은 소식을 물어다 드릴 준비가 되었어요! 💰"

        return self._send_message(content=content)

    def send_premarket_report(
        self,
        signals: List[Dict[str, Any]],
        news_summary: Optional[str] = None
    ) -> bool:
        """
        Send pre-market analysis report.

        Args:
            signals: List of signal dictionaries with keys:
                - ticker: Stock ticker
                - action: buy/sell/hold
                - confidence: 0.0-1.0
                - reasoning: Explanation
                - technical: Optional dict with rsi, macd
            news_summary: Optional summary of today's major news

        Returns:
            True if successful, False otherwise
        """
        # Separate signals by action
        buy_signals = [s for s in signals if s["action"] == "buy" and s["confidence"] >= 0.75]
        sell_signals = [s for s in signals if s["action"] == "sell" and s["confidence"] >= 0.75]
        hold_count = len([s for s in signals if s["action"] == "hold" or s["confidence"] < 0.75])

        # Build message content
        now = datetime.now()
        content = f"🔔 **[PREMARKET REPORT]** {now.strftime('%Y-%m-%d %H:%M')} ET\n\n"

        # Add BUY signals (High Confidence)
        if buy_signals:
            content += "📈 **BUY 시그널** (High Confidence):\n"
            for s in sorted(buy_signals, key=lambda x: x['confidence'], reverse=True)[:5]:
                content += f"• **{s['ticker']}** ({int(s['confidence']*100)}%) - {s['reasoning'][:80]}\n"
                # Add technical indicators if available
                if "technical" in s and s["technical"]:
                    tech = s["technical"]
                    content += f"  📍 RSI: {tech.get('rsi', 'N/A')}, MACD: {tech.get('macd', 'N/A')}\n"
            content += "\n"

        # Add SELL signals
        if sell_signals:
            content += "⚠️ **SELL 시그널**:\n"
            for s in sorted(sell_signals, key=lambda x: x['confidence'], reverse=True)[:5]:
                content += f"• **{s['ticker']}** ({int(s['confidence']*100)}%) - {s['reasoning'][:80]}\n"
                # Add technical indicators if available
                if "technical" in s and s["technical"]:
                    tech = s["technical"]
                    content += f"  📍 RSI: {tech.get('rsi', 'N/A')}, MACD: {tech.get('macd', 'N/A')}\n"
            content += "\n"

        # Add HOLD summary
        content += f"✅ **HOLD**: 나머지 {hold_count}개 종목\n\n"

        # Add news summary if provided
        if news_summary:
            content += "---\n"
            content += f"💡 **오늘의 주요 뉴스**:\n{news_summary}\n"

        return self._send_message(content=content)

    def send_realtime_signal(
        self,
        ticker: str,
        action: str,
        confidence: float,
        reasoning: str,
        price_data: Optional[Dict[str, Any]] = None,
        news_title: Optional[str] = None,
        news_url: Optional[str] = None
    ) -> bool:
        """
        Send real-time trading signal.

        Args:
            ticker: Stock ticker
            action: buy/sell/hold
            confidence: 0.0-1.0
            reasoning: Explanation
            price_data: Optional price info (current, change_percent, rsi, macd, volume)
            news_title: Optional news headline
            news_url: Optional news URL

        Returns:
            True if successful, False otherwise
        """
        # Build message content
        content = f"🚨 **[BREAKING]** **{ticker}** - {action.upper()} ({int(confidence*100)}%)\n\n"

        # Add news title in quoted format
        if news_title:
            content += f'"{news_title}"\n\n'

        # Add current status
        if price_data:
            content += "📍 **현재 상태**:\n"
            if "current" in price_data:
                change = price_data.get('change_percent', 0)
                change_emoji = "📈" if change > 0 else "📉"
                content += f"• Price: ${price_data['current']:.2f} ({change_emoji}{change:+.2f}%)\n"

            tech_parts = []
            if "rsi" in price_data:
                tech_parts.append(f"RSI: {price_data['rsi']:.1f}")
            if "macd" in price_data:
                tech_parts.append(f"MACD: {price_data['macd']:+.2f}")
            if tech_parts:
                content += f"• {', '.join(tech_parts)}\n"

            if "volume" in price_data:
                vol = price_data['volume']
                if isinstance(vol, dict) and 'current' in vol and 'avg_ratio' in vol:
                    content += f"• Volume: {vol['current']} (평균 대비 {vol['avg_ratio']:+.0f}%)\n"
            content += "\n"

        # Add analysis
        content += f"💡 **분석**:\n{reasoning}\n"

        # Add news link if available
        if news_url:
            content += f"\n🔗 [뉴스 원문]({news_url})"

        return self._send_message(content=content)

    def send_postmarket_summary(
        self,
        total_signals: int,
        buy_count: int,
        sell_count: int,
        hold_count: int,
        breaking_signals: int = 0,
        buy_tickers: Optional[List[str]] = None,
        sell_tickers: Optional[List[str]] = None,
        virtual_return: Optional[float] = None
    ) -> bool:
        """
        Send post-market daily summary.

        Args:
            total_signals: Total signals generated today
            buy_count: Number of BUY signals
            sell_count: Number of SELL signals
            hold_count: Number of HOLD signals
            breaking_signals: Number of breaking/urgent signals
            buy_tickers: List of BUY ticker symbols
            sell_tickers: List of SELL ticker symbols
            virtual_return: Virtual return percentage (for reference only)

        Returns:
            True if successful, False otherwise
        """
        # Build message content
        today = datetime.now().strftime('%Y-%m-%d')
        content = f"📊 **[DAILY SUMMARY]** {today}\n\n"

        # 까악 activity section
        content += "🐦‍⬛ **오늘의 까악 활동**:\n"
        content += f"• 총 시그널: {total_signals}개 (BUY {buy_count}, SELL {sell_count}, HOLD {hold_count})\n"
        if breaking_signals > 0:
            content += f"• 긴급 시그널: {breaking_signals}개\n"
        content += "\n"

        # BUY/SELL tickers
        if buy_tickers:
            content += f"📈 **BUY 종목**: {', '.join(buy_tickers[:10])}\n"
            if len(buy_tickers) > 10:
                content += f"   (외 {len(buy_tickers) - 10}개)\n"

        if sell_tickers:
            content += f"📉 **SELL 종목**: {', '.join(sell_tickers[:10])}\n"
            if len(sell_tickers) > 10:
                content += f"   (외 {len(sell_tickers) - 10}개)\n"

        content += "\n"

        # Virtual return (reference only)
        if virtual_return is not None:
            return_emoji = "📈" if virtual_return > 0 else "📉"
            content += f"💰 **가상 수익률** (참고용):\n"
            content += f"만약 오늘 모든 시그널을 따랐다면: {return_emoji}{virtual_return:+.2f}%\n\n"

        # Closing message
        content += "---\n"
        content += "내일도 까악이 좋은 소식을 물어올게요! 🐦‍⬛💰"

        return self._send_message(content=content)

    def send_error(
        self,
        error_message: str,
        retry_info: Optional[str] = None,
        context: Optional[str] = None
    ) -> bool:
        """
        Send error notification.

        Args:
            error_message: Error description
            retry_info: Optional retry information (e.g., "다음 시도: 5분 후")
            context: Optional context information

        Returns:
            True if successful, False otherwise
        """
        content = "⚠️ **[SYSTEM ALERT]**\n\n"
        content += f"{error_message}\n"

        if retry_info:
            content += f"{retry_info}\n"

        if context:
            content += f"\n**상세 정보:** {context}\n"

        content += "\n까악이 잠시 날개를 쉬고 있어요. 곧 돌아올게요! 🐦‍⬛"

        return self._send_message(content=content)


# Test function
def test_discord_webhook(webhook_url: str):
    """
    Test Discord webhook connection.

    Args:
        webhook_url: Discord webhook URL
    """
    notifier = DiscordNotifier(webhook_url)

    print("🐦‍⬛ Discord webhook 연결 테스트 중...")
    success = notifier.send_test_message()

    if success:
        print("✅ 테스트 메시지 전송 완료!")
        print("\n📨 실시간 시그널 메시지 테스트 중...")

        # Test a sample signal
        notifier.send_realtime_signal(
            ticker="AAPL",
            action="buy",
            confidence=0.85,
            reasoning="신제품 발표로 긍정적 전망. 기술 지표 상승세 유지 중.",
            price_data={
                "current": 175.50,
                "change_percent": 2.5,
                "rsi": 65.2,
                "macd": 1.8,
                "volume": {"current": "1.2M", "avg_ratio": 150}
            },
            news_title="Apple announces new AI-powered product line",
            news_url="https://example.com/news"
        )
        print("✅ 시그널 메시지 전송 완료!")

        print("\n📊 장전 리포트 테스트 중...")
        notifier.send_premarket_report(
            signals=[
                {
                    "ticker": "AAPL",
                    "action": "buy",
                    "confidence": 0.85,
                    "reasoning": "신제품 발표로 긍정적 전망",
                    "technical": {"rsi": 65, "macd": 1.8}
                },
                {
                    "ticker": "TSLA",
                    "action": "sell",
                    "confidence": 0.75,
                    "reasoning": "규제 리스크 증가",
                    "technical": {"rsi": 72, "macd": -0.5}
                }
            ],
            news_summary="기술주 강세 전망, Fed 금리 동결 예상"
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
