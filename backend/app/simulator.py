"""Demo mode: after "Check in all", fake residents reply over ~60 real seconds.
Simulated replies use the rule-based agent (fast, free). Real inbound texts use Nemotron.
"""
import random
import threading
import time

from . import config, db, seed, services

DURATION_S = 25  # must finish before silence.SETTLE_MINUTES (30 sim min at SIM_SPEED=60) so only truly quiet blocks flag
_stop = threading.Event()
_thread = None


def _reply_for(h, block, rng):
    m = h["members"]
    es = h["language"] == "es"
    oxygen = any(x.get("oxygen") for x in m)
    infant = any(x.get("infant") for x in m)
    mobility = any(x.get("mobility") for x in m)
    elderly = any(x.get("age", 0) >= 75 for x in m)
    insulin = any("insulin_hours_left" in x for x in m)
    special = oxygen or infant or mobility or elderly or insulin
    deep = block["flood_depth_ft"] >= 3

    if not special and rng.random() < (0.45 if deep else 0.8):
        return rng.choice(["Estamos bien, gracias", "BIEN"] if es else
                          ["SAFE", "We're ok, water in the yard but the house is dry", "safe thanks", "We are fine"])

    parts = []
    if es:
        if deep and rng.random() < 0.3:
            parts.append("Está entrando agua a la casa.")
        if oxygen:
            parts.append("Mi esposo usa oxígeno.")
        if mobility:
            parts.append("Mi mamá usa silla de ruedas.")
        if infant:
            parts.append("Tenemos un bebé, necesitamos fórmula.")
        if insulin:
            parts.append("Se nos acaba la insulina.")
        if elderly and not parts:
            parts.append("Mi abuela tiene 84 años.")
        return " ".join(parts) or "Necesitamos ayuda"
    if deep and rng.random() < 0.3:
        parts.append("Water is coming in the house.")
    if oxygen:
        parts.append("My husband uses oxygen.")
    if mobility:
        parts.append("My mother uses a wheelchair.")
    if infant:
        parts.append("We have a baby and need formula.")
    if insulin:
        parts.append("Running low on insulin.")
    if elderly and not parts:
        parts.append("My grandma is 84.")
    return " ".join(parts) or "HELP"


def _run(household_ids):
    rng = random.Random(11)
    blocks = {b["id"]: b for b in db.all_docs("blocks")}
    plan = []
    for hid in household_ids:
        h = db.get("households", hid)
        if hid in ("H-JENKINS", seed.REYES_ID):
            continue  # Jenkins never replies; the Reyes family's reply is the live demo text
        b = blocks[h["block_id"]]
        p = 0.07 if h["block_id"] == seed.FLAGGED_BLOCK else 0.95 - 0.5 * b["svi"]
        if rng.random() < p:
            plan.append((rng.uniform(2, DURATION_S), h, b))
    plan.sort(key=lambda x: x[0])
    t0 = time.time()
    for delay, h, b in plan:
        wait = delay - (time.time() - t0)
        if wait > 0 and _stop.wait(wait):
            return
        if _stop.is_set():
            return
        try:
            services.handle_inbound(h["phone"], _reply_for(h, b, rng), use_llm=False)
        except Exception as e:  # never let one bad reply kill the stream
            print("simulator error:", e)


def start(household_ids):
    global _thread
    if not config.DEMO_MODE:
        return
    stop()
    _stop.clear()
    _thread = threading.Thread(target=_run, args=(list(household_ids),), daemon=True)
    _thread.start()


def stop():
    _stop.set()
    if _thread is not None and _thread.is_alive():
        _thread.join(timeout=2)
