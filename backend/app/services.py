"""Case operations shared by the API, the agent tools and the simulator."""
from . import claims as claims_mod
from . import clock, db, geo, messenger, scoring, seed, silence

CHECKIN_TEXT = {
    "en": "State Farm Lifeline: flooding reported near you. Reply SAFE, HELP, or tell us what you need. "
          "If in immediate danger call 911.",
    "es": "State Farm Lifeline: se reportan inundaciones cerca de usted. Responda BIEN, AYUDA, o díganos qué "
          "necesita. Si está en peligro inmediato llame al 911.",
}


def audit(actor, action, case_id=None):
    db.append("audit", {"t": clock.now(), "actor": actor, "action": action, "case_id": case_id})


def meta():
    return db.get("meta", "scenario") or {"id": "scenario", "phase": "idle", "outreach_at": None, "sweeps": {}}


def save_meta(m):
    db.put("meta", "scenario", m)


# ---------- scenario ----------

def start_scenario(phase: str = "during"):
    from . import business, simulator
    simulator.stop()
    business.stop_sim()
    db.reset()
    stats = seed.seed()
    clock.start(clock.PHASE_AT[phase])
    business.backfill_autopay()
    save_meta({"id": "scenario", "phase": "flood", "outreach_at": None, "sweeps": {}})
    audit("system", f"Storm scenario started at {clock.fmt(clock.now())}: "
                    f"{stats['in_zone']} households in the forecast flood zone")
    return {**stats, "now": clock.now(), "event_phase": clock.phase_of(clock.now())}


def set_phase(phase: str):
    """Jump simulated time to the start of a phase: before = T−72h, during = landfall, after = T+48h."""
    if meta()["phase"] == "idle":
        start_scenario(phase)
    else:
        clock.jump(clock.PHASE_AT[phase])
    audit("cat team", f"Jumped to {phase} phase ({clock.fmt(clock.now())})")
    return {"now": clock.now(), "clock": clock.fmt(clock.now()), "phase": phase}


def checkin_all():
    from . import simulator
    now = clock.now()
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    sent = []
    for h in db.all_docs("households"):
        if h.get("hidden_from_map") or not h.get("phone") or blocks[h["block_id"]]["flood_depth_ft"] == 0:
            continue
        case = db.get("cases", h["id"])
        if case["outreach_at"] is not None:
            continue
        messenger.deliver(h, CHECKIN_TEXT[h.get("language", "en")])
        case["outreach_at"] = now
        if case["status"] == "unreached":
            case["status"] = "contacted"
        db.put("cases", h["id"], case)
        sent.append(h["id"])
    m = meta()
    m["outreach_at"] = m["outreach_at"] if m["outreach_at"] is not None else now
    save_meta(m)
    audit("cat team", f"Check-in sent to {len(sent)} households by SMS/iMessage")
    simulator.start(sent)
    return {"sent": len(sent)}


# ---------- households / messages ----------

def find_or_create_household(phone: str) -> dict:
    for h in db.all_docs("households"):
        if h.get("phone") == phone:
            return h
    # Deepest-water block other than the planted quiet one, so the live demo case is clearly in danger.
    b = max((x for x in db.all_docs("blocks") if x["id"] != seed.FLAGGED_BLOCK), key=lambda x: x["flood_depth_ft"])
    s, w, n, e = b["bounds"]
    hid = f"H-LIVE-{phone[-4:]}"
    h = {"id": hid, "name": f"Live texter …{phone[-4:]}", "address": "1200 Bayou St (live demo)",
         "lat": round((s + n) / 2, 6), "lng": round((w + e) / 2, 6), "block_id": b["id"], "phone": phone,
         "language": "en", "source": "live", "consent": True, "policy_number": None, "members": [], "pets": False}
    db.put("households", hid, h)
    db.put("cases", hid, {"id": hid, "household_id": hid, "status": "contacted", "needs": {}, "danger": [],
                          "outreach_at": None, "last_reply_at": None, "assigned_team": None, "shelter_id": None})
    audit("system", f"New household created from an inbound text ({phone[-4:]})", hid)
    return h


def record_inbound(household, text, channel="sms", lat=None, lng=None):
    now = clock.now()
    db.append("messages", {"household_id": household["id"], "direction": "in", "channel": channel,
                           "body": text, "t": now, "lat": lat, "lng": lng})
    case = db.get("cases", household["id"])
    case["last_reply_at"] = now
    if case["status"] in ("unreached",):
        case["status"] = "contacted"
    db.put("cases", household["id"], case)


def handle_inbound(phone, text, channel="sms", lat=None, lng=None, use_llm=True):
    from . import agent, business
    h = find_or_create_household(phone)
    record_inbound(h, text, channel, lat, lng)
    # Before landfall, "1" / "2" / "3" / a photo confirm a pre-storm action instead of starting triage.
    if clock.phase_of(clock.now()) == "before" and business.is_action_reply(h, text):
        return {"engine": "actions", "confirmed": business.handle_action_reply(db.get("households", h["id"]), text)}
    return agent.run(h["id"], phone, text, use_llm=use_llm)


# ---------- scoring ----------

def score_case(case, h, block, now, flagged_ids):
    needs = scoring.effective_needs(h, case)
    return scoring.compute(needs, block["flood_depth_ft"], block["power_out"], case["status"], case.get("danger", []),
                           case.get("outreach_at"), case.get("last_reply_at"), now,
                           reachable=bool(h.get("phone")), in_flagged_block=h["block_id"] in flagged_ids)


