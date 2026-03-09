#!/usr/bin/env python3
"""
Alpha Hunter — 24/7 Runner
Runs all watchers and the reasoning engine on a continuous schedule.
Designed to run as a macOS LaunchAgent.
"""

import os
import time
import logging
import schedule
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from services.database import init_db
from services.watcher_twitter import run as twitter_run
from services.watcher_reddit import run as reddit_run
from services.watcher_news import run as news_run
from services.deep_reasoner import run as reasoner_run
from services.alerter import run as alerter_run, send_daily_digest

# Logging setup
LOG_DIR = "/tmp/alpha-hunter"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/runner.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("alpha-hunter")


def safe_run(name: str, fn):
    """Run a job safely — log errors but never crash the runner."""
    try:
        log.info(f"▶ {name}")
        fn()
        log.info(f"✓ {name}")
    except Exception as e:
        log.error(f"✗ {name} failed: {e}", exc_info=True)


def watch_cycle():
    """Collect signals from all sources."""
    safe_run("News watcher", news_run)
    safe_run("Twitter watcher", twitter_run)


def think_cycle():
    """Process collected events through Claude reasoning engine."""
    safe_run("Reasoning engine", reasoner_run)
    safe_run("Alert checker", alerter_run)


def reddit_cycle():
    """Reddit runs less frequently to respect rate limits."""
    safe_run("Reddit watcher", reddit_run)


def morning_digest():
    """Daily digest at market open."""
    safe_run("Daily digest", send_daily_digest)


def setup_schedule():
    # Watch: every 15 minutes
    schedule.every(15).minutes.do(watch_cycle)

    # Reddit: every 30 minutes
    schedule.every(30).minutes.do(reddit_cycle)

    # Reason: every 20 minutes (after watchers have had time to collect)
    schedule.every(20).minutes.do(think_cycle)

    # Daily digest: 6:30 AM PT (market pre-open)
    schedule.every().day.at("06:30").do(morning_digest)

    log.info("Schedule configured:")
    log.info("  - News + Twitter: every 15 min")
    log.info("  - Reddit: every 30 min")
    log.info("  - Reasoning + Alerts: every 20 min")
    log.info("  - Daily digest: 06:30 PT")


def main():
    log.info("=" * 60)
    log.info("  Alpha Hunter starting up")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    # Initialize database
    init_db()
    log.info("Database initialized")

    # Run everything once immediately on startup
    safe_run("Initial watch cycle", watch_cycle)
    safe_run("Initial Reddit scan", reddit_cycle)
    safe_run("Initial reasoning", think_cycle)

    # Set up recurring schedule
    setup_schedule()

    log.info("Running 24/7... (logs: /tmp/alpha-hunter/runner.log)")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
