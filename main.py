#!/usr/bin/env python3
"""
Alpha Hunter — Main Entry Point
Scans for ignored, cheap assets before they explode.
"""

import yaml
import logging
import argparse
from datetime import datetime
from rich.console import Console
from rich.table import Table

from scanners.price_scanner import PriceScanner
from scanners.news_scanner import NewsScanner
from scanners.events_scanner import EventsScanner
from signals.conviction import ConvictionEngine
from screener.universe import UniverseLoader
from alerts.telegram import TelegramAlerter
from storage.db import Database

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("alpha-hunter")


def load_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def run_scan(config: dict, dry_run: bool = False):
    console.rule("[bold yellow]🎯 Alpha Hunter Scan Starting[/bold yellow]")
    console.print(f"  [dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n")

    cfg = config["scanner"]
    db = Database(config["storage"]["db_path"])

    # 1. Load universe of assets to scan
    console.print("[bold]Loading universe...[/bold]")
    universe = UniverseLoader(cfg).load()
    console.print(f"  → {len(universe)} assets loaded\n")

    # 2. Run scanners
    price_scanner = PriceScanner(config)
    news_scanner = NewsScanner(config)
    events_scanner = EventsScanner(config)

    candidates = []
    for ticker in universe:
        try:
            price_data = price_scanner.scan(ticker)
            if price_data is None:
                continue

            news_data = news_scanner.scan(ticker)
            events_data = events_scanner.scan(ticker)

            # 3. Score conviction
            engine = ConvictionEngine(config["signals"])
            score, breakdown = engine.score(ticker, price_data, news_data, events_data)

            if score > 0:
                candidates.append({
                    "ticker": ticker,
                    "score": score,
                    "breakdown": breakdown,
                    "price_data": price_data,
                    "news_data": news_data,
                    "events_data": events_data,
                })

        except Exception as e:
            log.debug(f"Skipping {ticker}: {e}")

    # 4. Sort by conviction score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # 5. Display results
    display_results(candidates[:20])

    # 6. Alert on high-conviction plays
    threshold = cfg.get("conviction_threshold", 65)
    alerts = [c for c in candidates if c["score"] >= threshold]

    if alerts:
        console.print(f"\n[bold green]🚀 {len(alerts)} high-conviction alert(s) found![/bold green]\n")
        alerter = TelegramAlerter(config["telegram"])
        for alert in alerts:
            db.save_alert(alert)
            if not dry_run:
                alerter.send(alert)
    else:
        console.print(f"\n[dim]No candidates above threshold ({threshold}). Market quiet.[/dim]")

    console.rule("[bold yellow]Scan Complete[/bold yellow]")
    return candidates


def display_results(candidates):
    if not candidates:
        console.print("[dim]No candidates found.[/dim]")
        return

    table = Table(title="Top Candidates", show_lines=True)
    table.add_column("Rank", style="dim", width=5)
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Score", style="bold yellow")
    table.add_column("Price", style="green")
    table.add_column("vs 52w Low", style="red")
    table.add_column("Vol Spike", style="magenta")
    table.add_column("Top Signal", style="white")

    for i, c in enumerate(candidates, 1):
        pd = c["price_data"]
        bd = c["breakdown"]
        top_signal = max(bd, key=bd.get) if bd else "—"
        table.add_row(
            str(i),
            c["ticker"],
            f"{c['score']:.0f}/100",
            f"${pd.get('price', 0):.2f}",
            f"+{pd.get('pct_from_52w_low', 0):.0f}%",
            f"{pd.get('volume_ratio', 0):.1f}x",
            top_signal.replace("_", " ").title(),
        )

    console.print(table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alpha Hunter — find the next explosion")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--dry-run", action="store_true", help="Scan but don't send alerts")
    parser.add_argument("--ticker", help="Scan a single ticker for debugging")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.ticker:
        config["scanner"]["universe"] = [args.ticker]

    run_scan(config, dry_run=args.dry_run)