def snapshot():
    """Everything computed fresh: blocks with silence stats, and every case scored."""
    now = clock.now()
    blocks = db.all_docs("blocks")
    households = db.all_docs("households")
    cases = {c["id"]: c for c in db.all_docs("cases")}
    m = meta()
    stats = silence.block_stats(blocks, households, cases, m.get("outreach_at"), now)
    flagged = {b["id"] for b in stats if b["flagged"]}
    blocks_by_id = {b["id"]: b for b in stats}
    scored = []
    for h in households:
        c = cases[h["id"]]
        s, reasons = score_case(c, h, blocks_by_id[h["block_id"]], now, flagged)
        scored.append((h, c, s, reasons))
    return now, m, stats, blocks_by_id, scored


def score_one(household_id):
    now, _, _, blocks_by_id, scored = snapshot()
    for h, c, s, reasons in scored:
        if h["id"] == household_id:
            return s, reasons
    return 0, []


# ---------- teams / shelters ----------

def _needs_medical(h, c):
    n = scoring.effective_needs(h, c)
    return n["oxygen"] or n["dialysis"] or (n["insulin_hours_left"] is not None and n["insulin_hours_left"] < 24) \
        or "medical_emergency" in c.get("danger", [])


def suggest_team(h, c, block, teams):
    if _needs_medical(h, c) and block["flood_depth_ft"] < 2:
        want = "medical"
    elif block["flood_depth_ft"] >= 2:
        want = "boat"
    else:
        want = "supply"
    free = [t for t in teams if t["status"] == "available"]
    pool = [t for t in free if t["type"] == want] or free
    if not pool:
        return None
    return min(pool, key=lambda t: geo.miles(h["lat"], h["lng"], t["lat"], t["lng"]))


def find_shelter(h, c):
    n = scoring.effective_needs(h, c)
    best = None
    for s in db.all_docs("shelters"):
        if s["occupancy"] >= s["capacity"]:
            continue
        if n["mobility"] and not s["wheelchair"]:
            continue
        if n["oxygen"] and not s["backup_power"]:
            continue
        if n["infant"] and not s["infant_supplies"]:
            continue
        d = geo.miles(h["lat"], h["lng"], s["lat"], s["lng"])
        if best is None or d < best[0]:
            best = (d, s)
    return best[1] if best else None


def assign(case_id, team_id=None, actor="cat team"):
    h = db.get("households", case_id)
    c = db.get("cases", case_id)
    block = db.get("blocks", h["block_id"])
    teams = db.all_docs("teams")
    team = next((t for t in teams if t["id"] == team_id), None) if team_id else suggest_team(h, c, block, teams)
    if team is None or team["status"] != "available":
        raise ValueError("No available team")
    team["status"], team["case_id"] = "busy", case_id
    db.put("teams", team["id"], team)
    c["status"], c["assigned_team"] = "assigned", team["id"]
    db.put("cases", case_id, c)
    audit(actor, f"Human approved dispatch: {team['name']} → {h['name']}", case_id)
    return team


def confirm_safe(case_id, actor="cat team"):
    h = db.get("households", case_id)
    c = db.get("cases", case_id)
    if c.get("assigned_team"):
        t = db.get("teams", c["assigned_team"])
        t["status"], t["case_id"] = "available", None
        db.put("teams", t["id"], t)
    c["status"] = "confirmed_safe"
    db.put("cases", case_id, c)
    audit(actor, f"Confirmed safe: {h['name']}", case_id)
    claim = None
    if h.get("policy_number") and not db.get("claims", f"C-{case_id}"):
        claim = {"id": f"C-{case_id}", "household_id": case_id, "status": "draft", "planted": None}
        db.put("claims", claim["id"], claim)
        audit("system", "Claim draft opened with verified timeline", case_id)
    return {"claim_id": claim["id"] if claim else None}


def sweep(block_id, actor="cat team"):
    b = db.get("blocks", block_id)
    boats = [t for t in db.all_docs("teams") if t["status"] == "available" and t["type"] == "boat"]
    boats = boats or [t for t in db.all_docs("teams") if t["status"] == "available"]
    if not boats:
        raise ValueError("No available team")
    team = min(boats, key=lambda t: geo.miles(b["center"][0], b["center"][1], t["lat"], t["lng"]))
    team["status"], team["case_id"] = "busy", f"sweep:{block_id}"
    db.put("teams", team["id"], team)
    m = meta()
    m.setdefault("sweeps", {})[block_id] = team["name"]
    save_meta(m)
    audit(actor, f"Door-to-door sweep: {team['name']} → quiet block {block_id}")
    return team


# ---------- claims ----------

def claims_view():
    households = {h["id"]: h for h in db.all_docs("households")}
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    all_claims = [c for c in db.all_docs("claims") if c.get("status") == "draft"]  # During-phase drafts
    out = []
    for c in all_claims:
        h = households[c["household_id"]]
        out.append({**c, "name": h["name"], "address": h["address"], "policy_number": h.get("policy_number"),
                    "flood_depth_ft": blocks[h["block_id"]]["flood_depth_ft"],
                    "flags": claims_mod.fraud_flags(c, households, blocks, all_claims),
                    "timeline": claims_mod.timeline(h["id"])})
    return sorted(out, key=lambda c: (len(c["flags"]) == 0, c["id"]))
