"""Keyword extraction. Used by the rule-based fallback agent and by the demo simulator."""
import re

KEYWORDS = {
    "oxygen": ["oxygen", "o2 ", "oxígeno", "oxigeno", "concentrator"],
    "dialysis": ["dialysis", "diálisis", "dialisis"],
    "insulin_low": ["insulin", "insulina"],
    "infant": ["baby", "infant", "newborn", "bebé", "bebe ", "formula"],
    "elderly": ["grandma", "grandmother", "grandpa", "grandfather", "elderly", "abuela", "abuelo", "years old", "años"],
    "mobility": ["wheelchair", "can't walk", "cannot walk", "cant walk", "walker", "bedridden", "silla de ruedas",
                 "no puede caminar"],
    "power_out": ["power is out", "power out", "no power", "power's out", "no electricity", "sin luz",
                  "no hay luz", "sin electricidad"],
}
DANGER = {
    "trapped": ["trapped", "stuck", "can't get out", "cant get out", "atrapad"],
    "roof": ["roof", "attic", "techo", "ático", "atico"],
    "water_rising": ["water rising", "water is rising", "water coming", "coming in", "water inside", "water in the house",
                     "el agua está subiendo", "el agua esta subiendo", "entrando agua", "se está inundando",
                     "agua está entrando", "agua esta entrando", "agua entrando", "se mete el agua"],
    "medical_emergency": ["can't breathe", "cant breathe", "unconscious", "chest pain", "bleeding", "no puede respirar"],
    "asked_help": ["help", "ayuda", "sos", "emergency", "emergencia"],
}
SAFE_WORDS = ["safe", "we're ok", "we are ok", "we're fine", "we are fine", "all good", "estamos bien", "bien",
              "ok", "okay", "dry"]
SPANISH_HINTS = ["agua", "ayuda", "bebé", "estamos", "necesitamos", " mi ", "luz", "silla", "gracias", "abuel", "está"]


def extract(text: str) -> dict:
    t = " " + text.lower().strip() + " "
    needs = {k: True for k, words in KEYWORDS.items() if any(w in t for w in words)}
    danger = [k for k, words in DANGER.items() if any(w in t for w in words)]
    if len(danger) > 1 and "asked_help" in danger:
        danger.remove("asked_help")  # keep the specific signal
    stripped = re.sub(r"[^a-záéíóúñ' ]", "", t).strip()
    safe = not danger and (stripped in SAFE_WORDS or stripped.startswith("safe") or "estamos bien" in t
                          or "we're ok" in t or "we are ok" in t)
    lang = "es" if sum(h in t for h in SPANISH_HINTS) >= 2 else "en"
    return {"needs": needs, "danger": danger, "self_reported_safe": safe, "language": lang}
