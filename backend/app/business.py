"""Before / After phases: forecast cone, exposure, action texts, claim lanes, auto-pay, contractor fraud, scorecard.

Every number here comes from fake data and assumptions that are labeled as such (see ASSUMPTIONS).
"""
import random
import re
import statistics
import threading
import time

from . import claims as claims_mod
from . import clock, config, db, geo, messenger, seed

# ---------- assumptions (all made up, shown on screen) ----------

P_WIND = 0.35                 # chance of wind damage for a home in the cone
SHUTTER_AVOIDED = 8000        # avg interior water/glass damage avoided by shutters
PHOTO_SAVING = 350            # ~3 fewer adjuster hours x ~$115/h per later claim
ADJUSTER_RATE = 115           # $/hour
HOURS = {"autopay": 0.25, "desk": 4, "field": 10}
PROJECTED_DAYS = {"autopay": 0.5, "desk": 6, "field": 14}
BASELINE_CYCLE_DAYS = 30
BASELINE_COST = 1100
CAPACITY = {"desk": {"adjusters": 12, "per_day": 5}, "field": {"adjusters": 6, "per_day": 2}}
AUTOPAY_MAX = 2500
FIELD_MIN = 25000

ASSUMPTIONS = {
    "car": "Car moved: car value x P(flood at address). Assumes an average flooded car is a total loss.",
    "shutters": f"Windows shuttered: ${SHUTTER_AVOIDED:,} x P(wind damage = {P_WIND}). "
                "Average interior water/glass damage avoided.",
    "photos": f"Pre-storm photos: ${PHOTO_SAVING} handling cost saved per later claim "
              f"(~3 fewer adjuster hours x ~${ADJUSTER_RATE}/h).",
    "meds": "Medication/evacuation ready: no dollar value. Counted as high-risk people prepared.",
    "cycle_time": f"Median days from first notice of loss to payment. Unpaid claims use projected days per lane "
                  f"(auto-pay {PROJECTED_DAYS['autopay']}, desk {PROJECTED_DAYS['desk']}, field "
                  f"{PROJECTED_DAYS['field']}). Baseline {BASELINE_CYCLE_DAYS} days is assumed.",
    "cost_per_claim": f"Adjuster hours per lane (auto-pay {HOURS['autopay']}h, desk {HOURS['desk']}h, field "
                      f"{HOURS['field']}h) x ${ADJUSTER_RATE}/h. Baseline ${BASELINE_COST:,} is assumed.",
    "expected_loss": "home value x P(damage) x damage share + sum of car value x P(flood). P(damage) and "
                     "P(flood) come from the block's forecast flood depth. Damage share 0.05 minor / 0.25 major "
                     "/ 0.6 total.",
}

ACTION_LABEL = {"car": "car moved", "shutters": "windows shuttered", "meds": "meds ready", "photos": "photos sent"}
ACTION_LABEL_ES = {"car": "carro movido", "shutters": "ventanas protegidas", "meds": "medicinas listas",
                   "photos": "fotos recibidas"}
CODE = {"1": "car", "2": "shutters", "3": "meds"}

# ---------- forecast cone ----------

STORM_START = (29.62, -95.22)   # storm position at T−72h (southeast, in the Gulf)
GRID_CENTER = (seed.CENTER_LAT, seed.CENTER_LNG)


def cone(now):
    """Fake forecast cone. It narrows as landfall gets closer: T−72h wide, T−48h narrower, T−24h narrowest."""
    half = 0.026 if now < -48 * 60 else 0.017 if now < -24 * 60 else 0.012
    (la0, ln0), (la1, ln1) = STORM_START, GRID_CENTER
    dla, dln = la1 - la0, ln1 - ln0
    end = (la1 + dla, ln1 + dln)
    norm = (dla ** 2 + dln ** 2) ** 0.5
    px, py = -dln / norm, dla / norm  # unit perpendicular
    left, right = [], []
    for i in range(9):
        t = i / 8
        cla, cln = la0 + (end[0] - la0) * t, ln0 + (end[1] - ln0) * t
        w = 0.004 + (half * 2 - 0.004) * t
        left.append([round(cla + px * w, 5), round(cln + py * w, 5)])
        right.append([round(cla - px * w, 5), round(cln - py * w, 5)])
    return left + right[::-1]


