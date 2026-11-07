"""P0 #1: prove Nemotron runs for real (not the rule fallback).

Usage (from LifeLine/):
    backend/.venv/bin/python backend/scripts/nemotron_check.py            # list Nemotron models on your key
    backend/.venv/bin/python backend/scripts/nemotron_check.py --run      # run the real agent on the judge text

--run uses a throwaway database, so it never touches lifeline.db.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "nemotron_check.db")
os.environ["DEMO_MODE"] = "0"

from openai import OpenAI  # noqa: E402

from app import config  # noqa: E402

if not config.NVIDIA_API_KEY:
    sys.exit("NVIDIA_API_KEY is empty. Put it in backend/.env (copy backend/.env.example).")

client = OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.NVIDIA_API_KEY, timeout=30)
models = sorted(m.id for m in client.models.list().data if "nemotron" in m.id.lower())
print("Nemotron models on this key:")
for m in models:
    print("  ", m)
print("NEMOTRON_MODEL in .env:", config.NEMOTRON_MODEL or "(empty)")

if "--run" not in sys.argv:
    sys.exit(0)
if not config.NEMOTRON_MODEL:
    sys.exit("Set NEMOTRON_MODEL in backend/.env to one of the IDs above (one that supports tool calling).")

from app import agent, db, services  # noqa: E402

services.start_scenario()
text = "el agua está entrando, mi mamá usa oxígeno y no hay luz"
h = services.find_or_create_household("+15125550199")
services.record_inbound(h, text)
result = agent.run(h["id"], h["phone"], text, use_llm=True)
print("\nengine:", result.get("engine"))
for t in reversed(db.recent("trace", 20)):
    print(f"  [{t['engine']}] {t['tool']} {t['args']} -> {str(t['result'])[:160]}")
ok = result.get("engine") == "nemotron"
print("\nPASS: Nemotron ran the tool loop itself." if ok else
      "\nFAIL: fell back to rules. Check the error line above (bad model ID, no tool-calling support, or skipped steps).")
sys.exit(0 if ok else 1)
