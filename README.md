# Lifeline

State Farm challenge, HackUTD 2026: *The Worst Day, at Scale.*
Find everyone in a disaster zone, reach them by text, rank by real need, dispatch help,
and close cases only when people are confirmed safe. **All data is fake.**

- [SPEC.md](SPEC.md): what to build, must-work vs nice-to-have, timeline
- [JUDGES.md](JUDGES.md): what State Farm judges care about, for the pitch

## Run it

Two terminals from this folder.

**Backend** (Python 3.11):
```bash
cd backend && uv venv .venv && uv pip install -r requirements.txt && cp .env.example .env
```
```bash
backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000 --reload
```

**Dashboard** (Node 20):
```bash
cd frontend && npm install && npm run dev
```
Open http://localhost:5173 and click **Start scenario**, then **Check in all**. About 25 seconds
later, the quiet block flags. Use **💬 Simulate a text** to rehearse the judge moment.

**Tests:**
```bash
backend/.venv/bin/python -m pytest -q backend
```

## How it fits together

```
backend/app/
  seed.py       fake Houston flood: 36 blocks, ~400 households, teams, shelters, claims
  scoring.py    urgency score 0-100, deterministic, with a reason for every point
  silence.py    expected vs actual replies per block → flags quiet blocks
  agent.py      Nemotron tool-calling loop (6 tools) + rule-based fallback; every step → trace
  extract.py    keyword extraction (fallback agent + simulator), English/Spanish
  messenger.py  ALL outbound messages; Photon goes here (mock until wired)
  simulator.py  demo mode: fake residents reply over ~25s after "Check in all"
  services.py   case operations: check-in, inbound, assign, confirm safe, sweep, claims
  claims.py     verified timeline + 3 fraud rules
  main.py       FastAPI routes (/api/...)
frontend/src/
  App.jsx       header KPIs, map, tabs, rehearsal text box
  MapView.jsx   Leaflet: flood depth, silence overlay, pins by score, teams, shelters
  panels.jsx    priority queue, quiet blocks, agent trace, claims
```

## What's left to wire (teammate)

1. **Photon 2.0.** Fill in `PhotonMessenger.send` in `backend/app/messenger.py`, and map
   Photon's webhook fields in `photon_inbound` in `backend/app/main.py`. Expose the
   backend with `ngrok http 8000` and point Photon's webhook at `/api/photon/inbound`.
   Only numbers in `ALLOWED_REAL_NUMBERS`, or people who text in live, ever get a real message.
2. **Nemotron.** Set `NVIDIA_API_KEY` and `NEMOTRON_MODEL` (a current Nemotron model with
   tool calling, from build.nvidia.com) in `backend/.env`. The header badge turns green.
   If the call fails, the rule agent takes over and the trace shows it.

## Demo-mode knobs

- `SIM_SPEED=60` means 1 real second = 1 simulated minute. Silence points grow +4/hour.
- The planted quiet block is `B4-2`, with Ruth & Harold Jenkins (on the utility medical list
  only, oxygen, never reply).
- Unknown numbers that text in become a new household in the deepest-water block.
