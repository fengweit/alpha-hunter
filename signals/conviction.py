"""
Conviction Engine
The brain of Alpha Hunter.

Combines all signals into a single conviction score (0-100).
Higher = more confident this is a pre-explosion setup.

Key criteria (the "SNDK pattern"):
  1. Cheap vs history (near 52w low or beaten down)
  2. Volume quietly building (smart money entering)
  3. Nobody talking about it yet (low news count)
  4. Structural catalyst exists (spinoff, buyback, etc.)
  5. Short squeeze potential (high short interest)
"""

import logging

log = logging.getLogger(__name__)


class ConvictionEngine:
    def __init__(self, signal_weights: dict):
        self.weights = signal_weights

    def score(self, ticker: str, price_data: dict, news_data: dict, events_data: dict) -> tuple[float, dict]:
        breakdown = {}

        # ── 1. Price vs 52-week low ────────────────────────────────────────
        # We want cheap — ideally within 50% of the 52w low
        # (not AT the low, which could signal distress — just beaten down)
        pct_from_low = price_data.get("pct_from_52w_low", 999)
        pct_from_high = price_data.get("pct_from_high", 0)

        if 0 <= pct_from_low <= 30:
            price_score = 100   # Very close to 52w low — deep value zone
        elif 30 < pct_from_low <= 60:
            price_score = 75
        elif 60 < pct_from_low <= 100:
            price_score = 40
        else:
            price_score = 10   # Too far from low = already ran

        breakdown["price_vs_52w_low"] = price_score * (self.weights.get("price_vs_52w_low", 20) / 100)

        # ── 2. Volume anomaly ──────────────────────────────────────────────
        # Big volume spike on a quiet stock = somebody knows something
        vol_ratio = price_data.get("volume_ratio", 1.0)

        if vol_ratio >= 5.0:
            vol_score = 100   # 5x normal volume — major signal
        elif vol_ratio >= 3.0:
            vol_score = 80
        elif vol_ratio >= 2.0:
            vol_score = 60
        elif vol_ratio >= 1.5:
            vol_score = 35
        else:
            vol_score = 10

        breakdown["volume_anomaly"] = vol_score * (self.weights.get("volume_anomaly", 25) / 100)

        # ── 3. Short interest (squeeze setup) ─────────────────────────────
        short_pct = price_data.get("short_percent_float", 0) or 0
        if isinstance(short_pct, float) and short_pct > 1:
            short_pct /= 100  # normalize if given as percentage

        if short_pct >= 0.25:
            short_score = 100  # >25% short float = massive squeeze potential
        elif short_pct >= 0.15:
            short_score = 70
        elif short_pct >= 0.08:
            short_score = 40
        else:
            short_score = 10

        breakdown["short_interest"] = short_score * (self.weights.get("short_interest", 15) / 100)

        # ── 4. Insider/fundamental catalyst ───────────────────────────────
        catalyst_score = events_data.get("catalyst_score", 0)
        breakdown["insider_activity"] = catalyst_score * (self.weights.get("insider_activity", 20) / 100)

        # ── 5. News sentiment (turning positive, still low coverage) ──────
        article_count = news_data.get("article_count", 0)
        sentiment = news_data.get("sentiment_score", 0)
        is_ignored = news_data.get("is_ignored", True)

        # Ideal: low coverage + positive sentiment = early in the narrative
        if is_ignored and sentiment >= 0:
            news_score = 80   # Under radar + no bad news
        elif is_ignored and sentiment < 0:
            news_score = 30   # Under radar but bad news exists
        elif not is_ignored and sentiment > 30:
            news_score = 50   # Getting attention + positive (may be late)
        elif not is_ignored and sentiment < 0:
            news_score = 5    # In the news for bad reasons
        else:
            news_score = 30

        breakdown["news_sentiment"] = news_score * (self.weights.get("news_sentiment", 10) / 100)

        # ── 6. Social momentum ────────────────────────────────────────────
        # Proxy: article count acceleration (low now = early stage)
        # TODO: wire up Reddit/Twitter API for real social data
        social_score = 50 if is_ignored else 20  # Placeholder
        breakdown["social_momentum"] = social_score * (self.weights.get("social_momentum", 10) / 100)

        # ── Final score ───────────────────────────────────────────────────
        total = sum(breakdown.values())
        total = min(max(total, 0), 100)

        log.debug(f"{ticker} conviction: {total:.1f} | {breakdown}")
        return total, breakdown
