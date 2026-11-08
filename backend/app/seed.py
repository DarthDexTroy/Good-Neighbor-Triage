"""Fake Houston flood scenario. Everything here is invented: names, phones (555), addresses, policies."""
import random

from . import db

CENTER_LAT, CENTER_LNG = 29.760, -95.370
GRID = 6
STEP = 0.0055  # ~600 m per block
FLAGGED_BLOCK = "B4-2"  # the quiet block from the demo script

FIRST_EN = ["James", "Mary", "Robert", "Linda", "Michael", "Patricia", "David", "Barbara", "Kevin", "Angela",
            "Brian", "Denise", "Marcus", "Tasha", "Steven", "Karen", "Andre", "Monica", "Tyler", "Grace"]
FIRST_ES = ["José", "María", "Luis", "Guadalupe", "Carlos", "Rosa", "Miguel", "Ana", "Jorge", "Lucía",
            "Juan", "Carmen", "Ricardo", "Elena"]
LAST_EN = ["Johnson", "Williams", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor", "Thomas", "Jackson",
           "White", "Harris", "Clark", "Lewis", "Walker", "Young", "Allen", "King", "Wright", "Scott"]
LAST_ES = ["García", "Hernández", "Martínez", "López", "González", "Rodríguez", "Pérez", "Sánchez", "Ramírez",
           "Torres", "Flores", "Rivera"]
STREETS = ["Bayou Bend Dr", "Cypress Ln", "Magnolia St", "Pecan Ave", "Live Oak Dr", "Heron Way", "Willow Crk Rd",
           "Mockingbird Ln", "Bluebonnet St", "Cottonwood Dr", "Prairie View Ln", "Sabine St"]


def _blocks(rng):
    blocks = []
    for r in range(GRID):
        for c in range(GRID):
            south = CENTER_LAT - GRID / 2 * STEP + r * STEP
            west = CENTER_LNG - GRID / 2 * STEP + c * STEP
            # A "bayou" runs diagonally; water is deepest near it.
            dist = abs((r - 2.5) + 0.5 * (c - 2.5))
            depth = max(0.0, 6.2 - 2.3 * dist + rng.uniform(-0.6, 0.6))
            depth = round(depth, 1) if depth >= 0.3 else 0.0
            svi = round(rng.uniform(0.15, 0.75), 2)
            bid = f"B{r}-{c}"
            if bid == FLAGGED_BLOCK:
                depth, svi = 5.6, 0.92
            blocks.append({
                "id": bid,
                "bounds": [round(south, 5), round(west, 5), round(south + STEP, 5), round(west + STEP, 5)],
                "center": [round(south + STEP / 2, 5), round(west + STEP / 2, 5)],
                "flood_depth_ft": depth,
                "power_out": depth >= 1.5,
                "svi": svi,
            })
    return blocks


def _member(rng, age_lo, age_hi):
    return {"age": rng.randint(age_lo, age_hi)}


def _household(rng, hid, block, n_in_block):
    spanish = rng.random() < 0.2
    first = rng.choice(FIRST_ES if spanish else FIRST_EN)
    last = rng.choice(LAST_ES if spanish else LAST_EN)
    s, w, n, e = block["bounds"]
    size = rng.choice([1, 1, 2, 2, 2, 3, 3, 4, 5])
    members = [_member(rng, 22, 70)]
    for _ in range(size - 1):
        members.append(_member(rng, 1, 70))
    if rng.random() < 0.15:
        members.append({"age": rng.randint(75, 92)})
    if rng.random() < 0.10:
        members.append({"age": 0, "infant": True})
    adults = [m for m in members if m["age"] >= 18]
    medical = False
    if rng.random() < 0.08:
        rng.choice(adults)["oxygen"] = True
        medical = True
    if rng.random() < 0.04:
        rng.choice(adults)["insulin_hours_left"] = rng.choice([10, 18, 36, 60])
    if rng.random() < 0.07:
        rng.choice(adults)["mobility"] = True

    roll = rng.random()
    if medical and roll < 0.5:
        source = "utility_medical"
    elif roll < 0.55:
        source = "policyholder"
    elif roll < 0.78:
        source = "app"
    elif roll < 0.88:
        source = "utility_medical" if medical else "policyholder"
    else:
        source = "census_estimate"  # known only statistically: no phone, no name on file

    hh = {
        "id": hid,
        "name": f"{first} {last}" if source != "census_estimate" else "Unknown household (census estimate)",
        "address": f"{rng.randint(100, 9899)} {rng.choice(STREETS)}",
        "lat": round(rng.uniform(s + 0.0004, n - 0.0004), 6),
        "lng": round(rng.uniform(w + 0.0004, e - 0.0004), 6),
        "block_id": block["id"],
        "phone": None if source == "census_estimate" else f"+1713555{rng.randint(0, 9999):04d}",
        "language": "es" if spanish else "en",
        "source": source,
        "consent": source != "census_estimate",
        "policy_number": f"SF-{rng.randint(10_000_000, 99_999_999)}" if source == "policyholder" else None,
        "members": members,
        "pets": rng.random() < 0.35,
    }
    return hh


