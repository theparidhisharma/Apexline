"""OPTIONAL Groq layer — plain-language incident summaries & session reports.

HARD RULE (say it to judges): no LLM in the decision path. Detection is
geometry, adjudication is deterministic law. Groq only turns already-decided
facts into readable prose for the report. If GROQ_API_KEY is absent, the
system produces a deterministic template summary instead — nothing breaks.

Setup: see docs/GROQ_SETUP.md.
"""
from __future__ import annotations

import os


def _template(inc: dict) -> str:
    return (f"Car {inc.get('car', '?')} — {inc.get('type_code')} at {inc.get('corner', 'monitored corner')}: "
            f"all four wheels beyond the boundary for {inc.get('duration_ms', 0)} ms, "
            f"peak overshoot {inc.get('max_overshoot_m', 0):.2f} m "
            f"(±{inc.get('error_band_m', 0):.2f} m), confidence {inc.get('confidence', 0):.2f}. "
            f"Band: {inc.get('band')}. Decision: {inc.get('status', 'pending')}.")


def explain_incident(inc: dict) -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return _template(inc)
    try:
        from groq import Groq
        client = Groq(api_key=key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=180,
            messages=[
                {"role": "system", "content":
                 "You write neutral, factual steward-report sentences. Never judge "
                 "guilt; only restate the provided measurements and decision."},
                {"role": "user", "content": f"Summarise this adjudicated incident for a session report: {inc}"},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return _template(inc)  # LLM failure degrades to template, never to silence
