"""
Reasoning Engine — the brain of Alpha Hunter.
Claude reads raw events and does two things:
1. Generates new theses from macro events (top-down)
2. Updates existing thesis conviction from new evidence (bottom-up)

This is the "thinking" layer. Everything else is just data collection.
"""

import os
import json
import logging
import anthropic
from services.database import (
    get_unprocessed_events, mark_event_processed,
    get_all_theses, upsert_thesis, add_evidence,
    update_conviction, get_thesis_evidence
)

log = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))


SYSTEM_PROMPT = """You are Alpha Hunter's reasoning engine — a macro analyst that finds hidden, ignored investment opportunities before they explode.

Your edge: you reason from macro events to 2nd and 3rd order effects, finding assets that are cheap and ignored but have a structural catalyst building.

Real examples of trades you would have caught early:
- OPEN (Opendoor) at $0.50: housing market frozen, but company has cash, new CEO, waiting on rate cuts
- SNDK at spinoff: AI boom → data storage demand → NAND cycle turning → pure-play spinoff mispriced
- Gold pre-$4000: Trump tariffs → uncertainty → debasement → central bank buying
- Korea (KOSPI) +76%: AI boom → Samsung/SK Hynix → Korea index cheap and ignored
- Rare earths: US-China tensions → China controls supply → domestic producers undervalued

Your thinking style:
- Always ask: what's the 2nd and 3rd order effect?
- Always ask: who is the unintended beneficiary?
- Always ask: what asset is MOST leveraged to this thesis AND cheapest right now?
- Always ask: what would BREAK this thesis?

You output structured JSON only. No preamble."""


def reason_on_events(events: list) -> dict:
    """Process a batch of raw events through Claude."""
    if not events:
        return {}

    existing_theses = get_all_theses()
    thesis_summary = "\n".join([
        f"- [{t['id']}] {t['name']} (conviction: {t['conviction']:.0f}, assets: {t['assets']})"
        for t in existing_theses
    ]) or "None yet."

    event_text = "\n\n".join([
        f"[{e['source'].upper()}] {e['content'][:600]}"
        for e in events[:15]  # Process in batches of 15
    ])

    prompt = f"""Analyze these new market events and decide:
1. Do any create a NEW investment thesis? (macro event → chain reasoning → underpriced asset)
2. Do any SUPPORT or CONTRADICT existing theses?
3. For each finding, what should the conviction score change be?

EXISTING ACTIVE THESES:
{thesis_summary}

NEW EVENTS:
{event_text}

Respond with JSON only:
{{
  "new_theses": [
    {{
      "name": "short thesis name",
      "summary": "the core thesis in 2-3 sentences. Include: why now, what's the catalyst, what could break it",
      "assets": ["TICKER1", "TICKER2"],
      "tags": ["macro", "geopolitical", "sector"],
      "initial_conviction": 25,
      "reasoning": "step by step: event → 1st order → 2nd order → asset → why cheap/ignored"
    }}
  ],
  "evidence_updates": [
    {{
      "thesis_id": 1,
      "direction": "for",
      "content": "what this event means for the thesis",
      "conviction_delta": 5,
      "weight": 1.5
    }}
  ],
  "summary": "one sentence on the most important signal today"
}}

Rules:
- Only create a new thesis if you have genuine conviction it's early and underpriced
- conviction_delta: positive = stronger, negative = weaker. Max ±15 per event
- initial_conviction: 15-35 range for new theses (they need to earn conviction over time)
- If events are noise with no thesis implication, return empty arrays"""

    try:
        response = client.messages.create(
            model="claude-haiku-3-5",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Strip markdown if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)

    except Exception as e:
        log.error(f"Reasoning engine failed: {e}")
        return {}


def apply_reasoning(result: dict, event_sources: list):
    """Apply Claude's reasoning output to the database."""
    if not result:
        return

    # Create new theses
    for t in result.get("new_theses", []):
        try:
            thesis_id = upsert_thesis(
                name=t["name"],
                summary=t["summary"],
                assets=t.get("assets", []),
                tags=t.get("tags", []),
            )
            update_conviction(thesis_id, t.get("initial_conviction", 20), t.get("reasoning", ""))
            add_evidence(
                thesis_id=thesis_id,
                source="reasoning",
                direction="for",
                content=t["reasoning"],
                weight=1.0,
            )
            log.info(f"New thesis born: [{thesis_id}] {t['name']} (conviction: {t.get('initial_conviction', 20)})")
        except Exception as e:
            log.error(f"Failed to save thesis: {e}")

    # Update existing thesis conviction
    all_theses = {t["id"]: t for t in get_all_theses()}
    for update in result.get("evidence_updates", []):
        try:
            thesis_id = update["thesis_id"]
            if thesis_id not in all_theses:
                continue

            current = all_theses[thesis_id]["conviction"]
            delta = update.get("conviction_delta", 0)
            new_conviction = max(0, min(100, current + delta))

            add_evidence(
                thesis_id=thesis_id,
                source=", ".join(set(e["source"] for e in event_sources)),
                direction=update["direction"],
                content=update["content"],
                weight=update.get("weight", 1.0),
            )
            update_conviction(thesis_id, new_conviction, update["content"])
            log.info(f"Thesis [{thesis_id}] conviction: {current:.0f} → {new_conviction:.0f} ({delta:+.0f})")

        except Exception as e:
            log.error(f"Failed to update thesis evidence: {e}")

    if result.get("summary"):
        log.info(f"Reasoning summary: {result['summary']}")


def run():
    """Process all unprocessed events through Claude."""
    events = get_unprocessed_events(limit=30)
    if not events:
        log.info("Reasoner: no new events to process")
        return 0

    log.info(f"Reasoner processing {len(events)} events...")
    result = reason_on_events(events)
    apply_reasoning(result, events)

    # Mark all processed
    for e in events:
        mark_event_processed(e["id"])

    log.info("Reasoner complete")
    return len(events)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
