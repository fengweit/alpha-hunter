"""
Database
SQLite storage for scan history and alert tracking.
Lets us track conviction over time — a rising score over multiple scans
is a stronger signal than a one-time spike.
"""

import sqlite3
import json
import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "data/alpha_hunter.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                score REAL NOT NULL,
                price REAL,
                volume_ratio REAL,
                breakdown TEXT,
                scanned_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                score REAL NOT NULL,
                price REAL,
                thesis TEXT,
                sent_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_scans_ticker ON scans(ticker);
            CREATE INDEX IF NOT EXISTS idx_scans_score ON scans(score DESC);
        """)
        self.conn.commit()

    def save_scan(self, ticker: str, score: float, price_data: dict, breakdown: dict):
        self.conn.execute(
            "INSERT INTO scans (ticker, score, price, volume_ratio, breakdown) VALUES (?, ?, ?, ?, ?)",
            (
                ticker,
                score,
                price_data.get("price"),
                price_data.get("volume_ratio"),
                json.dumps(breakdown),
            ),
        )
        self.conn.commit()

    def save_alert(self, alert: dict):
        pd = alert.get("price_data", {})
        self.conn.execute(
            "INSERT INTO alerts (ticker, score, price, thesis) VALUES (?, ?, ?, ?)",
            (
                alert["ticker"],
                alert["score"],
                pd.get("price"),
                json.dumps(alert.get("breakdown", {})),
            ),
        )
        self.conn.commit()

    def get_score_history(self, ticker: str, days: int = 30) -> list[dict]:
        """Get conviction score trend for a ticker — rising = strengthening setup."""
        rows = self.conn.execute(
            """SELECT score, price, volume_ratio, scanned_at
               FROM scans WHERE ticker = ?
               AND scanned_at >= datetime('now', ?)
               ORDER BY scanned_at ASC""",
            (ticker, f"-{days} days"),
        ).fetchall()
        return [{"score": r[0], "price": r[1], "volume_ratio": r[2], "scanned_at": r[3]} for r in rows]

    def was_alerted_recently(self, ticker: str, hours: int = 24) -> bool:
        """Prevent duplicate alerts within N hours."""
        row = self.conn.execute(
            "SELECT id FROM alerts WHERE ticker = ? AND sent_at >= datetime('now', ?) LIMIT 1",
            (ticker, f"-{hours} hours"),
        ).fetchone()
        return row is not None

    def top_movers(self, limit: int = 10) -> list[dict]:
        """Tickers with the biggest conviction score increase over last 7 days."""
        rows = self.conn.execute(
            """SELECT ticker, MAX(score) - MIN(score) as delta, MAX(score) as peak
               FROM scans
               WHERE scanned_at >= datetime('now', '-7 days')
               GROUP BY ticker
               ORDER BY delta DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [{"ticker": r[0], "score_delta": r[1], "peak_score": r[2]} for r in rows]

    def close(self):
        self.conn.close()
