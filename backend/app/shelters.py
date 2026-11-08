"""Shelter operations: intake, special-needs roster, medication schedule, supplies.

Owned by the frontend/shelters lane (see SPLIT.md). Mounted by one line in main.py:
    from . import shelters; app.include_router(shelters.router)

Only *calls* functions from the backend lane (messenger.deliver, services.audit, ...). All data is fake.
"""
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import clock, db, messenger, scoring, services
from .seed import FIRST_EN, FIRST_ES, LAST_EN, LAST_ES

router = APIRouter(prefix="/api/shelters", tags=["shelters"])

SUPPLY_BASE = [("Water (cases)", 140, 40), ("Meals (MREs)", 260, 80), ("Blankets", 90, 30),
               ("Baby formula (cans)", 18, 10), ("Diapers (packs)", 25, 10), ("Oxygen tanks", 6, 4),
               ("Insulin (vials)", 9, 5), ("Phone chargers", 30, 10)]

ACCEPT_TEXT = {
    "en": "Good Neighbor here: {shelter} has a spot for you. Show this text at the door. "
          "If in immediate danger call 911.",
    "es": "Good Neighbor: {shelter} tiene lugar para usted. Muestre este mensaje en la entrada. "
          "Si está en peligro inmediato llame al 911.",
}


class AcceptBody(BaseModel):
    case_id: str


def _key(shelter_id):
    return f"shelter:{shelter_id}"


def _needs_list(flags: dict) -> list[str]:
    labels = [("oxygen", "oxygen"), ("wheelchair", "wheelchair"), ("infant", "infant"), ("insulin", "insulin"),
              ("dialysis", "dialysis"), ("elderly", "age 75+"), ("pets", "pets")]
    return [label for key, label in labels if flags.get(key)]


def _generate(shelter: dict) -> dict:
    """Fake evacuees already at the shelter when the scenario starts."""
    rng = random.Random(shelter["id"])
    now = clock.now()
    detail = {"id": _key(shelter["id"]), "intake": [], "meds": [], "supplies": [], "next_med": 1}
    for i in range(rng.randint(5, 7)):
        es = rng.random() < 0.25
        name = f"{rng.choice(FIRST_ES if es else FIRST_EN)} {rng.choice(LAST_ES if es else LAST_EN)}"
        flags = {
            "wheelchair": shelter["wheelchair"] and rng.random() < 0.25,
            "infant": shelter["infant_supplies"] and rng.random() < 0.25,
            "oxygen": shelter["backup_power"] and rng.random() < 0.2,
            "insulin": rng.random() < 0.2,
            "pets": shelter["pets"] and rng.random() < 0.3,
        }
        detail["intake"].append({"case_id": None, "name": name, "party_size": rng.randint(1, 4),
                                 "arrived_t": round(now - rng.uniform(20, 180), 1), "flags": flags})
        for drug, cond in (("Oxygen tank check", flags["oxygen"]), ("Insulin", flags["insulin"])):
            if cond:
                # Spread doses so one or two are already overdue when the demo starts.
                _add_med(detail, name, drug, round(now + rng.choice([-25, -5, 20, 45, 90]), 1))
    for item, count, low_at in SUPPLY_BASE:
        if item.startswith("Baby") and not shelter["infant_supplies"]:
            count = rng.randint(2, 6)
        if item.startswith("Oxygen") and not shelter["backup_power"]:
            count = 1
        detail["supplies"].append({"item": item, "count": max(0, count + rng.randint(-15, 10) if count > 20 else count),
                                   "low_at": low_at})
    return detail


def _add_med(detail, name, drug, due_t):
    detail["meds"].append({"id": f"M{detail['next_med']}", "name": name, "drug": drug, "due_t": due_t,
                           "given": False, "given_t": None})
    detail["next_med"] += 1


def _shelter_or_404(shelter_id):
    s = db.get("shelters", shelter_id)
    if not s:
        raise HTTPException(404, "Unknown shelter")
    return s


