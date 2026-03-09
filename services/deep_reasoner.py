"""
Deep Reasoner — 3-Layer Chain Reasoning Engine

The core insight: markets price in Layer A and B almost instantly.
The real alpha lives at Layer C — the second-order beneficiary
that is cheap, ignored, and has no analyst coverage yet.

A → B → C
  A: macro event (everyone sees it)
  B: obvious first-order effect (consensus trade)
  C: non-obvious second-order beneficiary (where the money is)

C must satisfy ALL of:
  1. Cheap — near 52w low, or down 70%+, or just spun off / IPO'd
  2. Ignored — minimal coverage, low social mentions, no analyst notes
  3. High leverage — directly benefits from B playing out
  4. Survivable — has cash runway to wait for the thesis to play out
"""

import os
import json
import logging
import anthropic
from services.database import (
    get_all_theses, upsert_thesis, add_evidence,
    update_conviction, create_signal, get_unprocessed_events,
    mark_event_processed, get_conn
)

log = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """You are Alpha Hunter's deep reasoning engine.

Your job: find Layer C — the cheap, ignored, second-order beneficiary
that markets haven't recognized yet.

The three-layer framework:
  LAYER A (Trigger):   The macro event. Everyone sees it.
  LAYER B (Consensus): The obvious reaction. Already being priced in.
  LAYER C (Alpha):     The non-obvious downstream beneficiary.
                       CHEAP. IGNORED. HIGH LEVERAGE. SURVIVABLE.

Layer C criteria (ALL must be true):
  ✓ Price: near multi-year lows, or down 60%+, or just emerged (spinoff/IPO)
  ✓ Coverage: < 5 mainstream articles in last 30 days
  ✓ Leverage: directly and materially benefits from Layer B playing out
  ✓ Survivable: has enough cash/revenue to wait 6-24 months

Famous Layer C trades:
  - AI boom (A) → Nvidia (B, obvious) → Vertiv/cooling/uranium (C, ignored)
  - Trump tariffs (A) → gold/CHF (B, obvious) → rare earth processors outside China (C)
  - SNDK spinoff (A) → NAND recovery (B) → Korea index/Samsung ecosystem (C)
  - Rate cuts coming (A) → housing (B, obvious) → Opendoor at $0.50 (C, priced for bankruptcy)
  - DeepSeek launches (A) → chip selloff (B) → Chinese AI infra plays cheap (C)

You reason in chains. You always ask:
  "Who benefits from B that nobody is talking about?"
  "What is the downstream supply chain effect of B?"
  "What asset is MOST leveraged to this but trading at its LOWEST?"
  "Who will look obvious in hindsight but is invisible right now?"

Output JSON only. No preamble."""


def build_prompt(events: list, existing_theses: list) -> str:
    event_text = "\n\n".join([
        f"[{e['source'].upper()}] {e['content'][:180]}"
        for e in events[:6]
    ])

    thesis_summary = "\n".join([
        f"  [{t['id']}] {t['name']} | conviction:{t['conviction']:.0f} | assets:{t['assets']}"
        for t in existing_theses
    ]) or "  None yet."

    return f"""Analyze these market events using 3-layer chain reasoning.
For each significant event, trace A → B → C.
Focus on finding Layer C assets that are cheap and ignored RIGHT NOW.

CURRENT EVENTS:
{event_text}

EXISTING THESES (update these if relevant, don't duplicate):
{thesis_summary}

Respond with JSON:
{{
  "chains": [
    {{
      "layer_a": {{
        "event": "The macro trigger in one sentence",
        "source": "where this came from"
      }},
      "layer_b": {{
        "effect": "The obvious first-order market reaction",
        "already_priced": true,
        "consensus_assets": ["NVDA", "GLD"],
        "why_skip": "Why chasing Layer B is late/crowded"
      }},
      "layer_c": {{
        "insight": "The non-obvious second-order opportunity in 2 sentences",
        "reasoning": "Step by step: A caused B, B causes C because...",
        "assets": ["TICKER1", "TICKER2"],
        "why_cheap": "Why these are cheap/ignored right now",
        "why_now": "What's the timing catalyst — why will market eventually see this?",
        "what_breaks_it": "What single event would kill this thesis",
        "initial_conviction": 30,
        "tags": ["macro", "sector", "geopolitical"]
      }}
    }}
  ],
  "evidence_updates": [
    {{
      "thesis_id": 1,
      "layer": "B",
      "direction": "for",
      "content": "How this event affects existing thesis",
      "conviction_delta": 8
    }}
  ],
  "summary": "One sentence: most important Layer C finding today"
}}

Rules:
- Max 2 chains per response
- Keep all string values under 120 chars
- Only create a new thesis if Layer C assets are genuinely cheap and ignored
- initial_conviction: 20-40 range (new thesis needs to earn conviction over time)
- conviction_delta: max ±12 per event batch
- If no genuine Layer C opportunity exists, return empty chains array
- Layer C assets should be specific tickers, not just sectors
- Prefer small/mid cap — large caps are never ignored"""


