"""Verified timelines and three simple, explainable fraud rules."""
from . import clock, db, geo

FAR_MILES = 25


def timeline(household_id):
    events = []
    for m in db.all_docs("messages"):
        if m.get("household_id") != household_id:
            continue
        who = "Good Neighbor" if m["direction"] == "out" else "Resident"
        loc = f" @ {m['lat']:.3f},{m['lng']:.3f}" if m.get("lat") is not None else ""
        events.append({"t": m["t"], "when": clock.fmt(m["t"]), "kind": f"{m['channel']} {m['direction']}",
                       "text": f"{who}: {m['body']}{loc}"})
    for a in db.all_docs("audit"):
        if a.get("case_id") == household_id:
            events.append({"t": a["t"], "when": clock.fmt(a["t"]), "kind": "action", "text": f"{a['actor']}: {a['action']}"})
    return sorted(events, key=lambda e: e["t"])


def fraud_flags(claim, households_by_id, blocks_by_id, all_claims):
    h = households_by_id[claim["household_id"]]
    b = blocks_by_id[h["block_id"]]
    flags = []
    if b["flood_depth_ft"] == 0:
        flags.append("Address is outside the flood zone (0 ft of water recorded)")
    for m in db.all_docs("messages"):
        if m.get("household_id") == h["id"] and m["direction"] == "in" and m.get("lat") is not None:
            d = geo.miles(h["lat"], h["lng"], m["lat"], m["lng"])
            if d > FAR_MILES and "safe" in m["body"].lower():
                flags.append(f"Phone checked in SAFE {d:.0f} miles from the property during the event")
                break
    for other in all_claims:
        if other["id"] == claim["id"]:
            continue
        oh = households_by_id[other["household_id"]]
        if oh["address"] == h["address"] and oh.get("policy_number") != h.get("policy_number"):
            flags.append(f"Same address also claimed under policy {oh.get('policy_number')}")
        elif oh.get("phone") and oh.get("phone") == h.get("phone"):
            flags.append("Same phone number on another claim")
    return flags
