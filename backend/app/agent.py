"""Triage agent. Nemotron (via NVIDIA's OpenAI-compatible API) runs a multi-step tool loop.
If it isn't configured or errors, a rule-based agent runs the same tools so the demo never dies.

Every tool call is written to the `trace` table and shown live in the dashboard.
The agent can never dispatch a team: it recommends, a human approves.
"""
import json
import logging

from . import clock, config, db, extract, messenger, scoring, services

log = logging.getLogger("lifeline.agent")
MAX_STEPS = 7

SYSTEM_PROMPT = """You are Good Neighbor Triage's agent, working for an insurer's catastrophe team during a flash flood in Houston.
A resident just sent a text message. Work step by step using the tools, in this order:
1. lookup_household(phone): who they are and what is already on file.
2. get_hazard(household_id): flood depth and power status at their address.
3. update_needs(...): record ONLY facts stated in the message. Do not guess or add needs that were not mentioned.
4. compute_score(household_id): the official urgency score. Never invent or estimate a score yourself.
5. find_shelter(household_id): if they need help or may need to leave.
6. send_reply(household_id, text): ONE short, calm SMS under 300 characters, in the resident's language
   (Spanish if they wrote in Spanish). Never promise an arrival time. No medical advice.
   Always end with "If in immediate danger call 911." (Spanish: "Si está en peligro inmediato llame al 911.")
You cannot dispatch rescue teams; a human on the cat team approves every dispatch. Stop after send_reply."""

TOOLS = [
    {"type": "function", "function": {
        "name": "lookup_household", "description": "Find the household for a phone number and what's on file.",
        "parameters": {"type": "object", "properties": {"phone": {"type": "string"}}, "required": ["phone"]}}},
    {"type": "function", "function": {
        "name": "get_hazard", "description": "Flood depth (ft), power status and block for the household's address.",
        "parameters": {"type": "object", "properties": {"household_id": {"type": "string"}},
                       "required": ["household_id"]}}},
    {"type": "function", "function": {
        "name": "update_needs", "description": "Save facts extracted from the message.",
        "parameters": {"type": "object", "properties": {
            "household_id": {"type": "string"},
            "needs": {"type": "object", "properties": {
                "oxygen": {"type": "boolean"}, "dialysis": {"type": "boolean"}, "insulin_low": {"type": "boolean"},
                "infant": {"type": "boolean"}, "elderly": {"type": "boolean"}, "mobility": {"type": "boolean"},
                "power_out": {"type": "boolean"}}},
            "danger": {"type": "array", "items": {"type": "string", "enum": [
                "water_rising", "trapped", "roof", "medical_emergency", "asked_help"]}},
            "self_reported_safe": {"type": "boolean"},
            "summary": {"type": "string", "description": "One-line summary for the cat team"}},
            "required": ["household_id", "needs", "danger", "self_reported_safe", "summary"]}}},
    {"type": "function", "function": {
        "name": "compute_score", "description": "Run the official urgency formula. Returns score 0-100 and reasons.",
        "parameters": {"type": "object", "properties": {"household_id": {"type": "string"}},
                       "required": ["household_id"]}}},
    {"type": "function", "function": {
        "name": "find_shelter", "description": "Nearest open shelter that fits the household's needs.",
        "parameters": {"type": "object", "properties": {"household_id": {"type": "string"}},
                       "required": ["household_id"]}}},
    {"type": "function", "function": {
        "name": "send_reply", "description": "Send one SMS reply to the resident.",
        "parameters": {"type": "object", "properties": {"household_id": {"type": "string"}, "text": {"type": "string"}},
                       "required": ["household_id", "text"]}}},
]


# ---------- tools ----------

class Toolbox:
    def __init__(self, household_id, engine):
        self.household_id = household_id
        self.engine = engine
        self.called = set()

    def trace(self, tool, args, result):
        h = db.get("households", self.household_id) or {}
        db.append("trace", {"t": clock.now(), "engine": self.engine, "household_id": self.household_id,
                            "name": h.get("name"), "tool": tool, "args": args, "result": result})

    def run(self, tool, args):
        fn = getattr(self, f"t_{tool}", None)
        if fn is None:
            result = {"error": f"unknown tool {tool}"}
        else:
            try:
                result = fn(**args)
            except Exception as e:  # report tool errors back to the model instead of crashing
                result = {"error": str(e)}
        self.called.add(tool)
        self.trace(tool, args, result)
        return result

    def t_lookup_household(self, phone):
        h = services.find_or_create_household(phone)
        self.household_id = h["id"]
        c = db.get("cases", h["id"])
        return {"household_id": h["id"], "name": h["name"], "language": h["language"], "source": h["source"],
                "on_file": scoring.effective_needs(h, c), "members": len(h["members"]), "status": c["status"]}

    def t_get_hazard(self, household_id):
        h = db.get("households", household_id)
        b = db.get("blocks", h["block_id"])
        return {"block": b["id"], "flood_depth_ft": b["flood_depth_ft"], "power_out": b["power_out"]}

    def t_update_needs(self, household_id, needs, danger, self_reported_safe, summary=""):
        c = db.get("cases", household_id)
        c["needs"] = {**c.get("needs", {}), **{k: v for k, v in needs.items() if v}}
        c["danger"] = sorted(set(c.get("danger", [])) | set(danger))
        if c["status"] not in ("assigned", "confirmed_safe"):
            c["status"] = "self_reported_safe" if self_reported_safe and not c["danger"] else "needs_help"
        c["summary"] = summary
        db.put("cases", household_id, c)
        return {"status": c["status"], "needs": c["needs"], "danger": c["danger"]}

    def t_compute_score(self, household_id):
        s, reasons = services.score_one(household_id)
        return {"score": s, "reasons": reasons}

    def t_find_shelter(self, household_id):
        h = db.get("households", household_id)
        c = db.get("cases", household_id)
        s = services.find_shelter(h, c)
        if s:
            c["shelter_id"] = s["id"]
            db.put("cases", household_id, c)
            return {"shelter": s["name"], "beds_free": s["capacity"] - s["occupancy"],
                    "wheelchair": s["wheelchair"], "backup_power": s["backup_power"]}
        return {"shelter": None}

    def t_send_reply(self, household_id, text):
        h = db.get("households", household_id)
        if not text.lstrip().lower().startswith("good neighbor"):
            text = ("Good Neighbor: " if h.get("language") == "es" else "Good Neighbor here: ") + text.lstrip()
        via = messenger.deliver(h, text[:480])
        return {"sent": True, "via": via}


