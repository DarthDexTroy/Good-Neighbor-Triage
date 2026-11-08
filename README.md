# LifeLine

**Warn you before. Find you during. Pay you after.** One text conversation across a catastrophe.

Built at HackUTD 2026 for the State Farm challenge *"The Worst Day, at Scale: Intelligent Catastrophe Response."* LifeLine is a concept, not an official State Farm product. **All people, phone numbers, addresses and claims in the demo are fictional.**

- Project page: https://darthdextroy.github.io/Good-Neighbor-Triage/
- Live dashboard (while our demo server is running): https://darthdextroy.github.io/Good-Neighbor-Triage/app/

## The problem

When a hurricane hits a city like Houston, the damage happens at three different moments:

- **Before:** people get generic warnings ("a storm is coming") that never say *your* car, on *your* street, will be underwater. Preventable losses happen anyway.
- **During:** thousands of people need help at once. The ones in the most danger often go quiet: dead phones, no signal, elderly neighbors who don't text. Silence looks the same as "we're fine."
- **After:** families wait weeks for claims, while storm-chasing contractors go door to door asking them to sign over their insurance benefits.

## The solution

LifeLine is an AI agent that people talk to over iMessage or SMS, in English or Spanish (text **EN** or **ES** to switch). There's no app to install. An insurer's catastrophe (CAT) manager watches the whole event on one dashboard with **Before / During / After** tabs.

### Before the storm: prevent losses
- A forecast cone shows every policy in the storm's path and the total **expected loss** in dollars.
- Each household gets a personal action text, picked from its own data:
  - *"Move your car to higher ground. Reply 1 when done."*
  - *"Board or shutter your windows. Reply 2."*
  - *"Refill medication and plan to evacuate if you use oxygen. Reply 3."*
  - *"Send us photos of your home and car."*
- Every confirmed reply adds to an **avoided-losses** counter. People are never given a dollar value.

### During the storm: no one overlooked
- Incoming texts like *"el agua está entrando, mi mamá usa oxígeno"* go to an **NVIDIA Nemotron** agent. It looks up the household, checks the flood depth, works out what they need, scores urgency, finds a suitable shelter, and replies, with every step shown in plain English.
- A transparent **0–100 urgency score** ranks everyone by need, with a reason for every point. The AI extracts facts; a formula, not the AI, decides priority. A human approves every dispatch.
- A **silence map** flags blocks where far fewer people replied than expected, so quiet households get a door-to-door sweep. Every hour of silence moves a household *up* the list.

### After the storm: fast, fair claims
- Claims are routed into three lanes:
  - **Auto-pay**: up to $2,500, pre-storm photos, minor damage, no flags. Paid within hours, with a text.
  - **Desk adjuster**: mid-size claims, reviewed remotely with photos.
  - **Field adjuster**: total losses, claims over $25,000, or anything flagged.
- **Contractor fraud rules** catch storm chasers: one contractor on many claims, inflated estimates, benefits signed within 24 hours of landfall, unlicensed contractors. Flags send a claim to a human. They never deny it.

### The business case
A scorecard on every screen shows **losses avoided**, **claim cycle time** and **cost per claim**, each next to an *assumed* industry baseline, plus the share of customers reached and the dollars held for fraud review. A "How we calculate this" table shows every formula and assumption. In production, those numbers would come from the insurer's own data.

## How it fits together

```
 Resident's phone ──iMessage──► Photon 2.0 ──► LifeLine backend (Python / FastAPI)
        ▲                                         │  • Nemotron agent (tool calling)
        └──────────── replies ◄───────────────────┤  • urgency score + silence map
                                                   │  • Before / After business rules
                                                   │  • simulated storm clock (T−72h → T+48h)
                                                   ▼
                                   CAT manager dashboard (React + Leaflet map)
```

- **Photon 2.0** carries real iMessages. The backend checks Photon for new messages and replies into the same conversation, so no public webhook is needed.
- **NVIDIA Nemotron 3.5 Super** runs the triage agent. If the model is unavailable, a rule-based agent takes over, so no text goes unanswered.
- A **simulated clock** lets the demo jump between phases: 72 hours before landfall, landfall, and 48 hours after.
- About 400 fictional households, plus response teams, shelters, contractors and claims, are generated on every restart. In demo mode, fake residents reply on their own.

## Run it

**Backend** (Python 3.11+)
```bash
cd backend
uv venv .venv && uv pip install -r requirements.txt     # or: python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                                     # then add your keys (see below)
cd .. && backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
```

**Dashboard** (Node 18+)
```bash
npm --prefix frontend install
npm --prefix frontend run dev                            # http://localhost:5173
```

**Keys** in `backend/.env`. The app runs without any keys, using the rule-based agent and a phone simulator.

| Variable | What it's for |
|---|---|
| `NVIDIA_API_KEY` | Nemotron (`nvapi-…`, free at build.nvidia.com) |
| `PHOTON_API_KEY`, `PHOTON_PROJECT_ID` | Photon 2.0 beta project (`pho_sk_…`, `pho_prj_…`) |
| `DEMO_FAMILY_PHONE` | Your own phone number. The demo family uses it, so real texts reach you. |

Check the integrations: `backend/.venv/bin/python backend/scripts/nemotron_check.py --run` and `backend/.venv/bin/python backend/scripts/photon_check.py`.

**Tests:** `backend/.venv/bin/python -m pytest -q backend`

**Public demo:** with the backend running, `scripts/publish_tunnel.sh` opens a Cloudflare tunnel and points the GitHub Pages dashboard at it.

## Demo walkthrough

1. Start the backend. Text **"hola"** from the demo phone to your Photon number: a shared line can't send the first message.
2. **Restart scenario.** It starts at **Before, T−72h**, with the forecast cone, policies in the path and expected loss.
3. **Send action texts.** The phone gets its personal action list. Reply **1**, and losses avoided go up.
4. **During**, then **Check in all**. Within about 90 seconds, send *"el agua está entrando, mi mamá usa oxígeno"*. The family jumps to **#1**. Open **Agent trace** to see Nemotron's steps.
5. **Quiet blocks**: sweep the flagged block.
6. **After**, then **Run auto-pay**. The family's $1,840 claim is paid and the phone gets the approval text. Show the **Gulf Rapid Roofing** contractor flags and **How we calculate this**.

## Repository layout

```
backend/app/       API, agent, scoring, silence map, Before/After rules, seed data, Photon client
backend/tests/     pytest suite
frontend/src/      React dashboard (Before / During / After tabs, map, claims board, phone simulator)
scripts/           publish_tunnel.sh: share the local backend with the public dashboard
```
