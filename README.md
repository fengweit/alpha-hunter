# Alpha Hunter

> **Status: Archived.** This project ran autonomously on a Mac mini from March 2026. All services have been stopped. The codebase is preserved here for reference.

---

## What it was

Alpha Hunter was an AI-driven investment thesis detection and paper trading system that ran 24/7. It monitored news, SEC filings, and market signals, extracted investment theses using LLMs, scored conviction using a swarm simulation engine, and automatically executed paper trades on Alpaca.

The whole thing ran unattended — no manual intervention required once deployed.

---

## Architecture

A three-layer chain: **A → B → C**

```
Layer A — Signal Ingestion
  ├── news_scanner.py       — scrapes financial news headlines
  ├── events_scanner.py     — monitors SEC filings and corporate events
  ├── price_scanner.py      — detects unusual price/volume movement
  └── watcher_*.py          — monitors Reddit, Twitter for sentiment

Layer B — Theme Extraction & Reasoning
  ├── reasoner.py           — Claude Haiku extracts investment thesis from signals
  ├── deep_reasoner.py      — A→B→C chain: news event → macro theme → affected sectors
  └── event_processor.py    — deduplicates, clusters, and scores incoming signals

Layer C — Conviction Scoring & Execution
  ├── conviction.py         — MiroFish swarm: 20 LLM agents vote independently
  ├── alerter.py            — Telegram alerts on high-conviction theses
  └── runner.py             — Alpaca paper trading: sizes positions by conviction score
```

---

## Key components

### Signal ingestion
- Polled news APIs, SEC EDGAR, Reddit (`r/investing`, `r/stocks`), and Twitter
- Deduplicated signals using SQLite; tracked full lifecycle (detected → processed → acted)
- Python 3.9, ran every 5–15 minutes depending on the source

### LLM reasoning engine
- **Model:** Claude Haiku (cost target: ~$9/month)
- **Pattern:** Single news event → extract macro theme (e.g. "stagflation risk") → identify affected sectors (e.g. "M&A activity in defensives")
- 3-layer A→B→C chain made the reasoning explainable and auditable

### MiroFish swarm (conviction scoring)
- 20 independent LLM agents each evaluate a thesis without seeing each other's votes
- Aggregated conviction score: 0–100
- First simulation result: Thesis [5] Stagflation→M&A, 62% discovery, conviction 51→66
- Ran as a separate microservice at `http://127.0.0.1:5001`
- Python 3.11, venv at `~/mirofish/.venv`

### Alpaca paper trading
- $100K paper account, $200K buying power
- Position sizing by conviction score:

| Conviction | Allocation |
|-----------|-----------|
| < 20% | 0% (no trade) |
| 20–35% | 5% |
| 35–50% | 15% |
| 50–65% | 30% |
| 65–80% | 60% |
| ≥ 80% | 85% |

- Max $15K per thesis; dual confirmation required before >30% allocation
- Library: `alpaca-py==0.43.2`

### Dashboard
- Flask web app at `http://192.168.68.120:5050`
- Real-time thesis cards with conviction badges, source links, trade log
- Templates: `index.html` (main feed), `plays.html` (active positions)

---

## Tech stack

| Component | Tech |
|-----------|------|
| Language | Python 3.9 (main), Python 3.11 (MiroFish) |
| Database | SQLite at `~/alpha-hunter/data/alpha_hunter.db` |
| LLM | Anthropic Claude Haiku |
| Trading | Alpaca Markets (paper) |
| Dashboard | Flask |
| Notifications | Telegram bot |
| Deployment | macOS LaunchAgents (4 services) |

---

## Services (all now disabled)

```
ai.alphahunter.runner     — main signal loop + reasoning
ai.alphahunter.dashboard  — Flask dashboard
ai.alphahunter.mirofish   — swarm conviction engine
ai.alphahunter.portfolio  — portfolio runner / trade executor
```

All four LaunchAgents were disabled on 2026-03-25.

---

## Lessons learned

1. **The A→B→C chain worked.** Extracting a macro theme as the intermediate step made reasoning more coherent than direct news→trade signals. The "stagflation → M&A in defensives" thesis was the clearest example.

2. **MiroFish swarm added real signal.** Independent voting (20 agents, no cross-contamination) consistently moved conviction scores meaningfully vs. single-agent evaluation. Worth rebuilding as a standalone library.

3. **Cost was controllable.** Running Claude Haiku at 5-minute intervals across all signal sources stayed well under the $9/month target with batching.

4. **Paper trading revealed sizing bugs early.** The conviction→allocation mapping was too aggressive at the 65–80% band. Real money would require tighter dual-confirmation logic.

5. **The dashboard was the most useful part.** Having a human-readable view of what the agent was thinking — thesis cards, conviction scores, source links — built trust in the system far faster than reading logs.

---

## Related

- [OpenFactory](https://github.com/fengweit/OpenFactory) — current project: factory API infrastructure for AI agents in the GBA
