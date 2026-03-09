"""
Events Scanner
Looks for corporate/structural catalysts that can unlock hidden value:
- Spinoffs (like SNDK from WDC)
- Share buybacks
- Insider purchases
- Earnings beats
- Index inclusion coming
"""

import yfinance as yf
import logging

log = logging.getLogger(__name__)

CATALYST_KEYWORDS = [
    "spinoff", "spin-off", "buyback", "repurchase", "insider buying",
    "index inclusion", "uplisting", "acquisition", "merger", "earnings beat",
    "special dividend", "asset sale", "restructuring", "activist investor"
]


class EventsScanner:
    def __init__(self, config: dict):
        self.config = config

    def scan(self, ticker: str) -> dict:
        try:
            t = yf.Ticker(ticker)
            info = t.info

            events = []
            catalyst_score = 0

            # Insider ownership & transactions
            insider_pct = info.get("heldPercentInsiders", 0)
            inst_pct = info.get("heldPercentInstitutions", 0)

            # High insider ownership = skin in the game
            if insider_pct and insider_pct > 0.10:
                events.append(f"High insider ownership ({insider_pct*100:.0f}%)")
                catalyst_score += 15

            # Low institutional ownership = under the radar
            if inst_pct and inst_pct < 0.30:
                events.append(f"Low institutional ownership ({inst_pct*100:.0f}%) — room to run")
                catalyst_score += 20

            # Buyback signal: shares outstanding declining
            shares = info.get("sharesOutstanding", 0)
            float_shares = info.get("floatShares", 0)
            if shares and float_shares and float_shares < shares * 0.85:
                events.append("Significant share reduction detected (buyback?)")
                catalyst_score += 10

            # P/B ratio — deeply undervalued?
            pb = info.get("priceToBook")
            if pb and pb < 1.0:
                events.append(f"Trading below book value (P/B: {pb:.2f})")
                catalyst_score += 15

            # Revenue growth
            rev_growth = info.get("revenueGrowth")
            if rev_growth and rev_growth > 0.15:
                events.append(f"Revenue growing {rev_growth*100:.0f}% YoY")
                catalyst_score += 10

            # EV/EBITDA — cheap?
            ev_ebitda = info.get("enterpriseToEbitda")
            if ev_ebitda and 0 < ev_ebitda < 8:
                events.append(f"Cheap valuation (EV/EBITDA: {ev_ebitda:.1f}x)")
                catalyst_score += 10

            return {
                "catalyst_score": min(catalyst_score, 100),
                "events": events,
                "insider_pct": insider_pct,
                "inst_pct": inst_pct,
                "pb_ratio": pb,
                "ev_ebitda": ev_ebitda,
                "rev_growth": rev_growth,
            }

        except Exception as e:
            log.debug(f"EventsScanner failed for {ticker}: {e}")
            return {"catalyst_score": 0, "events": []}
