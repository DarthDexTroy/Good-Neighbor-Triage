from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import clock, config, db, services

app = FastAPI(title="Lifeline")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class DevInbound(BaseModel):
    phone: str
    text: str


class PhaseBody(BaseModel):
    phase: Literal["before", "during", "after"]


class StartBody(BaseModel):
    phase: Literal["before", "during", "after"] = "during"


class AssignBody(BaseModel):
    team_id: str | None = None


def _mask(phone):
    return f"…{phone[-4:]}" if phone else None


@app.get("/api/health")
def health():
    return {"ok": True, "demo_mode": config.DEMO_MODE, "nemotron": config.llm_configured(),
            "photon": config.photon_configured()}


@app.post("/api/scenario/start")
def start_scenario(body: StartBody | None = None):
    return services.start_scenario((body or StartBody()).phase)


@app.post("/api/phase")
def set_phase(body: PhaseBody):
    """Jump simulated time: before → T−72h, during → landfall (T+0), after → T+48h."""
    return services.set_phase(body.phase)


@app.post("/api/outreach/checkin_all")
def checkin_all():
    if services.meta()["phase"] == "idle":
        raise HTTPException(400, "Start the scenario first")
    return services.checkin_all()


@app.post("/api/photon/inbound")
async def photon_inbound(request: Request, background: BackgroundTasks):
    """Photon webhook. TODO(teammate): map Photon 2.0's real payload fields here (check their docs)."""
    body = await request.json()
    phone = body.get("from") or body.get("sender") or body.get("phone")
    text = body.get("text") or body.get("body") or body.get("message") or ""
    channel = body.get("channel", "sms")
    if not phone or not text:
        raise HTTPException(400, "Missing sender or text")
    background.add_task(services.handle_inbound, phone, text, channel)  # reply fast; agent runs after
    return {"ok": True}


@app.post("/api/dev/inbound")
def dev_inbound(body: DevInbound, background: BackgroundTasks):
    """Rehearsal: pretend a text arrived, without Photon."""
    if services.meta()["phase"] == "idle":
        raise HTTPException(400, "Start the scenario first")
    background.add_task(services.handle_inbound, body.phone, body.text, "sms")
    return {"ok": True}


@app.get("/api/state")
def state():
    now, m, blocks, blocks_by_id, scored = services.snapshot()
    teams = db.all_docs("teams")
    shelters = db.all_docs("shelters")
    shelters_by_id = {s["id"]: s for s in shelters}
    teams_by_id = {t["id"]: t for t in teams}

    last_in = {}
    for msg in db.all_docs("messages"):
        if msg["direction"] == "in":
            last_in[msg["household_id"]] = msg

    pins, queue = [], []
    counts = {"in_zone": 0, "contacted": 0, "replied": 0, "needs_help": 0, "assigned": 0, "confirmed_safe": 0,
              "self_reported_safe": 0, "unreachable": 0}
    for h, c, score, reasons in scored:
        if h.get("hidden_from_map"):
            continue
        b = blocks_by_id[h["block_id"]]
        in_zone = b["flood_depth_ft"] > 0
        pins.append({"id": h["id"], "lat": h["lat"], "lng": h["lng"], "score": score, "status": c["status"],
                     "name": h["name"], "in_zone": in_zone})
        if not in_zone:
            continue
        counts["in_zone"] += 1
        counts["contacted"] += c["outreach_at"] is not None
        counts["replied"] += c["last_reply_at"] is not None
        counts["unreachable"] += not h.get("phone")
        for k in ("needs_help", "assigned", "confirmed_safe", "self_reported_safe"):
            counts[k] += c["status"] == k
        if c["status"] == "confirmed_safe":
            continue
        team = None
        if c["status"] != "assigned":
            t = services.suggest_team(h, c, b, teams)
            team = {"id": t["id"], "name": t["name"]} if t else None
        msg = last_in.get(h["id"])
        queue.append({
            "id": h["id"], "name": h["name"], "address": h["address"], "phone": _mask(h.get("phone")),
            "source": h["source"], "language": h["language"], "block_id": h["block_id"], "status": c["status"],
            "score": score, "reasons": reasons, "summary": c.get("summary"),
            "last_message": msg["body"] if msg else None,
            "last_reply": clock.fmt(c["last_reply_at"]) if c["last_reply_at"] is not None else None,
            "suggested_team": team,
            "assigned_team": teams_by_id[c["assigned_team"]]["name"] if c.get("assigned_team") else None,
            "shelter": shelters_by_id[c["shelter_id"]]["name"] if c.get("shelter_id") else None,
            "sweep": m.get("sweeps", {}).get(h["block_id"]),
            "lat": h["lat"], "lng": h["lng"], "_activity": c["last_reply_at"] or -1,
        })
    queue.sort(key=lambda q: (-q["score"], -q["_activity"]))
    for i, q in enumerate(queue):
        q["rank"] = i + 1
        q.pop("_activity")

    return {
        "now": now, "clock": clock.fmt(now), "phase": m["phase"],
        "event_phase": clock.phase_of(now) if m["phase"] != "idle" else None, "outreach_at": m.get("outreach_at"),
        "sweeps": m.get("sweeps", {}),
        "config": {"demo_mode": config.DEMO_MODE, "nemotron": config.llm_configured(),
                   "photon": config.photon_configured()},
        "counts": {**counts, "flagged_blocks": sum(b["flagged"] for b in blocks)},
        "blocks": blocks, "pins": pins, "queue": queue[:60], "teams": teams, "shelters": shelters,
        "trace": _trace(),
        "audit": [{**a, "when": clock.fmt(a["t"])} for a in db.recent("audit", 20)],
    }


def _trace():
    """Real/rehearsal agent steps first-class; simulated replies kept but limited so they can't bury them."""
    rows = db.recent("trace", 600)
    live = [t for t in rows if t["engine"] != "simulated"][:40]
    sim = [t for t in rows if t["engine"] == "simulated"][:20]
    return [{**t, "when": clock.fmt(t["t"])} for t in sorted(live + sim, key=lambda t: -t["id"])]


@app.post("/api/cases/{case_id}/assign")
def assign(case_id: str, body: AssignBody):
    try:
        t = services.assign(case_id, body.team_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"team": t["name"]}


@app.post("/api/cases/{case_id}/safe")
def safe(case_id: str):
    return services.confirm_safe(case_id)


@app.post("/api/blocks/{block_id}/sweep")
def sweep(block_id: str):
    try:
        t = services.sweep(block_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"team": t["name"]}


@app.get("/api/claims")
def claims():
    return services.claims_view()


@app.get("/api/cases/{case_id}/messages")
def case_messages(case_id: str):
    return [{**m, "when": clock.fmt(m["t"])} for m in db.all_docs("messages") if m.get("household_id") == case_id]
