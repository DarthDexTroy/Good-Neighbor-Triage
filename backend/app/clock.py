"""Scenario clock. Times are stored as simulated minutes since the flood started (T+0)."""
import time

from . import config, db


def start():
    db.put("meta", "clock", {"id": "clock", "real_start": time.time()})


def now() -> float:
    m = db.get("meta", "clock")
    if not m:
        return 0.0
    return round((time.time() - m["real_start"]) * config.SIM_SPEED / 60, 2)


def fmt(minutes: float | None) -> str:
    if minutes is None:
        return "-"
    h, m = divmod(int(minutes), 60)
    return f"T+{h}h{m:02d}m"
