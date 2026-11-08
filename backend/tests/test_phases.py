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


def _thread(phone="+17135550188"):
    return [m["body"] for m in c.get("/api/thread", params={"phone": phone}).json()["messages"]]


def test_reyes_journey_before_during_after():
    c.post("/api/scenario/start", json={"phase": "before"})
    ex = c.get("/api/exposure").json()
    assert ex["totals"]["policies"] > 100 and ex["totals"]["expected_loss"] > 0
    assert any(h["demo"] for h in ex["homes"])

    # Before: action text in Spanish, reply 1 confirms the car.
    assert c.post("/api/before/send_actions").json()["sent"] > 50
    assert "Responda 1" in _thread()[-1]
    c.post("/api/dev/inbound", json={"phone": "+17135550188", "text": "1"})
    assert _thread()[-1].startswith("¡Gracias!")
    acts = {a["type"]: a for a in services.db.get("households", "H-REYES")["actions"]}
    assert acts["car"]["confirmed_t"] is not None and acts["meds"]["confirmed_t"] is None
    assert c.get("/api/scorecard").json()["avoided_by_type"]["car"] > 10000

    # During: the Spanish oxygen text puts the family at the top of the queue.
    c.post("/api/phase", json={"phase": "during"})
    c.post("/api/outreach/checkin_all")
    c.post("/api/dev/inbound", json={"phone": "+17135550188", "text": "el agua está entrando, mi mamá usa oxígeno"})
    q = c.get("/api/state").json()["queue"]
    assert q[0]["id"] == "H-REYES", [(x["name"], x["score"]) for x in q[:3]]

    # After: $1,840 minor claim lands in auto-pay, gets paid, and the family gets a text.
    c.post("/api/phase", json={"phase": "after"})
    lanes = c.get("/api/recovery/claims").json()["lanes"]
    reyes = next(x for x in lanes["autopay"] if x["household_id"] == "H-REYES")
    assert reyes["estimate"] == 1840 and reyes["claim_number"] == "DEMO-1042" and not reyes["flags"]
    assert c.post("/api/recovery/run_autopay").json()["paid"] >= 1
    assert "aprobado" in _thread()[-1] and "$1,840" in _thread()[-1]
    sc = c.get("/api/scorecard").json()
    assert sc["cycle_time_days"] < sc["cycle_baseline_days"] and sc["cost_per_claim"] < sc["cost_baseline"]


def test_gulf_rapid_roofing_flagged_and_routed_to_field():
    c.post("/api/scenario/start", json={"phase": "after"})
    ks = c.get("/api/contractors").json()
    assert ks[0]["name"] == "Gulf Rapid Roofing" and len(ks[0]["claims"]) == 9 and len(ks[0]["flags"]) == 4
    lanes = c.get("/api/recovery/claims").json()["lanes"]
    grr = [x for lane in lanes.values() for x in lane if x["contractor"] == "Gulf Rapid Roofing"]
    assert len(grr) == 9 and all(x["lane"] == "field" for x in grr)
    assert all(not x["flags"] for x in lanes["autopay"])
    assert c.post("/api/claims/" + grr[0]["id"] + "/autopay").status_code == 409


def test_cone_narrows():
    c.post("/api/scenario/start", json={"phase": "before"})
    wide = c.get("/api/exposure").json()["totals"]["households"]
    clock.jump(-20 * 60)
    narrow = c.get("/api/exposure").json()["totals"]["households"]
    assert narrow < wide


def test_photon_inbound_message_is_routed_and_space_remembered():
    from app import db, photon
    c.post("/api/scenario/start", json={"phase": "before"})
    msg = {"id": "msg_1", "status": "received", "createdAt": "2026-11-08T10:00:00Z", "platform": "imessage",
           "sentBy": {"kind": "human", "handle": "+17135550188", "id": "usr_h"},
           "receivedBy": {"kind": "agent", "handle": "+14155550100", "id": "usr_agent"},
           "space": {"id": "spc_1", "kind": "direct"},
           "content": {"type": "text", "format": "plain", "text": "hola"}}
    seen = set()
    assert photon.process(msg, seen) and not photon.process(msg, seen)  # de-duplicated
    assert db.get("meta", "photon:spaces")["+17135550188"] == {"space_id": "spc_1", "agent_id": "usr_agent"}
    assert _thread()[-1].startswith("LifeLine: listo")  # before landfall: opt-in ack, no triage
    own = {**msg, "id": "msg_2", "sentBy": {"kind": "agent", "handle": "+14155550100", "id": "usr_agent"}}
    assert not photon.process(own, seen)  # never answer our own messages


def test_stranger_gets_demo_disclaimer_first():
    c.post("/api/scenario/start", json={"phase": "during"})
    c.post("/api/dev/inbound", json={"phone": "+15125550777", "text": "hello?"})
    msgs = [m for m in c.get("/api/cases/H-LIVE-0777/messages").json() if m["direction"] == "out"]
    assert msgs[0]["body"].startswith("LifeLine is a HackUTD demo") and "911" in msgs[0]["body"]
    assert sum("HackUTD demo" in m["body"] for m in msgs) == 1
    c.post("/api/dev/inbound", json={"phone": "+15125550777", "text": "water coming in"})
    msgs = [m for m in c.get("/api/cases/H-LIVE-0777/messages").json() if m["direction"] == "out"]
    assert sum("HackUTD demo" in m["body"] for m in msgs) == 1  # only once
