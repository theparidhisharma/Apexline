"""KNOW / taxonomy — the seven violation types + context exceptions.

Most teams detect one violation and don't know the rest exist. The rules
engine below encodes the family (FIA ISC Art. 33.3 + published steward
guidance). Only geometry-pure V1/V2 with no context tags may auto-triage;
V3-V7 and anything context-tagged ALWAYS routes to a human.
"""
from __future__ import annotations

from dataclasses import dataclass, field

TAXONOMY = {
    "V1": ("Lap-time deletion (practice/quali)", True),
    "V2": ("Repeated infringement (race strikes)", True),
    "V3": ("Overtaking off track", False),
    "V4": ("Keeping/defending position off track", False),
    "V5": ("Lasting advantage / time gained", False),
    "V6": ("Unsafe rejoin", False),
    "V7": ("Forcing another car off", False),
    "X":  ("Context exception (avoidance / lost control / place returned)", False),
}


@dataclass
class Context:
    session_type: str = "race"           # practice|quali|race
    rival_within_1s: bool = False        # proximity at the crossing
    position_changed: bool = False       # gained a place through the excursion
    position_retained_under_attack: bool = False
    speed_anomaly: bool = False          # sudden brake/speed spike -> possible loss of control
    gave_place_back: bool | None = None
    rejoin_traffic_close: bool = False
    tags: list[str] = field(default_factory=list)


def classify(ctx: Context) -> tuple[str, list[str], bool]:
    """Returns (type_code, context_tags, auto_decidable)."""
    tags = list(ctx.tags)
    if ctx.speed_anomaly:
        tags.append("possible-loss-of-control")
    if ctx.rival_within_1s:
        tags.append("proximity")

    if ctx.rejoin_traffic_close:
        return "V6", tags + ["unsafe-rejoin-risk"], False
    if ctx.position_changed:
        code = "V3"
    elif ctx.position_retained_under_attack:
        code = "V4"
    elif ctx.session_type in ("practice", "quali"):
        code = "V1"
    else:
        code = "V2"

    if ctx.gave_place_back:
        return "X", tags + ["place-returned"], False

    auto = code in ("V1", "V2") and not tags
    return code, tags, auto
