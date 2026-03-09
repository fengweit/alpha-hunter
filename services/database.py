"""
Thesis Registry — the persistent brain of Alpha Hunter.
Every thesis lives here. Born, evolves, confirmed, exited.
Nothing is ever deleted — history is everything.
"""

import sqlite3
import json
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "../data/alpha_hunter.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        -- Each thesis is a living investment idea
        CREATE TABLE IF NOT EXISTS theses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            summary     TEXT,
            assets      TEXT,           -- JSON list of tickers
            status      TEXT DEFAULT 'watching',  -- watching|building|confirmed|exited
            conviction  REAL DEFAULT 0,
            position_pct REAL DEFAULT 0,  -- suggested % position size
            born_at     TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            tags        TEXT            -- JSON list: macro, sector, geopolitical, etc.
        );

        -- Every piece of evidence that touches a thesis
        CREATE TABLE IF NOT EXISTS evidence (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            thesis_id   INTEGER REFERENCES theses(id),
            source      TEXT,           -- twitter|reddit|news|price|reasoning
            direction   TEXT,           -- for|against|neutral
            content     TEXT,
            url         TEXT,
            weight      REAL DEFAULT 1.0,
            logged_at   TEXT DEFAULT (datetime('now'))
        );

        -- Conviction score history — the curve over time
        CREATE TABLE IF NOT EXISTS conviction_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            thesis_id   INTEGER REFERENCES theses(id),
            conviction  REAL,
            reasoning   TEXT,
            recorded_at TEXT DEFAULT (datetime('now'))
        );

        -- Raw events from watchers (before reasoning)
        CREATE TABLE IF NOT EXISTS raw_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT,
            content     TEXT,
            url         TEXT,
            author      TEXT,
            processed   INTEGER DEFAULT 0,
            received_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_thesis ON evidence(thesis_id);
        CREATE INDEX IF NOT EXISTS idx_events_processed ON raw_events(processed);
        CREATE INDEX IF NOT EXISTS idx_conviction_thesis ON conviction_history(thesis_id);
    """)
    conn.commit()
    conn.close()


def save_event(source: str, content: str, url: str = "", author: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO raw_events (source, content, url, author) VALUES (?,?,?,?)",
        (source, content, url, author)
    )
    conn.commit()
    conn.close()


def get_unprocessed_events(limit=50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM raw_events WHERE processed=0 ORDER BY received_at ASC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_event_processed(event_id: int):
    conn = get_conn()
    conn.execute("UPDATE raw_events SET processed=1 WHERE id=?", (event_id,))
    conn.commit()
    conn.close()


def upsert_thesis(name: str, summary: str, assets: list, tags: list) -> int:
    conn = get_conn()
    row = conn.execute("SELECT id FROM theses WHERE name=?", (name,)).fetchone()
    if row:
        conn.execute(
            "UPDATE theses SET summary=?, assets=?, tags=?, updated_at=datetime('now') WHERE id=?",
            (summary, json.dumps(assets), json.dumps(tags), row["id"])
        )
        thesis_id = row["id"]
    else:
        cur = conn.execute(
            "INSERT INTO theses (name, summary, assets, tags) VALUES (?,?,?,?)",
            (name, summary, json.dumps(assets), json.dumps(tags))
        )
        thesis_id = cur.lastrowid
    conn.commit()
    conn.close()
    return thesis_id


def add_evidence(thesis_id: int, source: str, direction: str, content: str, url: str = "", weight: float = 1.0):
    conn = get_conn()
    conn.execute(
        "INSERT INTO evidence (thesis_id, source, direction, content, url, weight) VALUES (?,?,?,?,?,?)",
        (thesis_id, source, direction, content, url, weight)
    )
    conn.commit()
    conn.close()


def update_conviction(thesis_id: int, conviction: float, reasoning: str = ""):
    conn = get_conn()
    conn.execute(
        "UPDATE theses SET conviction=?, position_pct=?, updated_at=datetime('now') WHERE id=?",
        (conviction, conviction_to_position(conviction), thesis_id)
    )
    conn.execute(
        "INSERT INTO conviction_history (thesis_id, conviction, reasoning) VALUES (?,?,?)",
        (thesis_id, conviction, reasoning)
    )
    conn.commit()
    conn.close()


def conviction_to_position(conviction: float) -> float:
    """Map conviction score to suggested position size %."""
    if conviction < 20:  return 0
    if conviction < 35:  return 5
    if conviction < 50:  return 15
    if conviction < 65:  return 30
    if conviction < 80:  return 60
    return 85


def get_all_theses():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM theses WHERE status != 'exited' ORDER BY conviction DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_thesis_evidence(thesis_id: int, limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM evidence WHERE thesis_id=? ORDER BY logged_at DESC LIMIT ?",
        (thesis_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_conviction_history(thesis_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT conviction, recorded_at FROM conviction_history WHERE thesis_id=? ORDER BY recorded_at ASC",
        (thesis_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
