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

    cases = [{"id": h["id"], "household_id": h["id"], "status": "unreached", "needs": {}, "danger": [],
              "outreach_at": None, "last_reply_at": None, "assigned_team": None, "shelter_id": None}
             for h in households]

    db.put_many("blocks", blocks)
    db.put_many("households", households)
    db.put_many("cases", cases)
    db.put_many("teams", _teams())
    db.put_many("shelters", _shelters(blocks))
    db.put_many("claims", claims)
    for c in claims:
        if c["planted"] == "far_checkin":
            # Policyholder's phone checked in SAFE from ~40 miles west (Katy-ish) during the event.
            db.append("messages", {"household_id": c["household_id"], "direction": "in", "channel": "sms",
                                   "body": "SAFE - out of town", "t": 0.0, "lat": 29.79, "lng": -96.03})
    return {"blocks": len(blocks), "households": len(households),
            "in_zone": sum(1 for h in households if blocks_by_id[h["block_id"]]["flood_depth_ft"] > 0
                           and not h.get("hidden_from_map"))}
