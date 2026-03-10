"""
Themed Plays Database
Separate from the thesis intelligence DB.
This is the trading journal — what you actually hold, at what price,
why you entered, how the theme evolved, and what you made.

Structure:
  themes      → the macro theme (Rare Earth, iBuying, Korea Index...)
  positions   → individual tickers held within a theme
  theme_events → every meaningful action (entry, add, trim, exit, catalyst)
  price_history → regular price snapshots for open positions
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/plays.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""

    -- ─── THEMES ───────────────────────────────────────────────
    -- The macro thesis that ties multiple positions together
    CREATE TABLE IF NOT EXISTS themes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,          -- "Rare Earth Supply Crunch"
        description     TEXT,                   -- what the theme is about
        layer_a         TEXT,                   -- the macro trigger (A)
        layer_b         TEXT,                   -- consensus play (skip)
        layer_c         TEXT,                   -- the actual edge (C)
        status          TEXT DEFAULT 'watching', -- watching|building|active|exiting|closed
        conviction      REAL DEFAULT 0,         -- 0-100, updated manually or by signals
        linked_thesis_id INTEGER,               -- optional link to alpha_hunter theses table
        created_at      TEXT DEFAULT (datetime('now')),
        activated_at    TEXT,                   -- when first position taken
        peak_conviction REAL DEFAULT 0,
        peak_at         TEXT,
        closed_at       TEXT,
        close_reason    TEXT,                   -- "thesis confirmed + exited", "thesis broken"
        notes           TEXT
    );

    -- ─── POSITIONS ───────────────────────────────────────────
    -- Individual ticker positions within a theme
    CREATE TABLE IF NOT EXISTS positions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        theme_id        INTEGER REFERENCES themes(id),
        ticker          TEXT NOT NULL,
        name            TEXT,                   -- company name
        layer           TEXT DEFAULT 'C',       -- which layer: A | B | C (should almost always be C)
        status          TEXT DEFAULT 'open',    -- open | partial | closed

        -- Entry
        avg_entry_price REAL,
        total_shares    REAL DEFAULT 0,
        total_cost      REAL DEFAULT 0,         -- total $ invested

        -- Current
        current_price   REAL,
        current_value   REAL,
        unrealized_pnl  REAL,
        unrealized_pct  REAL,
        last_updated    TEXT,

        -- Exit
        avg_exit_price  REAL,
        total_proceeds  REAL,
        realized_pnl    REAL,
        realized_pct    REAL,
        closed_at       TEXT,

        -- Context
        entry_thesis    TEXT,                   -- why you entered this specific ticker
        exit_reason     TEXT,
        added_at        TEXT DEFAULT (datetime('now')),
        notes           TEXT
    );

    -- ─── TRANSACTIONS ─────────────────────────────────────────
    -- Every buy/sell action (granular ledger)
    CREATE TABLE IF NOT EXISTS transactions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        position_id     INTEGER REFERENCES positions(id),
        theme_id        INTEGER REFERENCES themes(id),
        ticker          TEXT NOT NULL,
        action          TEXT NOT NULL,          -- buy | sell | add | trim
        shares          REAL NOT NULL,
        price           REAL NOT NULL,
        total           REAL,                   -- shares * price
        conviction_at   REAL,                   -- conviction score at time of trade
        reason          TEXT,                   -- "adding on dip", "thesis confirmed", etc.
        executed_at     TEXT DEFAULT (datetime('now'))
    );

    -- ─── THEME EVENTS ─────────────────────────────────────────
    -- Timeline of everything that happened to a theme
    CREATE TABLE IF NOT EXISTS theme_events (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        theme_id        INTEGER REFERENCES themes(id),
        event_type      TEXT NOT NULL,          -- signal | entry | add | trim | exit |
                                                -- catalyst | milestone | thesis_update |
                                                -- reversal | watchlist
        title           TEXT,                   -- short label
        description     TEXT,
        conviction_before REAL,
        conviction_after  REAL,
        url             TEXT,                   -- source article if applicable
        happened_at     TEXT DEFAULT (datetime('now'))
    );

    -- ─── PRICE HISTORY ────────────────────────────────────────
    -- Snapshot prices for open positions (updated by watcher)
    CREATE TABLE IF NOT EXISTS price_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        position_id     INTEGER REFERENCES positions(id),
        ticker          TEXT NOT NULL,
        price           REAL NOT NULL,
        recorded_at     TEXT DEFAULT (datetime('now'))
    );

    -- ─── INDEXES ──────────────────────────────────────────────
    CREATE INDEX IF NOT EXISTS idx_positions_theme   ON positions(theme_id);
    CREATE INDEX IF NOT EXISTS idx_positions_ticker  ON positions(ticker);
    CREATE INDEX IF NOT EXISTS idx_txns_position     ON transactions(position_id);
    CREATE INDEX IF NOT EXISTS idx_txns_theme        ON transactions(theme_id);
    CREATE INDEX IF NOT EXISTS idx_events_theme      ON theme_events(theme_id);
    CREATE INDEX IF NOT EXISTS idx_events_time       ON theme_events(happened_at DESC);
    CREATE INDEX IF NOT EXISTS idx_price_position    ON price_history(position_id);
    CREATE INDEX IF NOT EXISTS idx_price_ticker      ON price_history(ticker);

    """)
    conn.commit()
    conn.close()
    return True


