"""
News Watcher
Monitors macro news, Trump statements, Fed signals, geopolitical events.
These are the triggers for top-down thesis generation.
"""

import os
import requests
import logging
import feedparser
from services.database import save_event

log = logging.getLogger(__name__)

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

# RSS feeds for macro news
RSS_FEEDS = {
    "Reuters Markets":      "https://feeds.reuters.com/reuters/businessNews",
    "FT Markets":           "https://www.ft.com/markets?format=rss",
    "Bloomberg Markets":    "https://feeds.bloomberg.com/markets/news.rss",
    "WSJ Markets":          "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "CNBC Markets":         "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "Seeking Alpha":        "https://seekingalpha.com/market_currents.xml",
    "MarketWatch":          "https://feeds.marketwatch.com/marketwatch/topstories/",
    "Zero Hedge":           "https://feeds.feedburner.com/zerohedge/feed",
}

# Macro trigger keywords — events that need to be reasoned about
MACRO_TRIGGERS = [
    "trump", "tariff", "trade war", "sanction",
    "fed", "rate cut", "rate hike", "powell", "fomc",
    "china", "retaliation", "export ban", "import duty",
    "rare earth", "semiconductor", "supply chain",
    "russia", "ukraine", "nato", "defense spending",
    "recession", "inflation", "gdp", "unemployment",
    "opec", "oil production", "energy",
    "dollar", "devaluation", "currency",
    "bank failure", "credit", "liquidity",
    "ai", "artificial intelligence", "compute", "gpu",
    "housing", "mortgage", "rate",
    "spinoff", "merger", "acquisition", "bankruptcy",
]


def fetch_rss_feeds() -> int:
    total = 0
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                combined = (title + " " + summary).lower()

                if any(kw in combined for kw in MACRO_TRIGGERS):
                    save_event(
                        source=f"news:{name}",
                        content=f"{title}\n{summary[:400]}",
                        url=link,
                        author=name,
                    )
                    count += 1

            if count:
                log.info(f"News {name}: {count} macro events")
            total += count

        except Exception as e:
            log.debug(f"RSS failed for {name}: {e}")

    return total


def brave_search_macro() -> int:
    """Active search for breaking macro events."""
    if not BRAVE_API_KEY:
        return 0

    queries = [
        "Trump trade war tariff announcement today",
        "Federal Reserve rate decision statement",
        "China retaliation export controls",
        "rare earth supply shock",
        "geopolitical risk markets",
        "emerging market thesis undervalued",
    ]

    total = 0
    for query in queries:
        try:
            r = requests.get(
                "https://api.search.brave.com/res/v1/news/search",
                headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
                params={"q": query, "count": 5, "freshness": "pd"},
                timeout=10,
            )
            if r.status_code == 200:
                for article in r.json().get("results", []):
                    save_event(
                        source="brave_news",
                        content=f"{article.get('title','')}\n{article.get('description','')}",
                        url=article.get("url", ""),
                        author=article.get("source", {}).get("name", ""),
                    )
                    total += 1
        except Exception as e:
            log.debug(f"Brave search failed: {e}")

    return total


def run():
    """Main watcher job — called every 15 minutes."""
    log.info("News watcher running...")
    total = fetch_rss_feeds() + brave_search_macro()
    log.info(f"News watcher complete: {total} macro events saved")
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