def _plant_jenkins(block):
    s, w, n, e = block["bounds"]
    return {
        "id": "H-JENKINS",
        "name": "Ruth & Harold Jenkins",
        "address": "2214 Heron Way",
        "lat": round((s + n) / 2 + 0.0008, 6),
        "lng": round((w + e) / 2 - 0.0006, 6),
        "block_id": block["id"],
        "phone": "+17135550142",
        "language": "en",
        "source": "utility_medical",  # never installed the app; only on the power company's medical list
        "consent": True,
        "policy_number": None,
        "members": [{"age": 81, "oxygen": True, "mobility": True}, {"age": 79}],
        "pets": False,
    }


def _teams():
    base_lat, base_lng = CENTER_LAT - GRID / 2 * STEP - 0.003, CENTER_LNG - GRID / 2 * STEP - 0.003
    far_lat, far_lng = CENTER_LAT + GRID / 2 * STEP + 0.003, CENTER_LNG + GRID / 2 * STEP + 0.003
    spec = [("Boat 1", "boat", base_lat, base_lng), ("Boat 2", "boat", far_lat, far_lng),
            ("Boat 3", "boat", base_lat, far_lng), ("Boat 4", "boat", far_lat, base_lng),
            ("Medic 1", "medical", CENTER_LAT, base_lng), ("Medic 2", "medical", CENTER_LAT, far_lng),
            ("Supply 1", "supply", base_lat, CENTER_LNG), ("Supply 2", "supply", far_lat, CENTER_LNG)]
    return [{"id": f"T{i + 1}", "name": n, "type": t, "lat": round(la, 5), "lng": round(ln, 5),
             "status": "available", "case_id": None} for i, (n, t, la, ln) in enumerate(spec)]


def _shelters(blocks):
    dry = [b for b in blocks if b["flood_depth_ft"] == 0]
    picks = dry[:2] + dry[-2:] if len(dry) >= 4 else dry
    features = [
        {"name": "Northside HS Gym", "wheelchair": True, "backup_power": True, "infant_supplies": False, "pets": False},
        {"name": "Grace Community Center", "wheelchair": True, "backup_power": False, "infant_supplies": True, "pets": True},
        {"name": "Eastwood Rec Center", "wheelchair": False, "backup_power": True, "infant_supplies": True, "pets": False},
        {"name": "St. Mark's Hall", "wheelchair": True, "backup_power": True, "infant_supplies": True, "pets": True},
    ]
    out = []
    for i, b in enumerate(picks):
        f = features[i % len(features)]
        out.append({"id": f"S{i + 1}", **f, "lat": b["center"][0], "lng": b["center"][1],
                    "capacity": [120, 80, 150, 60][i % 4], "occupancy": [70, 64, 40, 51][i % 4]})
    return out


def _claims(rng, households, blocks_by_id):
    """Pre-existing claim drafts so the claims screen isn't empty. Two are planted as suspicious."""
    policy = [h for h in households if h["policy_number"] and blocks_by_id[h["block_id"]]["flood_depth_ft"] > 2]
    dry_policy = [h for h in households if h["policy_number"] and blocks_by_id[h["block_id"]]["flood_depth_ft"] == 0]
    claims = []
    for h in rng.sample(policy, 4):
        claims.append({"id": f"C-{h['id']}", "household_id": h["id"], "status": "draft", "planted": None})
    if dry_policy:
        h = dry_policy[0]
        claims.append({"id": f"C-{h['id']}", "household_id": h["id"], "status": "draft", "planted": "far_checkin"})
    # Duplicate: a second policy number filing on the same address as a legit claim.
    src = households[[x["id"] for x in households].index(claims[0]["household_id"])]
    dup = {**src, "id": "H-DUP", "name": "Derek Lane", "phone": "+17135559931",
           "policy_number": "SF-41207755", "source": "policyholder", "hidden_from_map": True}
    claims.append({"id": "C-H-DUP", "household_id": "H-DUP", "status": "draft", "planted": "duplicate"})
    return claims, dup


