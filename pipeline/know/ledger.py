"""KNOW / ledger — the sporting-code escalation as a deterministic FSM.

Default profile mirrors the published 2026 guideline shape:
warn1 -> warn2 -> black-and-white flag (3rd) -> 5 s (4th+) -> 10 s.
Profiles are YAML-configurable per series (config/rules_profiles/).
No LLM, no learned judge: the rule is written law; determinism is a feature.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_STEPS = ["warn1", "warn2", "bw_flag", "p5s", "p10s"]


@dataclass
class DriverLedger:
    steps: list[str] = field(default_factory=lambda: list(DEFAULT_STEPS))
    count: int = 0
    history: list[dict] = field(default_factory=list)

    @property
    def current_step(self) -> str | None:
        i = self.count - 1
        return self.steps[min(i, len(self.steps) - 1)] if i >= 0 else None

    @property
    def next_step(self) -> str:
        return self.steps[min(self.count, len(self.steps) - 1)]

    def apply_strike(self, incident_id: int) -> dict:
        self.count += 1
        step = self.current_step
        entry = {"incident_id": incident_id, "strike": self.count, "step": step}
        self.history.append(entry)
        return entry

    def alert(self) -> str | None:
        nxt = self.next_step
        if nxt in ("p5s", "p10s", "bw_flag"):
            return f"next violation = {nxt.replace('p', '').replace('s', ' s penalty') if nxt.startswith('p') else 'black-and-white flag'}"
        return None
