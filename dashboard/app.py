"""
Alpha Hunter Dashboard
Live web UI showing all active theses, conviction curves, and evidence feed.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import sqlite3
from flask import Flask, render_template, jsonify, Response
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/alpha_hunter.db")

app = Flask(__name__)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/theses")
def api_theses():
    conn = db()
    theses = conn.execute(
        "SELECT * FROM theses WHERE status != 'exited' ORDER BY conviction DESC"
    ).fetchall()

    result = []
    for t in theses:
        assets = json.loads(t["assets"] or "[]")
        tags = json.loads(t["tags"] or "[]")

        # Get conviction history for sparkline
        history = conn.execute(
            """SELECT conviction, recorded_at FROM conviction_history
               WHERE thesis_id=? ORDER BY recorded_at ASC""",
            (t["id"],)
        ).fetchall()

        # Get recent evidence
        evidence = conn.execute(
            """SELECT source, direction, content, logged_at FROM evidence
               WHERE thesis_id=? ORDER BY logged_at DESC LIMIT 5""",
            (t["id"],)
        ).fetchall()

        result.append({
            "id": t["id"],
            "name": t["name"],
            "summary": t["summary"],
            "assets": assets,
            "tags": tags,
            "conviction": t["conviction"],
            "position_pct": t["position_pct"],
            "status": t["status"],
            "born_at": t["born_at"],
            "updated_at": t["updated_at"],
            "history": [{"v": h["conviction"], "t": h["recorded_at"]} for h in history],
            "evidence": [{"src": e["source"], "dir": e["direction"],
                         "content": e["content"][:200], "at": e["logged_at"]} for e in evidence],
        })

    conn.close()
    return jsonify(result)


@app.route("/api/events")
def api_events():
    conn = db()
    events = conn.execute(
        """SELECT source, content, author, received_at, processed
           FROM raw_events ORDER BY received_at DESC LIMIT 50"""
    ).fetchall()
    conn.close()
    return jsonify([dict(e) for e in events])


@app.route("/api/stats")
def api_stats():
    conn = db()
    stats = {
        "total_theses": conn.execute("SELECT COUNT(*) FROM theses").fetchone()[0],
        "active_theses": conn.execute("SELECT COUNT(*) FROM theses WHERE status!='exited'").fetchone()[0],
        "total_evidence": conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
        "total_events": conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()[0],
        "unprocessed_events": conn.execute("SELECT COUNT(*) FROM raw_events WHERE processed=0").fetchone()[0],
        "high_conviction": conn.execute("SELECT COUNT(*) FROM theses WHERE conviction>=65 AND status!='exited'").fetchone()[0],
    }
    conn.close()
    return jsonify(stats)


if __name__ == "__main__":
    print("🎯 Alpha Hunter Dashboard → http://localhost:5050")
    app.run(port=5050, debug=False)