def run_deep_reasoning(events: list) -> dict:
    if not events:
        return {}

    existing_theses = get_all_theses()
    prompt = build_prompt(events, existing_theses)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]
        return json.loads(raw)

    except Exception as e:
        log.error(f"Deep reasoning failed: {e}")
        return {}


def apply_chains(result: dict, events: list):
    if not result:
        return

    source_urls = [e["url"] for e in events if e.get("url")]

    # ── Process Layer C chains → new theses ──
    for chain in result.get("chains", []):
        lc = chain.get("layer_c", {})
        la = chain.get("layer_a", {})
        lb = chain.get("layer_b", {})

        if not lc.get("assets"):
            continue

        name = f"{la.get('event','?')[:40]} → {lc.get('insight','?')[:40]}"
        summary = (
            f"[A] {la.get('event','')}\n"
            f"[B] {lb.get('effect','')} (consensus, skip)\n"
            f"[C] {lc.get('insight','')}\n\n"
            f"Why cheap/ignored: {lc.get('why_cheap','')}\n"
            f"Timing: {lc.get('why_now','')}\n"
            f"Breaks if: {lc.get('what_breaks_it','')}"
        )

        try:
            thesis_id = upsert_thesis(
                name=name,
                summary=summary,
                assets=lc.get("assets", []),
                tags=lc.get("tags", []),
            )

            conviction = lc.get("initial_conviction", 25)
            update_conviction(thesis_id, conviction, lc.get("reasoning", ""), trigger_type="deep_reasoning")

            # Create a signal record — the birth signal
            signal_id = create_signal(
                thesis_id=thesis_id,
                signal_type="macro",
                trigger_desc=f"3-layer chain: {la.get('event','')} → {lb.get('effect','')} → {lc.get('insight','')}",
                direction="for",
                strength="moderate",
                strength_score=conviction,
                url=source_urls[0] if source_urls else "",
            )

            # Store full chain as evidence
            add_evidence(
                thesis_id=thesis_id,
                source="deep_reasoning",
                direction="for",
                content=(
                    f"LAYER A: {la.get('event','')}\n"
                    f"LAYER B (consensus/skip): {lb.get('effect','')} — {lb.get('why_skip','')}\n"
                    f"LAYER C (alpha): {lc.get('reasoning','')}"
                ),
                url=source_urls[0] if source_urls else "",
                signal_id=signal_id,
            )

            # Log Layer B as context (not the trade, but important context)
            add_evidence(
                thesis_id=thesis_id,
                source="layer_b_context",
                direction="neutral",
                content=f"Consensus trade (skip): {lb.get('effect','')} → {', '.join(lb.get('consensus_assets',[]))}. {lb.get('why_skip','')}",
                url="",
            )

            log.info(
                f"[3-LAYER] New thesis: [{thesis_id}] {name[:60]} "
                f"(conviction:{conviction}, C-assets:{lc.get('assets',[])})"
            )

        except Exception as e:
            log.error(f"Failed to apply chain: {e}")

    # ── Update existing theses ──
    all_theses = {t["id"]: t for t in get_all_theses()}
    for update in result.get("evidence_updates", []):
        try:
            thesis_id = update["thesis_id"]
            if thesis_id not in all_theses:
                continue
            current = all_theses[thesis_id]["conviction"]
            delta = update.get("conviction_delta", 0)
            new_conviction = max(0, min(100, current + delta))

            ev_url = source_urls[len(result.get("evidence_updates",[]))  % len(source_urls)] if source_urls else ""

            add_evidence(
                thesis_id=thesis_id,
                source=f"deep_reasoning:layer_{update.get('layer','?')}",
                direction=update["direction"],
                content=update["content"],
                url=ev_url,
            )
            update_conviction(thesis_id, new_conviction, update["content"], trigger_type="deep_reasoning")
            log.info(f"Thesis [{thesis_id}] updated: {current:.0f} → {new_conviction:.0f} ({delta:+.0f})")

        except Exception as e:
            log.error(f"Failed to update thesis: {e}")

    if result.get("summary"):
        log.info(f"[3-LAYER SUMMARY] {result['summary']}")


def run():
    """Process unprocessed events through 3-layer chain reasoning."""
    events = get_unprocessed_events(limit=8)
    if not events:
        log.info("Deep reasoner: no new events")
        return 0

    log.info(f"Deep reasoning {len(events)} events (3-layer chain)...")
    result = run_deep_reasoning(events)
    apply_chains(result, events)

    for e in events:
        mark_event_processed(e["id"])

    return len(events)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    run()