# ─── THEMES ───────────────────────────────────────────────

def create_theme(name: str, description: str = "",
                 layer_a: str = "", layer_b: str = "", layer_c: str = "",
                 linked_thesis_id: int = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO themes (name, description, layer_a, layer_b, layer_c, linked_thesis_id)
           VALUES (?,?,?,?,?,?)""",
        (name, description, layer_a, layer_b, layer_c, linked_thesis_id)
    )
    theme_id = cur.lastrowid
    log_event(theme_id, "watchlist", "Theme Created", description[:200], conn=conn)
    conn.commit()
    conn.close()
    return theme_id


def update_theme_conviction(theme_id: int, conviction: float, reason: str = ""):
    conn = get_conn()
    before = conn.execute("SELECT conviction FROM themes WHERE id=?", (theme_id,)).fetchone()
    before_val = before["conviction"] if before else 0
    conn.execute(
        """UPDATE themes
           SET conviction=?,
               peak_conviction=MAX(peak_conviction, ?),
               peak_at=CASE WHEN ? > conviction THEN datetime('now') ELSE peak_at END,
               status=CASE
                 WHEN ? >= 65 THEN 'active'
                 WHEN ? >= 35 THEN 'building'
                 ELSE 'watching'
               END
           WHERE id=?""",
        (conviction, conviction, conviction, conviction, conviction, theme_id)
    )
    log_event(theme_id, "thesis_update",
              f"Conviction {'↑' if conviction > before_val else '↓'} {conviction:.0f}",
              reason, before_val, conviction, conn=conn)
    conn.commit()
    conn.close()


def get_all_themes(include_closed=False) -> list:
    conn = get_conn()
    where = "" if include_closed else "WHERE t.status != 'closed'"
    rows = conn.execute(f"""
        SELECT t.*,
               COUNT(DISTINCT p.id) as position_count,
               SUM(CASE WHEN p.status='open' THEN p.total_cost ELSE 0 END) as total_invested,
               SUM(CASE WHEN p.status='open' THEN p.unrealized_pnl ELSE 0 END) as total_unrealized,
               SUM(CASE WHEN p.status='closed' THEN p.realized_pnl ELSE 0 END) as total_realized
        FROM themes t
        LEFT JOIN positions p ON p.theme_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY t.conviction DESC, t.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_theme(theme_id: int) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM themes WHERE id=?", (theme_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


# ─── POSITIONS ────────────────────────────────────────────

def add_position(theme_id: int, ticker: str, name: str = "",
                 layer: str = "C", entry_thesis: str = "") -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO positions (theme_id, ticker, name, layer, entry_thesis)
           VALUES (?,?,?,?,?)""",
        (theme_id, ticker.upper(), name, layer, entry_thesis)
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def record_transaction(position_id: int, theme_id: int, ticker: str,
                       action: str, shares: float, price: float,
                       reason: str = "", conviction_at: float = 0):
    conn = get_conn()
    total = shares * price

    conn.execute(
        """INSERT INTO transactions
           (position_id, theme_id, ticker, action, shares, price, total, conviction_at, reason)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (position_id, theme_id, ticker.upper(), action, shares, price, total, conviction_at, reason)
    )

    # Update position averages
    pos = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    if pos:
        if action in ("buy", "add"):
            new_shares = (pos["total_shares"] or 0) + shares
            new_cost   = (pos["total_cost"] or 0) + total
            new_avg    = new_cost / new_shares if new_shares else 0
            conn.execute(
                """UPDATE positions SET total_shares=?, total_cost=?, avg_entry_price=?,
                   activated_at=COALESCE(activated_at, datetime('now'))
                   WHERE id=?""",
                (new_shares, new_cost, new_avg, position_id)
            )
            # Mark theme as activated
            conn.execute(
                "UPDATE themes SET activated_at=COALESCE(activated_at,datetime('now')) WHERE id=?",
                (theme_id,)
            )
        elif action in ("sell", "trim"):
            new_shares = max(0, (pos["total_shares"] or 0) - shares)
            proceeds   = (pos["total_proceeds"] or 0) + total
            pnl        = proceeds - ((pos["total_cost"] or 0) * (shares / (pos["total_shares"] or 1)))
            status     = "closed" if new_shares == 0 else "partial"
            conn.execute(
                """UPDATE positions SET total_shares=?, total_proceeds=?, realized_pnl=?,
                   status=?, closed_at=CASE WHEN ? = 0 THEN datetime('now') ELSE NULL END
                   WHERE id=?""",
                (new_shares, proceeds, pnl, status, new_shares, position_id)
            )

    log_event(theme_id, action,
              f"{action.upper()} {shares} {ticker} @ ${price:.2f}",
              reason, conn=conn)
    conn.commit()
    conn.close()


