"""
Alpha Hunter — Database Schema v2
Full signal lifecycle tracking:
  raw news → LLM scoring → signals → thesis conviction → trading opportunities
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
    conn.execute("PRAGMA journal_mode=WAL")   # concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""

    -- ─────────────────────────────────────────────
    --  LAYER 1: RAW INPUTS
    -- ─────────────────────────────────────────────

    -- Every news article/post the system reads
    CREATE TABLE IF NOT EXISTS news_articles (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        title           TEXT,
        url             TEXT UNIQUE,          -- deduplicate by URL
        source          TEXT,                 -- reuters.com, reddit.com, etc.
        outlet          TEXT,                 -- "FT Markets", "WSB", "Brave Search"
        author          TEXT,
        published_at    TEXT,
        fetched_at      TEXT DEFAULT (datetime('now')),
        content         TEXT,                 -- full text / summary from feed
        llm_summary     TEXT,                 -- LLM-generated 1-sentence summary
        relevance_score REAL DEFAULT 0,       -- 0-100: how relevant to ANY active thesis
        processed       INTEGER DEFAULT 0     -- 0=raw, 1=LLM scored
    );

    -- ─────────────────────────────────────────────
    --  LAYER 2: LLM SCORING
    -- ─────────────────────────────────────────────

    -- LLM analysis of each article against each thesis
    CREATE TABLE IF NOT EXISTS article_scores (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id      INTEGER REFERENCES news_articles(id),
        thesis_id       INTEGER REFERENCES theses(id),
        relevance       REAL,                 -- 0-100: how much does this article affect this thesis
        direction       TEXT,                 -- for | against | neutral
        reasoning       TEXT,                 -- LLM 1-sentence explanation
        conviction_delta REAL DEFAULT 0,      -- suggested conviction change
        scored_at       TEXT DEFAULT (datetime('now'))
    );

    -- ─────────────────────────────────────────────
    --  LAYER 3: SIGNALS
    -- ─────────────────────────────────────────────

    -- Detected signals — discrete moments when something becomes notable
    CREATE TABLE IF NOT EXISTS signals (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        thesis_id       INTEGER REFERENCES theses(id),
        article_id      INTEGER REFERENCES news_articles(id),   -- what triggered it (nullable)
        signal_type     TEXT,                 -- news | social | price | macro | pattern
        trigger_desc    TEXT,                 -- human-readable: "Volume spike 4.2x on $SNDK"
        direction       TEXT,                 -- for | against | neutral
        strength        TEXT,                 -- weak | moderate | strong | critical
        strength_score  REAL,                 -- 0-100
        url             TEXT,                 -- direct link to source
        detected_at     TEXT DEFAULT (datetime('now'))
    );

    -- ─────────────────────────────────────────────
    --  LAYER 4: THESES (core)
    -- ─────────────────────────────────────────────

    CREATE TABLE IF NOT EXISTS theses (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        summary         TEXT,
        assets          TEXT,                 -- JSON list of tickers
        status          TEXT DEFAULT 'watching', -- watching|building|confirmed|opportunity|exited
        conviction      REAL DEFAULT 0,
        position_pct    REAL DEFAULT 0,
        born_at         TEXT DEFAULT (datetime('now')),
        first_signal_at TEXT,                 -- when was the FIRST signal ever detected
        first_signal_id INTEGER REFERENCES signals(id),
        opportunity_at  TEXT,                 -- when did it cross into "trade it" territory
        updated_at      TEXT DEFAULT (datetime('now')),
        tags            TEXT,                 -- JSON list
        exit_reason     TEXT                  -- why was this thesis closed
    );

    -- Full audit trail of every conviction change
    CREATE TABLE IF NOT EXISTS conviction_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        thesis_id       INTEGER REFERENCES theses(id),
        conviction_before REAL,
        conviction_after  REAL,
        delta           REAL,
        trigger_type    TEXT,                 -- news | signal | manual | price
        trigger_id      INTEGER,              -- signal_id or article_id that caused this
        reasoning       TEXT,
        recorded_at     TEXT DEFAULT (datetime('now'))
    );

    -- Every thesis lifecycle event (born, signal, milestone, exit)
    CREATE TABLE IF NOT EXISTS thesis_timeline (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        thesis_id       INTEGER REFERENCES theses(id),
        event_type      TEXT,                 -- born|signal|conviction_up|conviction_down|milestone|opportunity|exited
        title           TEXT,                 -- short label: "First signal detected"
        description     TEXT,                 -- full description
        conviction_at   REAL,                 -- conviction score at this moment
        signal_id       INTEGER REFERENCES signals(id),
        article_id      INTEGER REFERENCES news_articles(id),
        metadata        TEXT,                 -- JSON extra data
        happened_at     TEXT DEFAULT (datetime('now'))
    );

    -- ─────────────────────────────────────────────
    --  LAYER 5: EVIDENCE (links signal → thesis)
    -- ─────────────────────────────────────────────

    CREATE TABLE IF NOT EXISTS evidence (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        thesis_id       INTEGER REFERENCES theses(id),
        signal_id       INTEGER REFERENCES signals(id),       -- which signal generated this
        article_id      INTEGER REFERENCES news_articles(id), -- source article
        source          TEXT,
        direction       TEXT,                 -- for | against | neutral
        content         TEXT,
        url             TEXT,
        weight          REAL DEFAULT 1.0,
        logged_at       TEXT DEFAULT (datetime('now'))
    );

    -- ─────────────────────────────────────────────
    --  LAYER 6: TRADING OPPORTUNITIES
    -- ─────────────────────────────────────────────

    CREATE TABLE IF NOT EXISTS trading_opportunities (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        thesis_id       INTEGER REFERENCES theses(id),
        assets          TEXT,                 -- JSON: tickers to trade
        conviction      REAL,                 -- conviction score when triggered
        entry_zone      TEXT,                 -- e.g. "$4.50–$5.00"
        position_size   REAL,                 -- suggested % of portfolio
        thesis_summary  TEXT,                 -- the thesis at time of trigger
        catalyst        TEXT,                 -- what pushed it over the threshold
        risk_factors    TEXT,                 -- what would break the thesis
        status          TEXT DEFAULT 'active', -- active | exited | expired
        triggered_at    TEXT DEFAULT (datetime('now')),
        exited_at       TEXT,
        exit_notes      TEXT
    );

    -- ─────────────────────────────────────────────
    --  INDEXES
    -- ─────────────────────────────────────────────

    CREATE INDEX IF NOT EXISTS idx_articles_processed   ON news_articles(processed);
    CREATE INDEX IF NOT EXISTS idx_articles_relevance   ON news_articles(relevance_score DESC);
    CREATE INDEX IF NOT EXISTS idx_scores_article       ON article_scores(article_id);
    CREATE INDEX IF NOT EXISTS idx_scores_thesis        ON article_scores(thesis_id);
    CREATE INDEX IF NOT EXISTS idx_signals_thesis       ON signals(thesis_id);
    CREATE INDEX IF NOT EXISTS idx_signals_time         ON signals(detected_at DESC);
    CREATE INDEX IF NOT EXISTS idx_evidence_thesis      ON evidence(thesis_id);
    CREATE INDEX IF NOT EXISTS idx_conviction_thesis    ON conviction_history(thesis_id);
    CREATE INDEX IF NOT EXISTS idx_timeline_thesis      ON thesis_timeline(thesis_id);
    CREATE INDEX IF NOT EXISTS idx_timeline_time        ON thesis_timeline(happened_at DESC);
    CREATE INDEX IF NOT EXISTS idx_opps_status          ON trading_opportunities(status);

    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  NEWS ARTICLES
# ─────────────────────────────────────────────

def save_article(title: str, url: str, source: str, outlet: str,
                 content: str, author: str = "", published_at: str = ""):
    """Save a news article, deduplicating by URL. Returns article_id or None if duplicate."""
    if not url:
        return None
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO news_articles
               (title, url, source, outlet, author, published_at, content)
               VALUES (?,?,?,?,?,?,?)""",
            (title, url, source, outlet, author, published_at, content)
        )
        conn.commit()
        if cur.rowcount == 0:
            return None  # duplicate
        return cur.lastrowid
    except Exception:
        return None
    finally:
        conn.close()


