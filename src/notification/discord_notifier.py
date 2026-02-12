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
            logger.info("Discord message sent successfully")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Discord message: {e}")
            return False

    def send_test_message(self) -> bool:
        """
        Send a test message to verify webhook connection.

        Returns:
            True if successful, False otherwise
        """
        embed = {
            "title": "🤖 Trading Bot Connected",
            "description": "Discord webhook connection successful!",
            "color": 0x00ff00,  # Green
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "kkaak Trading Bot"
            }
        }

        return self._send_message(embeds=[embed])

    def send_premarket_report(self, signals: List[Dict[str, Any]]) -> bool:
        """
        Send pre-market analysis report.

        Args:
            signals: List of signal dictionaries with keys:
                - ticker: Stock ticker
                - action: buy/sell/hold
                - confidence: 0.0-1.0
                - reasoning: Explanation

        Returns:
            True if successful, False otherwise
        """
        # Separate signals by action
        buy_signals = [s for s in signals if s["action"] == "buy" and s["confidence"] >= 0.75]
        sell_signals = [s for s in signals if s["action"] == "sell" and s["confidence"] >= 0.75]
        hold_count = len([s for s in signals if s["action"] == "hold"])

        # Build embed
        embed = {
            "title": "📊 Pre-Market Report",
            "description": f"Market Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M ET')}",
            "color": 0x3498db,  # Blue
            "fields": [],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "kkaak Trading Bot | Pre-Market Analysis"
            }
        }

        # Add BUY signals
        if buy_signals:
            buy_text = "\n".join([
                f"• **{s['ticker']}** ({int(s['confidence']*100)}%) - {s['reasoning'][:100]}"
                for s in sorted(buy_signals, key=lambda x: x['confidence'], reverse=True)[:5]
            ])
            embed["fields"].append({
                "name": f"📈 BUY Signals ({len(buy_signals)})",
                "value": buy_text,
                "inline": False
            })

        # Add SELL signals
        if sell_signals:
            sell_text = "\n".join([
                f"• **{s['ticker']}** ({int(s['confidence']*100)}%) - {s['reasoning'][:100]}"
                for s in sorted(sell_signals, key=lambda x: x['confidence'], reverse=True)[:5]
            ])
            embed["fields"].append({
                "name": f"📉 SELL Signals ({len(sell_signals)})",
                "value": sell_text,
                "inline": False
            })

        # Add summary
        embed["fields"].append({
            "name": "📋 Summary",
            "value": f"HOLD: {hold_count} stocks | Total monitored: {len(signals)}",
            "inline": False
        })

        return self._send_message(embeds=[embed])

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
            price_data: Optional price info (current, change_percent, rsi, macd)
            news_title: Optional news headline
            news_url: Optional news URL

        Returns:
            True if successful, False otherwise
        """
        # Determine color based on action
        color_map = {
            "buy": 0x00ff00,   # Green
            "sell": 0xff0000,  # Red
            "hold": 0xffa500   # Orange
        }
        color = color_map.get(action.lower(), 0x808080)

        # Determine emoji
        emoji_map = {
            "buy": "🚨 BUY",
            "sell": "⚠️ SELL",
            "hold": "⏸️ HOLD"
        }
        emoji = emoji_map.get(action.lower(), "📊")

        # Build description
        description = f"**Confidence:** {int(confidence*100)}%\n"
        description += f"**Action:** {action.upper()}\n\n"
        description += f"💡 {reasoning}"

        # Build embed
        embed = {
            "title": f"{emoji} Signal - {ticker}",
            "description": description,
            "color": color,
            "fields": [],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "kkaak Trading Bot | Real-time Signal"
            }
        }

        # Add price data if available
        if price_data:
            price_text = ""
            if "current" in price_data:
                price_text += f"Price: ${price_data['current']:.2f}"
            if "change_percent" in price_data:
                change = price_data['change_percent']
                emoji = "📈" if change > 0 else "📉"
                price_text += f" ({emoji}{change:+.2f}%)"
            if "rsi" in price_data:
                price_text += f"\nRSI: {price_data['rsi']:.1f}"
            if "macd" in price_data:
                price_text += f" | MACD: {price_data['macd']:+.2f}"

            embed["fields"].append({
                "name": "📍 Market Data",
                "value": price_text,
                "inline": False
            })

        # Add news if available
        if news_title:
            news_text = news_title
            if news_url:
                news_text = f"[{news_title}]({news_url})"

            embed["fields"].append({
                "name": "📰 Related News",
                "value": news_text,
                "inline": False
            })

        return self._send_message(embeds=[embed])

    def send_postmarket_summary(
        self,
        total_signals: int,
        buy_count: int,
        sell_count: int,
        hold_count: int,
        top_signals: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Send post-market daily summary.

        Args:
            total_signals: Total signals generated today
            buy_count: Number of BUY signals
            sell_count: Number of SELL signals
            hold_count: Number of HOLD signals
            top_signals: Optional list of top signals

        Returns:
            True if successful, False otherwise
        """
        embed = {
            "title": "📊 Daily Summary",
            "description": f"Trading Day Summary - {datetime.now().strftime('%Y-%m-%d')}",
            "color": 0x9b59b6,  # Purple
            "fields": [
                {
                    "name": "📈 BUY Signals",
                    "value": str(buy_count),
                    "inline": True
                },
                {
                    "name": "📉 SELL Signals",
                    "value": str(sell_count),
                    "inline": True
                },
                {
                    "name": "⏸️ HOLD Signals",
                    "value": str(hold_count),
                    "inline": True
                },
                {
                    "name": "📊 Total Signals",
                    "value": str(total_signals),
                    "inline": False
                }
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "kkaak Trading Bot | Daily Summary"
            }
        }

        # Add top signals if available
        if top_signals:
            top_text = "\n".join([
                f"• **{s['ticker']}** - {s['action'].upper()} ({int(s['confidence']*100)}%)"
                for s in top_signals[:5]
            ])
            embed["fields"].append({
                "name": "⭐ Top Signals",
                "value": top_text,
                "inline": False
            })

        return self._send_message(embeds=[embed])

    def send_error(self, error_message: str, context: Optional[str] = None) -> bool:
        """
        Send error notification.

        Args:
            error_message: Error description
            context: Optional context information

        Returns:
            True if successful, False otherwise
        """
        description = f"❌ {error_message}"
        if context:
            description += f"\n\n**Context:** {context}"

        embed = {
            "title": "🚨 Bot Error",
            "description": description,
            "color": 0xff0000,  # Red
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "kkaak Trading Bot | Error Alert"
            }
        }

        return self._send_message(embeds=[embed])


# Test function
def test_discord_webhook(webhook_url: str):
    """
    Test Discord webhook connection.

    Args:
        webhook_url: Discord webhook URL
    """
    notifier = DiscordNotifier(webhook_url)

    print("Testing Discord webhook connection...")
    success = notifier.send_test_message()

    if success:
        print("✓ Test message sent successfully!")
        print("\nTesting signal message...")

        # Test a sample signal
        notifier.send_realtime_signal(
            ticker="AAPL",
            action="buy",
            confidence=0.85,
            reasoning="Strong positive earnings report with revenue beat. Technical indicators showing bullish momentum.",
            price_data={
                "current": 175.50,
                "change_percent": 2.5,
                "rsi": 65.2,
                "macd": 1.8
            },
            news_title="Apple Reports Record Q4 Earnings",
            news_url="https://example.com/news"
        )
        print("✓ Signal message sent successfully!")
    else:
        print("✗ Failed to send test message. Check your webhook URL.")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL not found in .env file")
        print("Please set your Discord webhook URL in .env file")
    else:
        test_discord_webhook(webhook_url)
