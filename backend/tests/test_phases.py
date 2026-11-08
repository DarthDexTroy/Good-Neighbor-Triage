"""Before / During / After: phase clock, exposure, action texts, recovery lanes, scorecard."""
import os
import tempfile

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ["DEMO_MODE"] = "0"
os.environ["NVIDIA_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import clock, scoring, services, silence  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)
NO_NEEDS = {"oxygen": False, "dialysis": False, "insulin_hours_left": None, "infant": False,
            "elderly": False, "mobility": False, "power_out": False}


def test_clock_formats_negative_time():
    assert clock.fmt(-4320) == "T−72h00m"
    assert clock.fmt(-90.5) == "T−1h30m"
    assert clock.fmt(2880) == "T+48h00m"
    assert [clock.phase_of(t) for t in (-1, 0, 2879, 2880)] == ["before", "during", "during", "after"]


def test_negative_time_does_not_break_scoring_or_silence():
    # Census household before landfall: no negative silence points.
    s, reasons = scoring.compute(NO_NEEDS, 3.0, True, "unreached", [], None, None, -4320, reachable=False)
    assert s == 15 and not any("No way to contact" in r for r in reasons)
    blocks = [{"id": "A", "flood_depth_ft": 5.0, "svi": 0.9}]
    hh = [{"id": f"a{i}", "block_id": "A"} for i in range(10)]
    cases = {h["id"]: {"last_reply_at": None} for h in hh}
    assert not silence.block_stats(blocks, hh, cases, outreach_at=None, now=-4000)[0]["flagged"]


def test_phase_jumps():
    c.post("/api/scenario/start", json={"phase": "before"})
    st = c.get("/api/state").json()
    assert st["event_phase"] == "before" and -4330 < st["now"] <= -4310
    for phase, at in clock.PHASE_AT.items():
        r = c.post("/api/phase", json={"phase": phase}).json()
        assert r["phase"] == phase and at <= r["now"] < at + 10
        assert c.get("/api/state").json()["event_phase"] == phase
    assert c.post("/api/phase", json={"phase": "later"}).status_code == 422