def update_position_price(position_id: int, current_price: float):
    conn = get_conn()
    pos = conn.execute("SELECT * FROM positions WHERE id=?", (position_id,)).fetchone()
    if pos and pos["total_shares"] and pos["total_shares"] > 0:
        current_value  = pos["total_shares"] * current_price
        unrealized_pnl = current_value - (pos["total_cost"] or 0)
        unrealized_pct = (unrealized_pnl / pos["total_cost"] * 100) if pos["total_cost"] else 0
        conn.execute(
            """UPDATE positions SET current_price=?, current_value=?,
               unrealized_pnl=?, unrealized_pct=?, last_updated=datetime('now')
               WHERE id=?""",
            (current_price, current_value, unrealized_pnl, unrealized_pct, position_id)
        )
        conn.execute(
            "INSERT INTO price_history (position_id, ticker, price) VALUES (?,?,?)",
            (position_id, pos["ticker"], current_price)
        )
    conn.commit()
    conn.close()


def get_positions(theme_id: int = None) -> list:
    conn = get_conn()
    if theme_id:
        rows = conn.execute(
            "SELECT * FROM positions WHERE theme_id=? ORDER BY total_cost DESC",
            (theme_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM positions WHERE status != 'closed' ORDER BY total_cost DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_transactions(position_id: int = None, theme_id: int = None) -> list:
    conn = get_conn()
    if position_id:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE position_id=? ORDER BY executed_at DESC",
            (position_id,)
        ).fetchall()
    elif theme_id:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE theme_id=? ORDER BY executed_at DESC",
            (theme_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY executed_at DESC LIMIT 100"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── EVENTS ───────────────────────────────────────────────

def log_event(theme_id: int, event_type: str, title: str, description: str = "",
              conviction_before: float = None, conviction_after: float = None,
              url: str = "", conn=None):
    close_after = conn is None
    if conn is None:
        conn = get_conn()
    conn.execute(
        """INSERT INTO theme_events
           (theme_id, event_type, title, description, conviction_before, conviction_after, url)
           VALUES (?,?,?,?,?,?,?)""",
        (theme_id, event_type, title, description[:500] if description else "",
         conviction_before, conviction_after, url)
    )
    if close_after:
        conn.commit()
        conn.close()


def get_theme_timeline(theme_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM theme_events WHERE theme_id=? ORDER BY happened_at DESC",
        (theme_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── PRICE UPDATER ────────────────────────────────────────

def refresh_prices():
    """Pull latest prices for all open positions using yfinance."""
    try:
        import yfinance as yf
        conn = get_conn()
        open_positions = conn.execute(
            "SELECT id, ticker FROM positions WHERE status != 'closed'"
        ).fetchall()
        conn.close()

        for pos in open_positions:
            try:
                ticker = yf.Ticker(pos["ticker"])
                price = ticker.fast_info.get("last_price") or ticker.fast_info.get("previousClose")
                if price:
                    update_position_price(pos["id"], float(price))
            except Exception:
                pass
    except ImportError:
        pass


# ─── SUMMARY ──────────────────────────────────────────────

def get_portfolio_summary() -> dict:
    conn = get_conn()
    r = conn.execute("""
        SELECT
            COUNT(DISTINCT t.id) as active_themes,
            COUNT(DISTINCT p.id) as open_positions,
            COALESCE(SUM(CASE WHEN p.status='open' THEN p.total_cost END), 0) as total_invested,
            COALESCE(SUM(CASE WHEN p.status='open' THEN p.unrealized_pnl END), 0) as total_unrealized,
            COALESCE(SUM(CASE WHEN p.status='closed' THEN p.realized_pnl END), 0) as total_realized
        FROM themes t
        LEFT JOIN positions p ON p.theme_id = t.id
        WHERE t.status != 'closed'
    """).fetchone()
    conn.close()
    summary = dict(r) if r else {}
    total = (summary.get("total_unrealized") or 0) + (summary.get("total_realized") or 0)
    invested = summary.get("total_invested") or 0
    summary["total_pnl"] = total
    summary["total_pnl_pct"] = (total / invested * 100) if invested else 0
    return summary
