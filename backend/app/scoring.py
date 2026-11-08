"""Urgency score, 0-100. Deterministic and explainable: the language model extracts facts, this formula scores.

Fairness rule: sending more messages never adds points. Need does.
"""

DANGER_LABELS = {
    "water_rising": "Reported: water rising / coming in",
    "trapped": "Reported: trapped",
    "roof": "Reported: on roof or in attic",
    "asked_help": "Asked for help",
    "medical_emergency": "Reported: medical emergency",
}
DANGER_POINTS = {"trapped": 30, "roof": 30, "water_rising": 30, "medical_emergency": 30, "asked_help": 15}


def effective_needs(household: dict, case: dict) -> dict:
    """Merge what's on file (members) with what people told us (case.needs)."""
    members = household.get("members", [])
    told = case.get("needs", {})
    insulin = [m["insulin_hours_left"] for m in members if "insulin_hours_left" in m]
    if told.get("insulin_low"):
        insulin.append(12)
    return {
        "oxygen": any(m.get("oxygen") for m in members) or told.get("oxygen", False),
        "dialysis": any(m.get("dialysis") for m in members) or told.get("dialysis", False),
        "insulin_hours_left": min(insulin) if insulin else None,
        "infant": any(m.get("infant") for m in members) or told.get("infant", False),
        "elderly": any(m.get("age", 0) >= 75 for m in members) or told.get("elderly", False),
        "mobility": any(m.get("mobility") for m in members) or told.get("mobility", False),
        "power_out": told.get("power_out", False),
    }


def compute(needs: dict, depth_ft: float, block_power_out: bool, status: str, danger: list,
            outreach_at, last_reply_at, now: float, reachable: bool = True, in_flagged_block: bool = False):
    if status == "confirmed_safe":
        return 0, ["Confirmed safe by a responder"]

    score, reasons = 0, []

    def add(points, text):
        nonlocal score
        score += points
        reasons.append(f"{text} ({'+' if points >= 0 else ''}{points})")

    if depth_ft > 0:
        add(min(25, round(depth_ft * 5)), f"Water ~{depth_ft:g} ft at address")

    power_out = block_power_out or needs.get("power_out")
    if needs.get("oxygen") and power_out:
        add(30, "Oxygen concentrator, power out")
    elif needs.get("oxygen"):
        add(10, "Oxygen user")

    med = 0
    hrs = needs.get("insulin_hours_left")
    if hrs is not None and hrs < 24:
        med = 20
        reasons_text = f"Insulin runs out in ~{hrs}h"
    if needs.get("dialysis"):
        med = 20
        reasons_text = "Needs dialysis"
    if med:
        add(med, reasons_text)

    vuln = []
    if needs.get("infant"):
        vuln.append("infant")
    if needs.get("elderly"):
        vuln.append("age 75+")
    if needs.get("mobility"):
        vuln.append("mobility limited")
    if vuln:
        add(min(20, 10 * len(vuln)), "Vulnerable: " + ", ".join(vuln))

    if danger:
        # Life-threatening reports outweigh a generic "help"; several reports still count once.
        top = max(danger, key=lambda d: DANGER_POINTS.get(d, 15))
        add(DANGER_POINTS.get(top, 15), DANGER_LABELS.get(top, "Reported danger")
            + (f" +{len(danger) - 1} more" if len(danger) > 1 else ""))

    if depth_ft > 0 and last_reply_at is None:
        if not reachable:
            hours = max(0.0, now / 60)  # clock is negative before landfall
            pts = min(20, int(hours * 4))
            if pts:
                add(pts, f"No way to contact (census estimate), {hours:.1f}h since flood")
        elif outreach_at is not None:
            hours = max(0.0, (now - outreach_at) / 60)
            pts = min(20, int(hours * 4))
            if pts:
                add(pts, f"No reply for {hours:.1f}h")
        if in_flagged_block:
            add(10, "In a block that's unusually quiet")

    if status == "self_reported_safe" and not danger:
        score = min(score, 10)
        reasons.append("Self-reported safe, awaiting confirmation (capped at 10)")

    if status == "assigned":
        add(-30, "Team assigned")

    return max(0, min(100, score)), reasons
