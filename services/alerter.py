"""
Alerter — sends Telegram messages when theses cross conviction thresholds.

Alert types:
- 🟡 NEW THESIS BORN (conviction 20-35)
- 🟠 BUILDING CONVICTION (crosses 40, 60)
- 🔴 FULL CONVICTION (crosses 80)
- ⚠️  THESIS WEAKENING (drops 10+ points)
- 🚨 REVERSAL SIGNAL (drops below 30 after being above 60)
"""

import os
import requests
import logging
import json
from services.database import get_all_theses, get_thesis_evidence, get_conviction_history

log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Track last sent conviction to detect changes
_last_conviction = {}


def send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        log.warning("Telegram not configured")
        return
    try:
        requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log.error(f"Telegram send failed: {e}")


def conviction_bar(score: float) -> str:
    bars = int(score / 10)
    return "█" * bars + "░" * (10 - bars)


def format_thesis_alert(thesis: dict, alert_type: str) -> str:
    name = thesis["name"]
    conviction = thesis["conviction"]
    assets = json.loads(thesis.get("assets", "[]"))
    position_pct = thesis["position_pct"]
    summary = thesis.get("summary", "")

    # Get recent evidence
    evidence = get_thesis_evidence(thesis["id"], limit=3)
    evidence_lines = []
    for e in evidence:
        icon = "✅" if e["direction"] == "for" else "❌"
        evidence_lines.append(f"{icon} {e['content'][:120]}")

    bar = conviction_bar(conviction)
    tickers = " ".join([f"${t}" for t in assets]) if assets else "TBD"

    lines = [
        f"{alert_type}",
        f"",
        f"*{name}*",
        f"`{bar}` {conviction:.0f}/100",
        f"",
        f"Assets: {tickers}",
        f"Suggested position: *{position_pct:.0f}%*",
        f"",
        f"_{summary[:200]}_",
        f"",
    ]

    if evidence_lines:
        lines.append("*Recent signals:*")
        lines.extend(evidence_lines)

    return "\n".join(lines)


def check_and_alert(thesis: dict):
    tid = thesis["id"]
    conviction = thesis["conviction"]
    prev = _last_conviction.get(tid, 0)

    # New thesis born
    if prev == 0 and conviction > 0:
        msg = format_thesis_alert(thesis, "🟡 *NEW THESIS BORN*")
        send(msg)
        _last_conviction[tid] = conviction
        return

    delta = conviction - prev

    # Conviction milestones
    for threshold in [40, 60, 80]:
        if prev < threshold <= conviction:
            icons = {40: "🟠", 60: "🔴", 80: "🚀"}
            labels = {40: "BUILDING", 60: "HIGH CONVICTION", 80: "FULL CONVICTION — BUILD POSITION"}
            msg = format_thesis_alert(thesis, f"{icons[threshold]} *{labels[threshold]}*")
            send(msg)
            _last_conviction[tid] = conviction
            return

    # Significant drop — thesis weakening
    if delta <= -10:
        if conviction < 30 and prev >= 60:
            msg = format_thesis_alert(thesis, "🚨 *REVERSAL SIGNAL — consider exiting*")
        else:
            msg = format_thesis_alert(thesis, f"⚠️ *THESIS WEAKENING* ({delta:+.0f} pts)")
        send(msg)

    _last_conviction[tid] = conviction


def send_daily_digest():
    """Morning digest — state of all active theses."""
    theses = get_all_theses()
    if not theses:
        return

    lines = ["📊 *Alpha Hunter Daily Digest*\n"]
    for t in theses:
        assets = json.loads(t.get("assets", "[]"))
        tickers = " ".join([f"${a}" for a in assets]) if assets else "TBD"
        bar = conviction_bar(t["conviction"])
        action = _position_action(t["conviction"])
        lines.append(f"`{bar}` {t['conviction']:.0f} *{t['name']}*")
        lines.append(f"  {tickers} → {action}\n")

    send("\n".join(lines))


def _position_action(conviction: float) -> str:
    if conviction < 20:  return "👀 Watch only"
    if conviction < 35:  return "🪙 Starter position"
    if conviction < 50:  return "➕ Add on dips"
    if conviction < 65:  return "💰 Build meaningful size"
    if conviction < 80:  return "🔥 High conviction — size up"
    return "🚀 Full position — let it run"


def run():
    """Check all theses and send alerts if needed."""
    theses = get_all_theses()
    for t in theses:
        check_and_alert(t)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    send_daily_digest()
