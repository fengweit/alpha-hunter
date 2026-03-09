"""
Twitter/X Watcher
Monitors key accounts and search terms for early thesis signals.
Key sources:
- Trump (@realDonaldTrump) — trade wars, tariffs, geopolitics
- Fed officials — rate signals
- Key fintwit accounts — early thesis formation
- Search terms — "next carvana", "undervalued", "the thesis on X"
"""

import os
import requests
import logging
from urllib.parse import quote
from services.database import save_event

log = logging.getLogger(__name__)

BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# Accounts to monitor (user IDs)
WATCH_ACCOUNTS = {
    "25073877":      "realDonaldTrump",
    "813286":        "BarackObama",    # placeholder — replace with key fintwit
    "1367531".join(["",""]): "federalreserve",
}

# Search queries that signal early thesis formation
SEARCH_QUERIES = [
    "next carvana stock",
    "next nvidia stock undervalued",
    "the thesis on $",
    "down 90% not bankrupt",
    "short squeeze setup",
    "china retaliation trade war",
    "rare earth supply",
    "rate cut housing",
    "spinoff undervalued",
    "hidden gem small cap thesis",
]

MACRO_ACCOUNTS_IDS = [
    "25073877",      # Trump
    "44196397",      # Elon Musk
    "2347049341",    # Fed (placeholder)
]


def _headers():
    token = BEARER_TOKEN
    # URL decode if needed
    token = token.replace("%2F", "/").replace("%3D", "=")
    return {"Authorization": f"Bearer {token}"}


def fetch_user_tweets(user_id: str, username: str, max_results: int = 10) -> int:
    """Fetch recent tweets from a specific account."""
    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    params = {
        "max_results": max_results,
        "tweet.fields": "created_at,text,public_metrics",
        "exclude": "retweets,replies",
    }
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=15)
        if r.status_code == 429:
            log.warning("Twitter rate limited")
            return 0
        if r.status_code != 200:
            log.debug(f"Twitter user fetch error {r.status_code}: {r.text[:200]}")
            return 0

        tweets = r.json().get("data", [])
        count = 0
        for tweet in tweets:
            save_event(
                source="twitter",
                content=f"@{username}: {tweet['text']}",
                url=f"https://twitter.com/{username}/status/{tweet['id']}",
                author=username,
            )
            count += 1
        log.info(f"Twitter @{username}: {count} tweets saved")
        return count

    except Exception as e:
        log.error(f"Twitter fetch failed for {username}: {e}")
        return 0


def search_tweets(query: str, max_results: int = 10) -> int:
    """Search recent tweets matching a query."""
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": f"{query} -is:retweet lang:en",
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "created_at,text,public_metrics,author_id",
    }
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=15)
        if r.status_code == 429:
            log.warning("Twitter rate limited on search")
            return 0
        if r.status_code != 200:
            log.debug(f"Twitter search error {r.status_code}: {r.text[:200]}")
            return 0

        tweets = r.json().get("data", [])
        count = 0
        for tweet in tweets:
            metrics = tweet.get("public_metrics", {})
            engagement = metrics.get("like_count", 0) + metrics.get("retweet_count", 0) * 3
            # Only save tweets with some engagement (filter noise)
            if engagement >= 5:
                save_event(
                    source="twitter_search",
                    content=f"[query:{query}] {tweet['text']} [likes:{metrics.get('like_count',0)} rt:{metrics.get('retweet_count',0)}]",
                    url=f"https://twitter.com/i/web/status/{tweet['id']}",
                    author=tweet.get("author_id", ""),
                )
                count += 1

        log.info(f"Twitter search '{query[:40]}': {count} relevant tweets")
        return count

    except Exception as e:
        log.error(f"Twitter search failed: {e}")
        return 0


def run():
    """Main watcher job — called every 15 minutes."""
    log.info("Twitter watcher running...")
    total = 0

    # Monitor macro accounts
    for user_id, username in WATCH_ACCOUNTS.items():
        total += fetch_user_tweets(user_id, username)

    # Search for early thesis signals
    for query in SEARCH_QUERIES:
        total += search_tweets(query, max_results=15)

    log.info(f"Twitter watcher complete: {total} events saved")
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
