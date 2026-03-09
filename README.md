# 🎯 Alpha Hunter

> Find ignored, cheap assets before they explode.

## Philosophy

The best trades share a pattern:
- **Nobody cares yet** — low volume, low coverage, off the radar
- **Cheap enough** — room to build a position without moving the market
- **Something is changing** — a catalyst building under the surface
- **Conviction trigger** — when signals align, move fast and build the position

Alpha Hunter runs on a schedule, scans thousands of assets across multiple signal sources, scores conviction, and alerts you when something looks like the next SNDK, silver, or SNDK-style explosion.

## How It Works

```
┌─────────────────────────────────────────────────────┐
│                     SCANNERS                        │
│  Price/Volume  │  News  │  Social  │  Events/Corp   │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                     SIGNALS                         │
│  Momentum Score  │  Volume Anomaly  │  Sentiment    │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                  CONVICTION ENGINE                  │
│  Weighted score across all signals → 0-100          │
└────────────────────────┬────────────────────────────┘
                         │
                    score > threshold
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                     ALERT                           │
│  Telegram message with ticker, thesis, entry zone  │
└─────────────────────────────────────────────────────┘
```

## Signals Tracked

| Signal | Why It Matters |
|--------|---------------|
| Price near 52-week low | Cheap, ignored |
| Volume spike (quiet → loud) | Smart money entering |
| Short interest high | Squeeze potential |
| Insider buying | They know something |
| News sentiment turning positive | Narrative shift |
| Social mentions accelerating | Retail FOMO incoming |
| Macro tailwind alignment | Sector catalyst |
| Corporate events (spinoffs, splits) | Structural unlocks |

## Setup

```bash
pip install -r requirements.txt
cp config.yaml.example config.yaml
# edit config.yaml with your API keys and Telegram bot token
python main.py
```

## Scheduling

Runs automatically via GitHub Actions on a cron schedule.
Set secrets in repo settings:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `BRAVE_API_KEY`

## Output Example

```
🎯 ALPHA HUNTER ALERT

Ticker: $XYZ
Conviction: 78/100
Price: $4.21 (-62% from 52w high)
Why now:
  ✅ Volume up 340% vs 30-day avg
  ✅ Insider bought $2.1M last week
  ✅ Short interest 34% — squeeze setup
  ✅ Sector macro tailwind: rising commodity prices
  ✅ Sentiment turning: 3 bullish analyst pieces this week

Entry zone: $3.80–$4.50
Add on dips. Wait for explosion.
```
