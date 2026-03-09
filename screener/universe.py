"""
Universe Loader
Defines what assets Alpha Hunter scans.
Small/mid cap is the sweet spot — big caps are too covered, penny stocks are noise.
"""

import logging

log = logging.getLogger(__name__)

# Curated watchlists — add your own suspects here
COMMODITY_TICKERS = [
    "GLD", "SLV", "PPLT", "PALL",       # Gold, Silver, Platinum, Palladium ETFs
    "USO", "BNO", "UNG",                  # Oil, Brent, Natural Gas
    "CPER", "JJC",                        # Copper
    "DBA", "WEAT", "CORN",               # Agriculture
    "URA", "NLR",                         # Uranium
]

CRYPTO_PROXY_TICKERS = [
    "MSTR", "COIN", "MARA", "RIOT",      # BTC proxies
    "BITF", "HUT",                        # Miners
]

SMALL_CAP_WATCHLIST = [
    # Add names you're watching — spinoffs, beaten-down names, etc.
    "SNDK", "WDC",
]

# S&P 500 small constituent sample (expand as needed)
SP500_SAMPLE = [
    "AAL", "ALK", "UAL", "DAL",          # Airlines — cyclical beats
    "X", "CLF", "NUE", "STLD",          # Steel
    "FCX", "SCCO", "HBM",               # Copper miners
    "AG", "PAAS", "SILV", "SVM",        # Silver miners
    "AEM", "KGC", "EGO",                 # Gold miners
    "UUUU", "EU", "DNN", "CCJ",         # Uranium
    "MP", "LTHM", "LAC", "PLL",         # Rare earth / Lithium
]


class UniverseLoader:
    def __init__(self, config: dict):
        self.config = config
        self.universe_types = config.get("universe", ["sp500", "commodities"])

    def load(self) -> list[str]:
        tickers = set()

        for u in self.universe_types:
            if u == "commodities":
                tickers.update(COMMODITY_TICKERS)
            elif u == "crypto":
                tickers.update(CRYPTO_PROXY_TICKERS)
            elif u == "watchlist":
                tickers.update(SMALL_CAP_WATCHLIST)
            elif u in ("sp500", "russell2000"):
                tickers.update(self._load_index(u))

        # Always include the curated small-cap watchlist
        tickers.update(SMALL_CAP_WATCHLIST)
        tickers.update(SP500_SAMPLE)

        log.info(f"Universe loaded: {len(tickers)} tickers")
        return list(tickers)

    def _load_index(self, index: str) -> list[str]:
        """Fetch index constituents (uses Wikipedia for S&P 500)."""
        try:
            import pandas as pd
            if index == "sp500":
                tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
                return tables[0]["Symbol"].tolist()
            # Russell 2000 — too large, use a sample
            return SP500_SAMPLE
        except Exception as e:
            log.warning(f"Could not load {index} from Wikipedia: {e}")
            return SP500_SAMPLE