def in_polygon(lat, lng, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


# ---------- exposure ----------

def p_flood(depth):
    return min(0.95, depth / 6)


def p_damage(depth):
    return min(0.95, 0.10 + depth / 7)


def damage_share(depth):
    return 0.05 if depth < 1.5 else 0.25 if depth < 3.5 else 0.6


def expected_loss(h, depth):
    home = h.get("home", {}).get("value", 0) * p_damage(depth) * damage_share(depth)
    cars = sum(v["value"] for v in h.get("vehicles", [])) * p_flood(depth)
    return round(home + cars)


def _vulnerable(h):
    return any(m.get("oxygen") or m.get("mobility") or m.get("age", 0) >= 75 for m in h.get("members", []))


def exposure():
    now = clock.now()
    poly = cone(now)
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    homes, totals = [], {"policies": 0, "insured_value": 0, "expected_loss": 0, "vulnerable": 0, "households": 0}
    for h in db.all_docs("households"):
        if h.get("hidden_from_map") or not in_polygon(h["lat"], h["lng"], poly):
            continue
        depth = blocks[h["block_id"]]["flood_depth_ft"]
        el = expected_loss(h, depth)
        policy = bool(h.get("policy_number"))
        totals["households"] += 1
        totals["vulnerable"] += _vulnerable(h)
        if policy:
            totals["policies"] += 1
            totals["insured_value"] += h["home"]["value"] + sum(v["value"] for v in h.get("vehicles", []))
            totals["expected_loss"] += el
        homes.append({"id": h["id"], "name": h["name"], "lat": h["lat"], "lng": h["lng"], "policy": policy,
                      "expected_loss": el, "forecast_depth_ft": depth, "vulnerable": _vulnerable(h),
                      "demo": h["id"] == seed.REYES_ID})
    return {"now": now, "clock": clock.fmt(now), "cone": poly, "totals": totals, "homes": homes,
            "formula": ASSUMPTIONS["expected_loss"]}


# ---------- action texts (Before) ----------

def _actions_for(h, depth):
    acts = []
    if h.get("vehicles") and p_flood(depth) > 0:
        acts.append("car")
    if not h.get("home", {}).get("shutters"):
        acts.append("shutters")
    if any(m.get("oxygen") or m.get("dialysis") or "insulin_hours_left" in m for m in h.get("members", [])):
        acts.append("meds")
    acts.append("photos")
    return acts


def action_text(h, acts):
    es = h.get("language") == "es"
    lines = ["Good Neighbor: una tormenta llega en ~48 horas." if es else
             "Good Neighbor here: a storm is expected in ~48 hours."]
    for a in acts:
        lines.append({
            "car": "1) Mueva su carro a un lugar alto. Responda 1 cuando lo haga." if es else
                   "1) Move your car to higher ground. Reply 1 when done.",
            "shutters": "2) Cubra o proteja sus ventanas. Responda 2 cuando lo haga." if es else
                        "2) Board or shutter your windows. Reply 2 when done.",
            "meds": "3) Surta sus medicinas y cargue sus aparatos. Si usa oxígeno, planee evacuar. Responda 3 "
                    "cuando esté listo." if es else
                    "3) Refill medication and charge your devices. If you use oxygen, plan to evacuate. "
                    "Reply 3 when ready.",
            "photos": "Envíenos 4–6 fotos de su casa y carro hoy. Así cualquier reclamo es más rápido." if es else
                      "Text us 4–6 photos of your home and car today. It makes any claim faster.",
        }[a])
    return "\n".join(lines)


_stop = threading.Event()
_thread = None


def send_actions():
    """Personalized action texts to every policyholder in the cone. Moves the clock to T−48h if earlier."""
    from . import services
    if clock.now() < -48 * 60:
        clock.jump(-48 * 60)
    now = clock.now()
    poly = cone(now)
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    sent = []
    for h in db.all_docs("households"):
        if (h.get("hidden_from_map") or not h.get("phone") or not h.get("policy_number")
                or not in_polygon(h["lat"], h["lng"], poly) or h.get("actions")):
            continue
        acts = _actions_for(h, blocks[h["block_id"]]["flood_depth_ft"])
        h["actions"] = [{"type": a, "sent_t": now, "confirmed_t": None} for a in acts]
        db.put("households", h["id"], h)
        messenger.deliver(h, action_text(h, acts))
        sent.append(h["id"])
    services.audit("cat team", f"Pre-landfall action texts sent to {len(sent)} policyholders")
    _start_sim([x for x in sent if x != seed.REYES_ID])
    return {"sent": len(sent), "now": now}


def is_action_reply(h, text):
    if not any(a["confirmed_t"] is None for a in h.get("actions", [])):
        return False
    t = text.lower().strip()
    return bool(re.fullmatch(r"[\s,.y&+and]*([1-3][\s,.y&+and]*)+", t)) or "foto" in t or "photo" in t


def handle_action_reply(h, text):
    """Replies 1/2/3 confirm car/shutters/meds; a photo (or the word photo/foto) confirms photos."""
    now = clock.now()
    t = text.lower()
    types = {CODE[d] for d in re.findall(r"[1-3]", t)}
    if "foto" in t or "photo" in t:
        types.add("photos")
        h["photos"] = (h.get("photos") or []) + [
            {"phase": "pre", "url": "/photos/house-pre.svg", "label": f"Home (texted in at {clock.fmt(now)})"}]
    done = []
    for a in h.get("actions", []):
        if a["type"] in types and a["confirmed_t"] is None:
            a["confirmed_t"] = now
            done.append(a["type"])
    db.put("households", h["id"], h)
    es = h.get("language") == "es"
    labels = ACTION_LABEL_ES if es else ACTION_LABEL
    if done:
        msg = ("¡Gracias! Marcamos: " if es else "Thanks! Marked done: ") + ", ".join(labels[d] for d in done) + "."
    else:
        msg = "Ya lo teníamos, gracias." if es else "Already marked, thanks."
    messenger.deliver(h, msg)
    from . import services
    if done:
        services.audit("resident", f"Confirmed: {', '.join(ACTION_LABEL[d] for d in done)}", h["id"])
    return done


def _sim(household_ids):
    """Demo mode: other policyholders confirm some of their actions over ~20 real seconds."""
    from . import services
    rng = random.Random(23)
    plan = []
    for hid in household_ids:
        h = db.get("households", hid)
        for a in h["actions"]:
            if rng.random() < {"car": 0.55, "shutters": 0.35, "meds": 0.7, "photos": 0.45}[a["type"]]:
                plan.append((rng.uniform(1.5, 20), hid, a["type"]))
    plan.sort()
    t0 = time.time()
    for delay, hid, typ in plan:
        wait = delay - (time.time() - t0)
        if wait > 0 and _stop.wait(wait):
            return
        if _stop.is_set():
            return
        try:
            h = db.get("households", hid)
            text = "photo" if typ == "photos" else {v: k for k, v in CODE.items()}[typ]
            services.record_inbound(h, text if typ != "photos" else "[photo]", "sms")
            handle_action_reply(db.get("households", hid), text)
        except Exception as e:
            print("action sim error:", e)


def _start_sim(ids):
    global _thread
    if not config.DEMO_MODE:
        return
    stop_sim()
    _stop.clear()
    _thread = threading.Thread(target=_sim, args=(ids,), daemon=True)
    _thread.start()


def stop_sim():
    _stop.set()
    if _thread is not None and _thread.is_alive():
        _thread.join(timeout=2)


def actions_summary():
    by_type = {k: {"sent": 0, "confirmed": 0} for k in ACTION_LABEL}
    households = 0
    for h in db.all_docs("households"):
        if h.get("actions"):
            households += 1
        for a in h.get("actions", []):
            by_type[a["type"]]["sent"] += 1
            by_type[a["type"]]["confirmed"] += a["confirmed_t"] is not None
    return {"households": households, "by_type": by_type}


# ---------- After: lanes, auto-pay, contractor fraud ----------

def contractor_flags(all_claims, contractors_by_id, households_by_id):
    """Four contractor rules (spec §6.3). Returns {claim_id: [flag, ...]}."""
    out = {c["id"]: [] for c in all_claims}
    by_k = {}
    for c in all_claims:
        if c.get("contractor_id"):
            by_k.setdefault(c["contractor_id"], []).append(c)
    medians = {}
    for label in ("minor", "major", "total"):
        ests = [c["estimate"] for c in all_claims if c.get("damage_label") == label and c.get("estimate")]
        medians[label] = statistics.median(ests) if ests else None

    for kid, cs in by_k.items():
        k = contractors_by_id[kid]
        pts = [(households_by_id[c["household_id"]]["lat"], households_by_id[c["household_id"]]["lng"]) for c in cs]
        spread = max((geo.miles(a[0], a[1], b[0], b[1]) for a in pts for b in pts), default=0)
        early = [c for c in cs if c.get("aob_signed_t") is not None and c["aob_signed_t"] < c["fnol_t"]]
        shared = len(cs) >= 5 and (spread > 20 or early)
        for c in cs:
            f = out[c["id"]]
            if shared:
                f.append(f"Shared contractor: {k['name']} is on {len(cs)} claims"
                         + (", listed before the damage was reported" if early else f" {spread:.0f} mi apart"))
            med = medians.get(c.get("damage_label"))
            if med and c["estimate"] > 1.8 * med:
                f.append(f"Inflated estimate: ${c['estimate']:,} is {c['estimate'] / med:.1f}x the median "
                         f"for {c['damage_label']} damage")
            if c.get("aob_signed_t") is not None and c["aob_signed_t"] - seed.LANDFALL < 24 * 60:
                f.append(f"Fast assignment of benefits: signed {c['aob_signed_t'] / 60:.0f}h after landfall")
            if not k["licensed"]:
                f.append(f"Unlicensed contractor: {k['name']} is not on the license list")
    return out


def lane_for(c, flags, has_pre_photos):
    if c["damage_label"] == "total" or c["estimate"] > FIELD_MIN or flags:
        return "field"
    if c["estimate"] <= AUTOPAY_MAX and has_pre_photos and c["damage_label"] == "minor":
        return "autopay"
    return "desk"


def _lane_reason(lane, c, flags, pre):
    if lane == "autopay":
        return f"${c['estimate']:,} ≤ ${AUTOPAY_MAX:,}, minor damage, pre-storm photos, no flags"
    if lane == "field":
        if flags:
            return f"{len(flags)} flag(s): needs an in-person look (flags never deny a claim)"
        return "Total loss" if c["damage_label"] == "total" else f"Estimate over ${FIELD_MIN:,}"
    why = []
    if c["damage_label"] != "minor":
        why.append(f"{c['damage_label']} damage")
    if c["estimate"] > AUTOPAY_MAX:
        why.append(f"${c['estimate']:,} > ${AUTOPAY_MAX:,}")
    if not pre:
        why.append("no pre-storm photos")
    return "Desk review: " + ", ".join(why)


def routed_claims(include_future=False):
    now = clock.now()
    households = {h["id"]: h for h in db.all_docs("households")}
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    contractors = {k["id"]: k for k in db.all_docs("contractors")}
    all_claims = [c for c in db.all_docs("claims") if c.get("fnol_t") is not None]
    kflags = contractor_flags(all_claims, contractors, households)
    out = []
    for c in all_claims:
        if not include_future and c["fnol_t"] > now:
            continue
        h = households[c["household_id"]]
        flags = claims_mod.fraud_flags(c, households, blocks, all_claims) + kflags[c["id"]]
        pre = any(p["phase"] == "pre" for p in h.get("photos", []))
        lane = lane_for(c, flags, pre)
        out.append({**c, "name": h["name"], "address": h["address"], "language": h.get("language"),
                    "policy_number": h.get("policy_number"), "flags": flags, "lane": lane,
                    "lane_reason": _lane_reason(lane, c, flags, pre), "has_pre_photos": pre,
                    "photos": [p for p in h.get("photos", []) if p["phase"] == "pre"][:2]
                              + [p for p in c.get("photos", []) if p["phase"] == "post"],
                    "contractor": contractors[c["contractor_id"]]["name"] if c.get("contractor_id") else None,
                    "fnol_when": clock.fmt(c["fnol_t"]),
                    "paid_when": clock.fmt(c["paid_t"]) if c.get("paid_t") is not None else None,
                    "demo": h["id"] == seed.REYES_ID})
    return out


def recovery_claims():
    cs = routed_claims()
    lanes = {"autopay": [], "desk": [], "field": []}
    for c in sorted(cs, key=lambda c: (not c["demo"], c["paid_t"] is not None, -c["fnol_t"])):
        lanes[c["lane"]].append(c)
    cap = {}
    for lane in ("desk", "field"):
        open_n = sum(1 for c in lanes[lane] if c["paid_t"] is None)
        per_day = CAPACITY[lane]["adjusters"] * CAPACITY[lane]["per_day"]
        cap[lane] = {"adjusters": CAPACITY[lane]["adjusters"], "open": open_n,
                     "backlog_days": round(open_n / per_day, 1)}
    return {"now": clock.now(), "lanes": lanes, "capacity": cap,
            "rule": f"Auto-pay: estimate ≤ ${AUTOPAY_MAX:,} AND pre-storm photos AND minor damage AND zero flags. "
                    f"Field: total loss OR > ${FIELD_MIN:,} OR any flag. Desk: everything else."}


def pay(claim_id, actor="auto-pay rule", notify=True, at=None):
    c = next((x for x in routed_claims(include_future=True) if x["id"] == claim_id), None)
    if c is None:
        raise KeyError(claim_id)
    if c["lane"] != "autopay":
        raise ValueError(f"Claim is in the {c['lane']} lane, not auto-pay")
    raw = db.get("claims", claim_id)
    if raw.get("paid_t") is not None:
        return raw
    raw["paid_t"] = clock.now() if at is None else at
    raw["paid_amount"] = raw["estimate"]
    raw["status"] = "paid"
    db.put("claims", claim_id, raw)
    if notify:
        h = db.get("households", raw["household_id"])
        amt = f"${raw['paid_amount']:,}"
        messenger.deliver(h, f"Good Neighbor: su reclamo #{raw['claim_number']} fue aprobado. {amt} va en camino."
                          if h.get("language") == "es" else
                          f"Good Neighbor here: your claim #{raw['claim_number']} is approved. {amt} is on the way.")
        from . import services
        services.audit(actor, f"Auto-paid {raw['claim_number']} ({amt})", h["id"])
    return raw


def run_autopay():
    paid = []
    for c in routed_claims():
        if c["lane"] == "autopay" and c["paid_t"] is None:
            pay(c["id"])
            paid.append(c["id"])
    return {"paid": len(paid), "claim_ids": paid}


def backfill_autopay():
    """Seeded history: auto-pay claims filed well before T+48h were already paid a few hours after filing.
    The Reyes claim and anything filed in the last few hours are left for the live demo."""
    rng = random.Random(5)
    for c in routed_claims(include_future=True):
        if c["lane"] == "autopay" and not c["demo"] and c["fnol_t"] < 2600:
            pay(c["id"], notify=False, at=round(c["fnol_t"] + rng.uniform(90, 300), 1))


def contractors_view():
    cs = routed_claims(include_future=True)
    out = []
    for k in db.all_docs("contractors"):
        mine = [c for c in cs if c.get("contractor_id") == k["id"]]
        flags = sorted({f.split(":")[0] for c in mine for f in c["flags"] if ":" in f
                        and f.split(":")[0] in ("Shared contractor", "Inflated estimate", "Fast assignment of benefits",
                                                "Unlicensed contractor")})
        out.append({**k, "flags": flags, "claims": [{"id": c["id"], "claim_number": c["claim_number"],
                                                     "name": c["name"], "estimate": c["estimate"]} for c in mine],
                    "estimate_total": sum(c["estimate"] for c in mine)})
    return sorted(out, key=lambda k: (-len(k["flags"]), -len(k["claims"])))


def warn_scams():
    from . import services
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    sent = 0
    for h in db.all_docs("households"):
        if h.get("hidden_from_map") or not h.get("phone") or not h.get("policy_number"):
            continue
        if blocks[h["block_id"]]["flood_depth_ft"] == 0:
            continue
        messenger.deliver(h, "Good Neighbor: las estafas de reparación son comunes después de una tormenta. Verifique "
                             "licencias y nunca ceda sus beneficios de seguro en la puerta. ¿Preguntas? Responda AYUDA."
                          if h.get("language") == "es" else
                          "Good Neighbor here: storm repair scams are common. Verify licenses, and never sign over "
                          "your insurance benefits at the door. Questions? Reply HELP.")
        sent += 1
    services.audit("cat team", f"Scam warning sent to {sent} policyholders in damaged blocks")
    return {"sent": sent}


# ---------- scorecard ----------

def scorecard():
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    households = db.all_docs("households")
    avoided = {"car": 0, "shutters": 0, "photos": 0}
    prepared = 0
    for h in households:
        depth = blocks[h["block_id"]]["flood_depth_ft"]
        for a in h.get("actions", []):
            if a["confirmed_t"] is None:
                continue
            if a["type"] == "car":
                avoided["car"] += sum(v["value"] for v in h.get("vehicles", [])) * p_flood(depth)
            elif a["type"] == "shutters":
                avoided["shutters"] += SHUTTER_AVOIDED * P_WIND
            elif a["type"] == "meds":
                prepared += 1

    cs = routed_claims()
    avoided["photos"] = PHOTO_SAVING * sum(1 for c in cs if c["has_pre_photos"])
    avoided = {k: round(v) for k, v in avoided.items()}

    days = []
    for c in cs:
        if c["paid_t"] is not None:
            days.append((c["paid_t"] - c["fnol_t"]) / 1440)
        else:
            days.append(PROJECTED_DAYS[c["lane"]])
    cycle = round(statistics.median(days), 1) if days else None
    cost = round(sum(HOURS[c["lane"]] * ADJUSTER_RATE for c in cs) / len(cs)) if cs else None

    policy_ids = {h["id"] for h in households if h.get("policy_number") and not h.get("hidden_from_map")}
    replied = {m["household_id"] for m in db.all_docs("messages") if m["direction"] == "in"} & policy_ids
    return {
        "avoided": sum(avoided.values()), "avoided_by_type": avoided, "prepared_high_risk": prepared,
        "cycle_time_days": cycle, "cycle_baseline_days": BASELINE_CYCLE_DAYS,
        "cost_per_claim": cost, "cost_baseline": BASELINE_COST, "claims": len(cs),
        "paid": sum(1 for c in cs if c["paid_t"] is not None),
        "reached_pct": round(100 * len(replied) / len(policy_ids)) if policy_ids else 0,
        "fraud_held": sum(c["estimate"] for c in cs if c["flags"]),
        "assumptions": ASSUMPTIONS,
    }
