"""Tests for shelters.py (shelters lane). Mounts the router itself in case main.py doesn't yet."""
import os
import tempfile

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ["DEMO_MODE"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app import db, shelters  # noqa: E402
from app.main import app  # noqa: E402

if not any(getattr(r, "path", "").startswith("/api/shelters") for r in app.routes):
    app.include_router(shelters.router)

c = TestClient(app)


def _routed_case(shelter_id):
    """A flooded household with oxygen, routed to this shelter (as the agent's find_shelter would)."""
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    h = next(h for h in db.all_docs("households")
             if any(m.get("oxygen") for m in h["members"]) and blocks[h["block_id"]]["flood_depth_ft"] > 0
             and h.get("phone"))
    case = db.get("cases", h["id"])
    case["shelter_id"] = shelter_id
    db.put("cases", h["id"], case)
    return h


def test_shelter_detail_accept_and_meds():
    c.post("/api/scenario/start")
    sid = db.all_docs("shelters")[0]["id"]

    d = c.get(f"/api/shelters/{sid}").json()
    assert {"intake", "roster", "meds", "supplies", "pending"} <= d.keys()
    assert len(d["intake"]) >= 5 and len(d["supplies"]) == len(shelters.SUPPLY_BASE)

    h = _routed_case(sid)
    d = c.get(f"/api/shelters/{sid}").json()
    assert any(p["case_id"] == h["id"] for p in d["pending"])
    before = d["shelter"]["occupancy"]

    assert c.post(f"/api/shelters/{sid}/accept", json={"case_id": h["id"]}).json() == {"ok": True}
    assert c.post(f"/api/shelters/{sid}/accept", json={"case_id": h["id"]}).status_code == 409

    d = c.get(f"/api/shelters/{sid}").json()
    assert d["shelter"]["occupancy"] == before + max(1, len(h["members"]))
    assert not any(p["case_id"] == h["id"] for p in d["pending"])
    assert any(r["name"] == h["name"] and r["oxygen"] for r in d["roster"])
    med = next(m for m in d["meds"] if m["name"] == h["name"])
    assert c.post(f"/api/shelters/{sid}/meds/{med['id']}/given").json() == {"ok": True}

    texts = [m["body"] for m in c.get(f"/api/cases/{h['id']}/messages").json() if m["direction"] == "out"]
    assert any(t.startswith("Good Neighbor here") for t in texts)


def test_unknown_ids_404():
    c.post("/api/scenario/start")
    assert c.get("/api/shelters/NOPE").status_code == 404
    sid = db.all_docs("shelters")[0]["id"]
    assert c.post(f"/api/shelters/{sid}/accept", json={"case_id": "NOPE"}).status_code == 404
    assert c.post(f"/api/shelters/{sid}/meds/M999/given").status_code == 404
