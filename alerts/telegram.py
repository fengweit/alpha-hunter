"""
Telegram Alerter
Sends conviction alerts directly to your Telegram chat.
Format is designed to give you all the info needed to make a quick decision.
"""

import requests
import logging
from datetime import datetime

log = logging.getLogger(__name__)


class TelegramAlerter:
    def __init__(self, config: dict):
        self.bot_token = config.get("bot_token", "")
        self.chat_id = config.get("chat_id", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send(self, alert: dict) -> bool:
        if not self.bot_token or not self.chat_id:
            log.warning("Telegram not configured — skipping alert")
            return False

        message = self._format_alert(alert)
        try:
            r = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=10,
            )
            if r.status_code == 200:
                log.info(f"Alert sent for {alert['ticker']}")
                return True
            else:
                log.error(f"Telegram error: {r.status_code} {r.text}")
                return False
        except Exception as e:
            log.error(f"Failed to send Telegram alert: {e}")
            return False

    def _format_alert(self, alert: dict) -> str:
        pd = alert["price_data"]
        nd = alert["news_data"]
        ed = alert["events_data"]
        score = alert["score"]
        ticker = alert["ticker"]
        name = pd.get("name", ticker)

        # Conviction bar
        bars = int(score / 10)
        bar = "█" * bars + "░" * (10 - bars)

        lines = [
            f"🎯 *ALPHA HUNTER ALERT*",
            f"",
            f"*${ticker}* — {name}",
            f"Conviction: `{bar}` {score:.0f}/100",
            f"",
            f"💰 Price: *${pd.get('price', 0):.2f}*",
            f"📉 From 52w high: {pd.get('pct_from_high', 0):.0f}%",
            f"📈 From 52w low: +{pd.get('pct_from_52w_low', 0):.0f}%",
            f"📊 Volume spike: *{pd.get('volume_ratio', 0):.1f}x* normal",
            f"",
            f"*Why this, why now:*",
        ]

        # Add signal bullets
        bullets = []
        bd = alert.get("breakdown", {})

        if pd.get("pct_from_52w_low", 999) <= 50:
            bullets.append(f"✅ Deep value — near 52w low, room to run")
        if pd.get("volume_ratio", 0) >= 2:
            bullets.append(f"✅ Volume {pd['volume_ratio']:.1f}x — someone is accumulating")
        if pd.get("short_percent_float", 0) and pd["short_percent_float"] > 0.10:
            bullets.append(f"✅ Short float {pd['short_percent_float']*100:.0f}% — squeeze potential")
        if nd.get("is_ignored"):
            bullets.append(f"✅ Still under the radar — low media coverage")
        if nd.get("sentiment_score", 0) > 20:
            bullets.append(f"✅ News sentiment turning positive")
        for event in ed.get("events", [])[:3]:
            bullets.append(f"✅ {event}")

        if not bullets:
            bullets.append("📊 Multi-signal convergence detected")

        lines.extend(bullets)
        lines.extend([
            f"",
            f"*Sector:* {pd.get('sector', '—')} / {pd.get('industry', '—')}",
            f"*Market Cap:* ${pd.get('market_cap', 0)/1e6:.0f}M",
            f"",
            f"⚡ Add on dips. Wait for explosion.",
            f"",
            f"_Alpha Hunter • {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        ])

        return "\n".join(lines)

    def send_summary(self, candidates: list, threshold: int) -> bool:
        """Send a daily summary of top candidates even below threshold."""
        if not candidates:
            return False

        top = candidates[:5]
        lines = [
            f"📊 *Alpha Hunter Daily Scan*",
            f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_",
            f"",
            f"Top candidates today (threshold: {threshold}):",
            f"",
        ]

        for c in top:
            pd = c["price_data"]
            emoji = "🔥" if c["score"] >= threshold else "👀"
            lines.append(
                f"{emoji} *${c['ticker']}* — {c['score']:.0f}/100 | "
                f"${pd.get('price', 0):.2f} | "
                f"Vol {pd.get('volume_ratio', 0):.1f}x"
            )

        message = "\n".join(lines)
        try:
            r = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False
