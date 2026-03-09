"""
Reddit Watcher
Monitors WSB, r/investing, r/stocks, r/SecurityAnalysis for early thesis posts.
Looking for the pattern: "X is the next Y" at beaten-down prices.
"""

import requests
import logging
from services.database import save_event

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "AlphaHunter/1.0 (thesis research bot)"}

# Subreddits to monitor
SUBREDDITS = [
    "wallstreetbets",
    "investing",
    "stocks",
    "SecurityAnalysis",
    "ValueInvesting",
    "StockMarket",
    "options",
]

# Title patterns that signal an early thesis (same pattern as OPEN/Carvana post)
THESIS_PATTERNS = [
    "is the next",
    "next carvana",
    "next nvidia",
    "down 9",          # "down 90%", "down 95%", "down 98%"
    "not going bankrupt",
    "far from bankrupt",
    "the thesis",
    "undervalued",
    "hidden gem",
    "nobody is talking about",
    "sleeping giant",
    "short squeeze",
    "squeeze setup",
    "spinoff",
    "spin-off",
    "macro play",
    "trade war play",
    "china retaliation",
    "rare earth",
    "rate cut play",
    "turnaround play",
    "putting my",       # "putting my $X into..."
    "going all in",
    "this will 10x",
    "technical analysis",
]

# Minimum upvotes to consider a post signal
MIN_UPVOTES = 50


def fetch_subreddit_hot(subreddit: str, limit: int = 25) -> int:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            log.debug(f"Reddit {subreddit} error: {r.status_code}")
            return 0

        posts = r.json().get("data", {}).get("children", [])
        count = 0
        for post in posts:
            data = post["data"]
            title = data.get("title", "").lower()
            score = data.get("score", 0)
            text = data.get("selftext", "")

            # Check if title matches any thesis pattern
            if any(p in title for p in THESIS_PATTERNS) and score >= MIN_UPVOTES:
                content = f"[r/{subreddit}] {data['title']}\n\n{text[:500]}\n\nScore: {score} | Comments: {data.get('num_comments',0)}"
                save_event(
                    source="reddit",
                    content=content,
                    url=f"https://reddit.com{data.get('permalink','')}",
                    author=data.get("author", ""),
                )
                count += 1

        log.info(f"Reddit r/{subreddit}: {count} thesis posts found")
        return count

    except Exception as e:
        log.error(f"Reddit fetch failed for r/{subreddit}: {e}")
        return 0


def fetch_subreddit_new(subreddit: str, limit: int = 25) -> int:
    """Also check new posts — catch things before they get upvotes."""
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return 0

        posts = r.json().get("data", {}).get("children", [])
        count = 0
        for post in posts:
            data = post["data"]
            title = data.get("title", "").lower()
            text = data.get("selftext", "").lower()
            combined = title + " " + text

            # Lower bar for new posts — catch them early
            pattern_matches = sum(1 for p in THESIS_PATTERNS if p in combined)
            if pattern_matches >= 2:  # Must match at least 2 patterns
                content = f"[r/{subreddit}/new] {data['title']}\n\n{data.get('selftext','')[:400]}"
                save_event(
                    source="reddit_new",
                    content=content,
                    url=f"https://reddit.com{data.get('permalink','')}",
                    author=data.get("author", ""),
                )
                count += 1

        return count

    except Exception as e:
        log.error(f"Reddit new fetch failed for r/{subreddit}: {e}")
        return 0


def run():
    """Main watcher job — called every 30 minutes."""
    log.info("Reddit watcher running...")
    total = 0
    for sub in SUBREDDITS:
        total += fetch_subreddit_hot(sub)
        total += fetch_subreddit_new(sub, limit=15)

    log.info(f"Reddit watcher complete: {total} thesis signals saved")
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
