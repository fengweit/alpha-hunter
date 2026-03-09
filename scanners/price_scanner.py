"""
Price Scanner
Fetches price/volume data and computes core metrics:
- Price vs 52-week low/high
- Volume anomaly vs 30-day average
- Market cap filter
"""

import yfinance as yf
import logging

log = logging.getLogger(__name__)


class PriceScanner:
    def __init__(self, config: dict):
        self.cfg = config["scanner"]
        self.price_min = self.cfg.get("price_min", 1.0)
        self.price_max = self.cfg.get("price_max", 500.0)
        self.mcap_min = self.cfg.get("market_cap_min", 50) * 1_000_000
        self.mcap_max = self.cfg.get("market_cap_max", 10_000) * 1_000_000

    def scan(self, ticker: str) -> dict | None:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            hist = t.history(period="1y")

            if hist.empty or len(hist) < 20:
                return None

            price = info.get("currentPrice") or hist["Close"].iloc[-1]
            market_cap = info.get("marketCap", 0)

            # Apply filters
            if not (self.price_min <= price <= self.price_max):
                return None
            if market_cap and not (self.mcap_min <= market_cap <= self.mcap_max):
                return None

            # 52-week metrics
            high_52w = hist["High"].max()
            low_52w = hist["Low"].min()
            pct_from_high = ((price - high_52w) / high_52w) * 100  # negative = down from high
            pct_from_low = ((price - low_52w) / low_52w) * 100      # how much above low

            # Volume anomaly: today vs 30-day avg
            avg_volume_30d = hist["Volume"].iloc[-31:-1].mean()
            latest_volume = hist["Volume"].iloc[-1]
            volume_ratio = (latest_volume / avg_volume_30d) if avg_volume_30d > 0 else 1.0

            # Short interest (if available)
            short_ratio = info.get("shortRatio", 0)
            short_percent = info.get("shortPercentOfFloat", 0)

            # Recent price momentum (20-day)
            price_20d_ago = hist["Close"].iloc[-21] if len(hist) >= 21 else hist["Close"].iloc[0]
            momentum_20d = ((price - price_20d_ago) / price_20d_ago) * 100

            return {
                "ticker": ticker,
                "price": price,
                "market_cap": market_cap,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "pct_from_high": pct_from_high,
                "pct_from_52w_low": pct_from_low,
                "volume_ratio": volume_ratio,
                "avg_volume_30d": avg_volume_30d,
                "latest_volume": latest_volume,
                "short_ratio": short_ratio,
                "short_percent_float": short_percent,
                "momentum_20d": momentum_20d,
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "name": info.get("shortName", ticker),
            }

        except Exception as e:
            log.debug(f"PriceScanner failed for {ticker}: {e}")
            return None