# ---------- rule-based agent (fallback, and for simulated replies) ----------

def reply_text(lang, status, shelter):
    if lang == "es":
        if status == "self_reported_safe":
            return "Gracias, nos alegra que estén bien. Responda AYUDA si algo cambia. Si está en peligro inmediato llame al 911."
        s = f" Refugio más cercano: {shelter}." if shelter else ""
        return ("Good Neighbor: recibimos su mensaje y su hogar está marcado como prioridad. Estamos coordinando "
                f"un equipo de respuesta.{s} Si está en peligro inmediato llame al 911.")
    if status == "self_reported_safe":
        return "Thanks, glad you're safe. Reply HELP anytime if that changes. If in immediate danger call 911."
    s = f" Nearest open shelter: {shelter}." if shelter else ""
    return ("Good Neighbor here: we got your message and flagged your household as a priority. A response team is "
            f"being coordinated.{s} If in immediate danger call 911.")


def run_rules(household_id, phone, text, engine="rules"):
    tb = Toolbox(household_id, engine)
    info = tb.run("lookup_household", {"phone": phone})
    hid = info["household_id"]
    tb.run("get_hazard", {"household_id": hid})
    ex = extract.extract(text)
    if ex["language"] == "es":
        h = db.get("households", hid)
        if h["language"] != "es":
            h["language"] = "es"
            db.put("households", hid, h)
    upd = tb.run("update_needs", {"household_id": hid, "needs": ex["needs"], "danger": ex["danger"],
                                  "self_reported_safe": ex["self_reported_safe"], "summary": text[:120]})
    score = tb.run("compute_score", {"household_id": hid})
    shelter = None
    if upd["status"] == "needs_help":
        shelter = tb.run("find_shelter", {"household_id": hid}).get("shelter")
    lang = db.get("households", hid)["language"]
    tb.run("send_reply", {"household_id": hid, "text": reply_text(lang, upd["status"], shelter)})
    return {"engine": engine, "score": score}


# ---------- Nemotron agent ----------

def run_nemotron(household_id, phone, text):
    from openai import OpenAI
    client = OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.NVIDIA_API_KEY, timeout=30)
    tb = Toolbox(household_id, "nemotron")
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Inbound text from {phone} at {clock.fmt(clock.now())}:\n\"{text}\""}]
    for _ in range(MAX_STEPS):
        resp = client.chat.completions.create(model=config.NEMOTRON_MODEL, messages=messages, tools=TOOLS,
                                              tool_choice="auto", temperature=0.2, max_tokens=1024,
                                              extra_body={"chat_template_kwargs":
                                                          {"enable_thinking": config.NEMOTRON_THINKING}})
        msg = resp.choices[0].message
        if not msg.tool_calls:
            break
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tb.run(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
        if "send_reply" in tb.called:
            break

    # Guarantee the case is updated and the resident hears back, even if the model skipped steps.
    if "update_needs" not in tb.called or "send_reply" not in tb.called:
        log.warning("Nemotron skipped required steps (%s); finishing with rules", tb.called)
        return run_rules(tb.household_id, phone, text, engine="nemotron→rules")
    return {"engine": "nemotron"}


def run(household_id, phone, text, use_llm=True):
    if use_llm and config.llm_configured():
        try:
            return run_nemotron(household_id, phone, text)
        except Exception as e:
            log.warning("Nemotron failed, using rule-based agent: %s", e)
            db.append("trace", {"t": clock.now(), "engine": "nemotron", "household_id": household_id,
                                "name": None, "tool": "error", "args": {}, "result": {"error": str(e)[:200]}})
    return run_rules(household_id, phone, text, engine="rules" if use_llm else "simulated")
