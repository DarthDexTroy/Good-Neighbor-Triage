import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DEMO_MODE"] = "0"
os.environ["NVIDIA_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import extract, scoring, silence  # noqa: E402
from app.main import app  # noqa: E402

NO_NEEDS = {"oxygen": False, "dialysis": False, "insulin_hours_left": None, "infant": False,
            "elderly": False, "mobility": False, "power_out": False}


# ---------- scoring ----------

def test_oxygen_with_power_out_scores_high_with_reasons():
    s, reasons = scoring.compute({**NO_NEEDS, "oxygen": True}, 4.0, True, "needs_help", ["water_rising"],
                                 0, 5, 10)
    assert s == 20 + 30 + 30
    assert any("Oxygen" in r for r in reasons)


def test_more_messages_never_add_points():
    a = scoring.compute(NO_NEEDS, 3.0, True, "needs_help", ["asked_help"], 0, 5, 10)
    b = scoring.compute(NO_NEEDS, 3.0, True, "needs_help", ["asked_help", "asked_help"], 0, 9, 10)
    assert a[0] == b[0]


def test_silence_points_grow_and_cap():
    s1, _ = scoring.compute(NO_NEEDS, 2.0, True, "contacted", [], 0, None, 60)
    s2, _ = scoring.compute(NO_NEEDS, 2.0, True, "contacted", [], 0, None, 600)
    assert s1 == 10 + 4 and s2 == 10 + 20


def test_self_reported_safe_capped_and_confirmed_safe_zero():
    s, _ = scoring.compute({**NO_NEEDS, "elderly": True}, 5.0, True, "self_reported_safe", [], 0, 1, 2)
    assert s == 10
    assert scoring.compute(NO_NEEDS, 5.0, True, "confirmed_safe", [], 0, 1, 2)[0] == 0


def test_assigned_drops_score():
    s, _ = scoring.compute({**NO_NEEDS, "oxygen": True}, 5.0, True, "assigned", [], 0, 1, 2)
    assert s == 25 + 30 - 30


# ---------- extraction ----------

def test_extract_judge_message():
    ex = extract.extract("water coming in, my mom is on oxygen and the power is out")
    assert ex["needs"].get("oxygen") and ex["needs"].get("power_out")
    assert "water_rising" in ex["danger"] and not ex["self_reported_safe"]


def test_extract_safe_and_spanish():
    assert extract.extract("SAFE")["self_reported_safe"]
    ex = extract.extract("Necesitamos ayuda, el agua está subiendo y mi abuela usa silla de ruedas")
    assert ex["language"] == "es" and ex["needs"].get("mobility") and "water_rising" in ex["danger"]


# ---------- silence map ----------

def test_quiet_block_is_flagged():
    blocks = [{"id": "A", "flood_depth_ft": 5.0, "svi": 0.9}, {"id": "B", "flood_depth_ft": 5.0, "svi": 0.3}]
    hh = [{"id": f"a{i}", "block_id": "A"} for i in range(10)] + [{"id": f"b{i}", "block_id": "B"} for i in range(10)]
    cases = {h["id"]: {"last_reply_at": (1 if h["block_id"] == "B" and int(h["id"][1:]) < 7 else None)} for h in hh}
    cases["a0"]["last_reply_at"] = 1
    out = {b["id"]: b for b in silence.block_stats(blocks, hh, cases, outreach_at=0, now=60)}
    assert out["A"]["flagged"] and not out["B"]["flagged"]


# ---------- end to end (rule-based agent, no network) ----------

def test_full_flow():
    c = TestClient(app)
    stats = c.post("/api/scenario/start").json()
    assert stats["in_zone"] > 250
    assert c.post("/api/outreach/checkin_all").json()["sent"] > 200

    c.post("/api/dev/inbound", json={"phone": "+15125550199",
                                     "text": "water coming in, my mom is on oxygen and the power is out"})
    st = c.get("/api/state").json()
    live = next(q for q in st["queue"] if q["id"] == "H-LIVE-0199")
    assert live["score"] >= 70 and live["status"] == "needs_help"
    assert live["rank"] <= 3, [(q["name"], q["score"]) for q in st["queue"][:5]]
    tools = [t["tool"] for t in st["trace"] if t["household_id"] == "H-LIVE-0199"]
    assert {"lookup_household", "get_hazard", "update_needs", "compute_score", "send_reply"} <= set(tools)

    assert c.post(f"/api/cases/{live['id']}/assign", json={}).status_code == 200
    assert c.post(f"/api/cases/{live['id']}/safe").status_code == 200

    jenkins = c.post("/api/cases/H-JENKINS/safe").json()
    assert jenkins == {"claim_id": None}  # not a policyholder

    claims = c.get("/api/claims").json()
    flagged = [x for x in claims if x["flags"]]
    assert any("outside the flood zone" in f for x in flagged for f in x["flags"])
    assert any("miles from the property" in f for x in flagged for f in x["flags"])
    assert any("Same address" in f for x in flagged for f in x["flags"])
