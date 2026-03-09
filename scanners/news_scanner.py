"""
News Scanner
Uses Brave Search API to find recent news and score sentiment shift.
Key insight: we want to catch the BEGINNING of positive coverage,
not the peak (when it's already priced in).
"""

import requests
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

SENTIMENT_POSITIVE = ["surge", "soar", "rally", "breakout", "beat", "upgrade",
                       "buy", "outperform", "strong", "record", "launch", "win",
                       "partnership", "contract", "acquire", "spinoff", "explosive"]

SENTIMENT_NEGATIVE = ["crash", "plunge", "miss", "downgrade", "sell", "loss",
                       "lawsuit", "fraud", "bankruptcy", "decline", "cut", "weak"]

IGNORED_KEYWORDS = ["nobody", "overlooked", "hidden", "under the radar", "quiet",
                     "unnoticed", "ignored", "sleeper", "unknown"]


class NewsScanner:
    def __init__(self, config: dict):
        self.api_key = config.get("brave", {}).get("api_key", "")
        self.base_url = "https://api.search.brave.com/res/v1/news/search"

    def scan(self, ticker: str) -> dict:
        if not self.api_key:
            return self._empty()

        try:
            # Search for recent news (last 7 days)
            headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
            params = {"q": f"${ticker} stock", "count": 10, "freshness": "pw"}
            r = requests.get(self.base_url, headers=headers, params=params, timeout=10)

            if r.status_code != 200:
                return self._empty()

            articles = r.json().get("results", [])
            if not articles:
                return {"article_count": 0, "sentiment_score": 0, "is_ignored": True, "articles": []}

            # Score sentiment
            pos, neg = 0, 0
            for a in articles:
                text = (a.get("title", "") + " " + a.get("description", "")).lower()
                pos += sum(1 for kw in SENTIMENT_POSITIVE if kw in text)
                neg += sum(1 for kw in SENTIMENT_NEGATIVE if kw in text)

            total = pos + neg
            sentiment_score = ((pos - neg) / total * 100) if total > 0 else 0

            # Low article count = still under the radar (that's what we WANT)
            is_ignored = len(articles) <= 3

            return {
                "article_count": len(articles),
                "sentiment_score": sentiment_score,
                "positive_signals": pos,
                "negative_signals": neg,
                "is_ignored": is_ignored,
                "articles": [{"title": a.get("title"), "url": a.get("url")} for a in articles[:3]],
            }

        except Exception as e:
            log.debug(f"NewsScanner failed for {ticker}: {e}")
            return self._empty()

    def _empty(self):
        return {"article_count": 0, "sentiment_score": 0, "is_ignored": True, "articles": []}
