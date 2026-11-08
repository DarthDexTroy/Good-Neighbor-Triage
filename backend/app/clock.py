"""Scenario clock. Times are simulated minutes relative to landfall (T+0). Before landfall they are negative.

Phases: before = T−72h → landfall, during = landfall → T+48h, after = T+48h onward.
"""
import time

from . import config, db

PHASE_AT = {"before": -72 * 60, "during": 0, "after": 48 * 60}


def start(at: float = 0.0):
    """Start (or jump) the clock so that now() == at."""
    db.put("meta", "clock", {"id": "clock", "real_start": time.time() - at * 60 / config.SIM_SPEED})


def jump(at: float):
    start(at)


def now() -> float:
    m = db.get("meta", "clock")
    if not m:
        return 0.0
    return round((time.time() - m["real_start"]) * config.SIM_SPEED / 60, 2)


def phase_of(minutes: float) -> str:
    if minutes < PHASE_AT["during"]:
        return "before"
    if minutes < PHASE_AT["after"]:
        return "during"
    return "after"


def fmt(minutes: float | None) -> str:
    if minutes is None:
        return "-"
    sign = "−" if minutes < 0 else "+"
    h, m = divmod(int(abs(minutes)), 60)
    return f"T{sign}{h}h{m:02d}m"