def _detail(shelter):
    d = db.get("meta", _key(shelter["id"]))
    if d is None:
        d = _generate(shelter)
        db.put("meta", d["id"], d)
    return d


@router.get("/{shelter_id}")
def get_shelter(shelter_id: str):
    s = _shelter_or_404(shelter_id)
    d = _detail(s)
    accepted = {e["case_id"] for e in d["intake"] if e["case_id"]}
    pending = []
    for c in db.all_docs("cases"):
        if c.get("shelter_id") == shelter_id and c["id"] not in accepted and c["status"] != "confirmed_safe":
            h = db.get("households", c["id"])
            n = scoring.effective_needs(h, c)
            flags = {**n, "wheelchair": n["mobility"], "insulin": n["insulin_hours_left"] is not None,
                     "pets": h.get("pets")}
            pending.append({"case_id": c["id"], "name": h["name"], "status": c["status"], "needs": _needs_list(flags)})
    return {
        "shelter": s,
        "now": clock.now(),
        "intake": [{k: v for k, v in e.items() if k != "flags"} | {"needs": _needs_list(e["flags"])}
                   for e in sorted(d["intake"], key=lambda e: -e["arrived_t"])],
        "roster": [{"name": e["name"], **{k: bool(e["flags"].get(k)) for k in ("wheelchair", "infant", "oxygen", "pets")}}
                   for e in d["intake"]
                   if any(e["flags"].get(k) for k in ("wheelchair", "infant", "oxygen", "pets"))],
        "meds": sorted(d["meds"], key=lambda m: (m["given"], m["due_t"])),
        "supplies": d["supplies"],
        "pending": pending,
    }


@router.post("/{shelter_id}/accept")
def accept(shelter_id: str, body: AcceptBody):
    s = _shelter_or_404(shelter_id)
    h = db.get("households", body.case_id)
    c = db.get("cases", body.case_id)
    if not h or not c:
        raise HTTPException(404, "Unknown case")
    d = _detail(s)
    if any(e["case_id"] == body.case_id for e in d["intake"]):
        raise HTTPException(409, "Already accepted")
    party = max(1, len(h.get("members", [])))
    if s["occupancy"] + party > s["capacity"]:
        raise HTTPException(409, "Shelter is full")

    n = scoring.effective_needs(h, c)
    flags = {"wheelchair": n["mobility"], "infant": n["infant"], "oxygen": n["oxygen"],
             "insulin": n["insulin_hours_left"] is not None, "dialysis": n["dialysis"],
             "elderly": n["elderly"], "pets": bool(h.get("pets"))}
    now = clock.now()
    d["intake"].append({"case_id": body.case_id, "name": h["name"], "party_size": party, "arrived_t": now,
                        "flags": flags})
    if flags["oxygen"]:
        _add_med(d, h["name"], "Oxygen tank check", round(now + 60, 1))
    if flags["insulin"]:
        _add_med(d, h["name"], "Insulin", round(now + 30, 1))
    if flags["dialysis"]:
        _add_med(d, h["name"], "Dialysis transport", round(now + 120, 1))
    db.put("meta", d["id"], d)

    s["occupancy"] += party
    db.put("shelters", s["id"], s)
    c["shelter_id"] = shelter_id
    db.put("cases", c["id"], c)

    messenger.deliver(h, ACCEPT_TEXT.get(h.get("language"), ACCEPT_TEXT["en"]).format(shelter=s["name"]))
    services.audit("shelter staff", f"{s['name']} accepted {h['name']} (party of {party})", c["id"])
    return {"ok": True}


@router.post("/{shelter_id}/meds/{med_id}/given")
def med_given(shelter_id: str, med_id: str):
    s = _shelter_or_404(shelter_id)
    d = _detail(s)
    med = next((m for m in d["meds"] if m["id"] == med_id), None)
    if med is None:
        raise HTTPException(404, "Unknown medication entry")
    med["given"], med["given_t"] = True, clock.now()
    db.put("meta", d["id"], d)
    services.audit("shelter staff", f"{med['drug']} given to {med['name']} at {s['name']}")
    return {"ok": True}