def seed(rng_seed: int = 7):
    rng = random.Random(rng_seed)
    blocks = _blocks(rng)
    blocks_by_id = {b["id"]: b for b in blocks}
    households = []
    n = 0
    for b in blocks:
        count = 14 if b["id"] == FLAGGED_BLOCK else 11
        for _ in range(count):
            n += 1
            households.append(_household(rng, f"H{n:04d}", b, count))
    households.append(_plant_jenkins(blocks_by_id[FLAGGED_BLOCK]))

    claims, dup = _claims(rng, households, blocks_by_id)
    households.append(dup)
    # Before/After data uses its own RNG so the During scenario above stays byte-for-byte the same.
    contractors = _business(random.Random(rng_seed + 1000), households, blocks, blocks_by_id, claims)

    cases = [{"id": h["id"], "household_id": h["id"], "status": "unreached", "needs": {}, "danger": [],
              "outreach_at": None, "last_reply_at": None, "assigned_team": None, "shelter_id": None}
             for h in households]

    db.put_many("blocks", blocks)
    db.put_many("households", households)
    db.put_many("cases", cases)
    db.put_many("teams", _teams())
    db.put_many("shelters", _shelters(blocks))
    db.put_many("claims", claims)
    db.put_many("contractors", contractors)
    for c in claims:
        if c["planted"] == "far_checkin":
            # Policyholder's phone checked in SAFE from ~40 miles west (Katy-ish) during the event.
            db.append("messages", {"household_id": c["household_id"], "direction": "in", "channel": "sms",
                                   "body": "SAFE - out of town", "t": 0.0, "lat": 29.79, "lng": -96.03})
    return {"blocks": len(blocks), "households": len(households),
            "in_zone": sum(1 for h in households if blocks_by_id[h["block_id"]]["flood_depth_ft"] > 0
                           and not h.get("hidden_from_map"))}


# ---------- Before / After phases (all fake) ----------

REYES_ID = "H-REYES"
REYES_PHONE = "+17135550188"
LANDFALL = 0
CONTRACTORS = [
    # Gulf Rapid Roofing is the planted storm chaser: unlicensed, 9 claims, benefits signed ~6h after landfall.
    {"id": "K1", "name": "Gulf Rapid Roofing", "phone": "+17135550777", "licensed": False},
    {"id": "K2", "name": "Bayou City Restoration", "phone": "+17135550310", "licensed": True},
    {"id": "K3", "name": "Lone Star Roof & Siding", "phone": "+17135550422", "licensed": True},
    {"id": "K4", "name": "Coastal Home Repair", "phone": "+17135550533", "licensed": True},
]
PERIL_TEXT = {
    "minor": ("Flood: water in kitchen and garage", "Water damage to flooring and lower cabinets"),
    "major": ("Flood + wind", "Water to 2 ft inside, drywall and flooring out, roof shingles missing"),
    "total": ("Flood", "Water above 4 ft inside the home, structure and contents a total loss"),
}


def damage_for_depth(depth, rng):
    """Seeded 'simulated damage assessment' label. Mostly follows flood depth, with some noise."""
    if depth < 1.5:
        return "minor"
    if depth < 3.5:
        return rng.choice(["minor", "major", "major"])
    return rng.choice(["major", "major", "total"])


def _photo_set(kind, damage=None):
    pre = [{"phase": "pre", "url": "/photos/house-pre.svg", "label": "Home, front (pre-storm)"},
           {"phase": "pre", "url": "/photos/car-pre.svg", "label": "Car (pre-storm)"}]
    if kind == "pre":
        return pre
    return [{"phase": "post", "url": f"/photos/house-{damage}.svg", "label": f"Home, front (after): {damage}"}]


def _reyes(block):
    s, w, n, e = block["bounds"]
    return {
        "id": REYES_ID,
        "name": "Ana & Rosa Reyes",
        "address": "1418 Magnolia St",
        "lat": round((s + n) / 2 - 0.0012, 6),
        "lng": round((w + e) / 2 + 0.0010, 6),
        "block_id": block["id"],
        "phone": REYES_PHONE,
        "language": "es",
        "source": "policyholder",
        "consent": True,
        "policy_number": "SF-20481918",
        "members": [{"age": 34, "name": "Ana"}, {"age": 71, "name": "Rosa", "oxygen": True, "mobility": True}],
        "pets": False,
        "home": {"value": 215000, "roof_age": 22, "shutters": False, "construction": "wood frame"},
        "vehicles": [{"year": 2019, "type": "sedan", "value": 19500}],
        "photos": _photo_set("pre"),
        "actions": [],
    }