def get_unscored_articles(limit=20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM news_articles WHERE processed=0 ORDER BY fetched_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_article_scored(article_id: int, relevance_score: float, llm_summary: str = ""):
    conn = get_conn()
    conn.execute(
        "UPDATE news_articles SET processed=1, relevance_score=?, llm_summary=? WHERE id=?",
        (relevance_score, llm_summary, article_id)
    )
    conn.commit()
    conn.close()


def save_article_score(article_id: int, thesis_id: int, relevance: float,
                       direction: str, reasoning: str, conviction_delta: float):
    conn = get_conn()
    conn.execute(
        """INSERT INTO article_scores
           (article_id, thesis_id, relevance, direction, reasoning, conviction_delta)
           VALUES (?,?,?,?,?,?)""",
        (article_id, thesis_id, relevance, direction, reasoning, conviction_delta)
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  SIGNALS
# ─────────────────────────────────────────────

def create_signal(thesis_id: int, signal_type: str, trigger_desc: str,
                  direction: str, strength: str, strength_score: float,
                  url: str = "", article_id: int = None):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO signals
           (thesis_id, article_id, signal_type, trigger_desc, direction, strength, strength_score, url)
           VALUES (?,?,?,?,?,?,?,?)""",
        (thesis_id, article_id, signal_type, trigger_desc, direction, strength, strength_score, url)
    )
    signal_id = cur.lastrowid

    # Update thesis first_signal_at if this is the first
    conn.execute(
        """UPDATE theses SET first_signal_at=COALESCE(first_signal_at, datetime('now')),
           first_signal_id=COALESCE(first_signal_id, ?)
           WHERE id=?""",
        (signal_id, thesis_id)
    )
    conn.commit()
    conn.close()
    return signal_id


def get_signals(thesis_id: int = None, limit: int = 20) -> list[dict]:
    conn = get_conn()
    if thesis_id:
        rows = conn.execute(
            "SELECT * FROM signals WHERE thesis_id=? ORDER BY detected_at DESC LIMIT ?",
            (thesis_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY detected_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  THESES
# ─────────────────────────────────────────────

def upsert_thesis(name: str, summary: str, assets: list, tags: list):
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
        # Log birth event
        conn.execute(
            """INSERT INTO thesis_timeline (thesis_id, event_type, title, description, conviction_at)
               VALUES (?,?,?,?,?)""",
            (thesis_id, "born", "Thesis Born", summary[:300] if summary else "", 0)
        )
    conn.commit()
    conn.close()
    return thesis_id


def update_conviction(thesis_id: int, conviction: float, reasoning: str = "",
                      trigger_type: str = "news", trigger_id: int = None,
                      signal_id: int = None):
    conn = get_conn()
    current = conn.execute("SELECT conviction FROM theses WHERE id=?", (thesis_id,)).fetchone()
    before = current["conviction"] if current else 0
    delta = conviction - before
    pos_pct = conviction_to_position(conviction)

    conn.execute(
        """UPDATE theses SET conviction=?, position_pct=?, updated_at=datetime('now'),
           status=CASE
             WHEN ? >= 80 THEN 'confirmed'
             WHEN ? >= 65 THEN 'opportunity'
             WHEN ? >= 35 THEN 'building'
             ELSE 'watching'
           END
           WHERE id=?""",
        (conviction, pos_pct, conviction, conviction, conviction, thesis_id)
    )

    conn.execute(
        """INSERT INTO conviction_history
           (thesis_id, conviction_before, conviction_after, delta, trigger_type, trigger_id, reasoning)
           VALUES (?,?,?,?,?,?,?)""",
        (thesis_id, before, conviction, delta, trigger_type, trigger_id, reasoning)
    )

    # Log milestone events to timeline
    milestone = None
    if before < 35 <= conviction:  milestone = ("milestone", "🟡 Building Conviction", f"Crossed 35 — {reasoning[:150]}")
    elif before < 65 <= conviction: milestone = ("milestone", "🟠 High Conviction",    f"Crossed 65 — {reasoning[:150]}")
    elif before < 80 <= conviction: milestone = ("milestone", "🔴 Full Conviction",    f"Crossed 80 — {reasoning[:150]}")
    elif before >= 65 > conviction: milestone = ("milestone", "⚠️ Thesis Weakening",   f"Dropped below 65 — {reasoning[:150]}")

    if milestone:
        conn.execute(
            """INSERT INTO thesis_timeline
               (thesis_id, event_type, title, description, conviction_at, signal_id)
               VALUES (?,?,?,?,?,?)""",
            (thesis_id, milestone[0], milestone[1], milestone[2], conviction, signal_id)
        )

        # Create trading opportunity record when crossing 65
        if "High Conviction" in (milestone[1] if milestone else ""):
            assets = conn.execute("SELECT assets FROM theses WHERE id=?", (thesis_id,)).fetchone()
            conn.execute(
                """INSERT OR IGNORE INTO trading_opportunities
                   (thesis_id, assets, conviction, thesis_summary, catalyst)
                   VALUES (?,?,?,?,?)""",
                (thesis_id, assets["assets"] if assets else "[]", conviction,
                 reasoning[:300], f"Conviction crossed 65 threshold")
            )

    conn.commit()
    conn.close()


def add_evidence(thesis_id: int, source: str, direction: str, content: str,
                 url: str = "", weight: float = 1.0,
                 signal_id: int = None, article_id: int = None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO evidence
           (thesis_id, signal_id, article_id, source, direction, content, url, weight)
           VALUES (?,?,?,?,?,?,?,?)""",
        (thesis_id, signal_id, article_id, source, direction, content, url, weight)
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  RAW EVENTS (legacy — kept for watcher compat)
# ─────────────────────────────────────────────

def save_event(source: str, content: str, url: str = "", author: str = ""):
    """Save raw event AND try to save as structured news article."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO raw_events (source, content, url, author) VALUES (?,?,?,?)",
        (source, content, url, author)
    )
    conn.commit()
    conn.close()

    # Also persist as news article if we have a URL
    if url:
        title = content.split('\n')[0][:200]
        outlet = source.replace('news:', '').replace('brave_news', 'Brave Search')
        save_article(
            title=title, url=url, source=source, outlet=outlet,
            content=content, author=author
        )


def get_unprocessed_events(limit=10) -> list[dict]:
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


# ─────────────────────────────────────────────
#  QUERIES
# ─────────────────────────────────────────────

def get_all_theses() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM theses WHERE status != 'exited' ORDER BY conviction DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_thesis_evidence(thesis_id: int, limit=20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT e.*, a.url as article_url, a.title as article_title
           FROM evidence e
           LEFT JOIN news_articles a ON e.article_id = a.id
           WHERE e.thesis_id=? ORDER BY e.logged_at DESC LIMIT ?""",
        (thesis_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_thesis_timeline(thesis_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT t.*, s.trigger_desc as signal_desc, s.url as signal_url
           FROM thesis_timeline t
           LEFT JOIN signals s ON t.signal_id = s.id
           WHERE t.thesis_id=? ORDER BY t.happened_at ASC""",
        (thesis_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trading_opportunities(status: str = "active") -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT o.*, t.name as thesis_name, t.conviction as current_conviction
           FROM trading_opportunities o
           JOIN theses t ON o.thesis_id = t.id
           WHERE o.status=? ORDER BY o.triggered_at DESC""",
        (status,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_articles(limit=50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM news_articles
           WHERE url != '' ORDER BY fetched_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def conviction_to_position(conviction: float) -> float:
    if conviction < 20:  return 0
    if conviction < 35:  return 5
    if conviction < 50:  return 15
    if conviction < 65:  return 30
    if conviction < 80:  return 60
    return 85


# ─────────────────────────────────────────────
#  LEGACY TABLE (keep for raw_events compat)
# ─────────────────────────────────────────────

def _ensure_raw_events_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT,
            content     TEXT,
            url         TEXT,
            author      TEXT,
            processed   INTEGER DEFAULT 0,
            received_at TEXT DEFAULT (datetime('now'))
        )
    """)


def get_conviction_history(thesis_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        """SELECT conviction_after as conviction, recorded_at
           FROM conviction_history WHERE thesis_id=? ORDER BY recorded_at ASC""",
        (thesis_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