def _business(rng, households, blocks, blocks_by_id, claims):
    # Homes, cars and pre-storm photos for everyone we know about.
    for h in households:
        if h["source"] == "census_estimate":
            h.update({"home": {"value": rng.randint(110, 260) * 1000, "roof_age": rng.randint(3, 35),
                               "shutters": False, "construction": "unknown"}, "vehicles": [], "photos": [],
                      "actions": []})
            continue
        h["home"] = {"value": rng.randint(140, 420) * 1000, "roof_age": rng.randint(2, 30),
                     "shutters": rng.random() < 0.3, "construction": rng.choice(["wood frame", "brick", "wood frame"])}
        h["vehicles"] = [{"year": rng.randint(2010, 2025), "type": rng.choice(["sedan", "SUV", "pickup"]),
                          "value": rng.randint(8, 38) * 1000} for _ in range(rng.choice([0, 1, 1, 2]))]
        h["photos"] = _photo_set("pre") if h.get("policy_number") and rng.random() < 0.5 else []
        h["actions"] = []

    # The demo family lives in the deepest block other than the planted quiet one.
    deep = max((b for b in blocks if b["id"] != FLAGGED_BLOCK), key=lambda b: b["flood_depth_ft"])
    reyes = _reyes(deep)
    households.append(reyes)

    by_id = {h["id"]: h for h in households}
    n = 1000

    def claim_fields(h, damage, estimate, fnol_t, contractor=None, aob_t=None):
        nonlocal n
        n += 1 + (n + 1 == 1042)  # DEMO-1042 is reserved for the Reyes family (demo script)
        peril, dmg = PERIL_TEXT[damage]
        return {"claim_number": f"DEMO-{n}", "fnol_t": round(fnol_t, 1),
                "fnol": {"date_of_loss": "landfall (T+0)", "peril": peril, "damage": dmg,
                         "injuries": "none reported", "temp_housing": damage != "minor", "photos": []},
                "estimate": int(estimate), "damage_label": damage, "contractor_id": contractor,
                "aob_signed_t": aob_t, "paid_t": None, "paid_amount": None,
                "photos": [p for p in h.get("photos", [])] + _photo_set("post", damage)}

    def estimate_for(damage):
        return {"minor": rng.randint(9, 24) * 100, "major": rng.randint(60, 240) * 100,
                "total": rng.randint(300, 900) * 100}[damage]

    # Legacy claims (During tab's fraud examples) get recovery fields too.
    for c in claims:
        h = by_id[c["household_id"]]
        depth = blocks_by_id[h["block_id"]]["flood_depth_ft"]
        damage = "minor" if c["planted"] else damage_for_depth(depth, rng)
        est = 2100 if c["planted"] else estimate_for(damage)
        c.update(claim_fields(h, damage, est, rng.uniform(600, 1800)))

    # New recovery claims from policyholders in flooded blocks.
    taken = {c["household_id"] for c in claims} | {REYES_ID, "H-DUP"}
    pool = [h for h in households if h.get("policy_number") and h["id"] not in taken
            and blocks_by_id[h["block_id"]]["flood_depth_ft"] > 0]
    picks = rng.sample(pool, min(40, len(pool)))
    for i, h in enumerate(picks):
        depth = blocks_by_id[h["block_id"]]["flood_depth_ft"]
        if i < 9:  # Gulf Rapid Roofing: benefits signed ~6h after landfall, estimates padded ~2.3x
            damage = rng.choice(["minor", "major", "major"])
            fields = claim_fields(h, damage, estimate_for(damage) * 2.3, rng.uniform(900, 2700), "K1",
                                  round(360 + rng.uniform(-30, 45), 1))
        elif i < 17:  # licensed contractors, signed days after the claim was filed
            damage = damage_for_depth(depth, rng)
            fnol_t = rng.uniform(1500, 2300)
            fields = claim_fields(h, damage, estimate_for(damage), fnol_t, rng.choice(["K2", "K3", "K4"]),
                                  round(fnol_t + rng.uniform(150, 450), 1))
        else:
            damage = damage_for_depth(depth, rng)
            if rng.random() < 0.35:
                damage = "minor"  # plenty of small claims so auto-pay has work to do
            fields = claim_fields(h, damage, estimate_for(damage), rng.uniform(300, 2820))
        claims.append({"id": f"C-{h['id']}", "household_id": h["id"], "status": "filed", "planted": None, **fields})

    # Reyes: minor, $1,840, pre-storm photos on file, no contractor → auto-pay.
    rc = {"id": f"C-{REYES_ID}", "household_id": REYES_ID, "status": "filed", "planted": None,
          **claim_fields(reyes, "minor", 1840, 2820)}
    rc["claim_number"] = "DEMO-1042"
    rc["fnol"]["damage"] = "Water in kitchen and garage (~4 in); flooring and lower cabinets"
    claims.append(rc)
    return CONTRACTORS
