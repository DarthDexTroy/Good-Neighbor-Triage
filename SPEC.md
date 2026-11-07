# Lifeline: Build Spec (HackUTD 2026, State Farm Challenge)

**One line:** Lifeline helps a State Farm catastrophe team find *everyone* in a disaster
zone, reach them by text and voice, rank them by real need, dispatch help, and close
each case only when the person is confirmed safe.

| Decision | Choice |
|---|---|
| Scenario | Houston flash flood, Harvey-style. **All data is fake.** |
| Main user | State Farm catastrophe (cat) team coordinator, working with responders |
| Stack | React + Vite + Tailwind + Leaflet frontend; Python FastAPI + SQLite backend |
| Sponsors | **Photon 2.0** (SMS / iMessage / voice), **NVIDIA Nemotron** (multi-step triage agent) |
| Time | 12–20 hours; plan assumes ~16 |
| Live moment | A judge texts the Photon number, and their case appears and re-ranks live |

---

## 0. First hour, before any code (both people)

- [ ] **Get Photon 2.0 credentials** at the sponsor booth. Ask: how to send SMS/iMessage,
      how inbound webhooks work, whether voice is available, and any rate limits. The live
      demo depends on this, so it comes first.
- [ ] **Get an NVIDIA API key** (build.nvidia.com). Pick a current **Nemotron** model that
      supports **tool / function calling** and confirm the model ID there. The API is
      OpenAI-compatible (`https://integrate.api.nvidia.com/v1`), so the `openai` Python
      client works.
- [ ] Set up a shared GitHub repo and an `.env` (never commit keys).
- [ ] Get a public URL for the webhook: `ngrok` or `cloudflared` pointing at FastAPI.

---

## 1. The core loop

```
 Hazard zone ─► Roster of everyone inside ─► Photon outreach (SMS/iMessage/voice)
                                                    │
                       replies ◄────────────────────┘
                          │
                Nemotron triage agent (tools) ─► Case + urgency score + reasons
                          │
        Cat-team dashboard: map · ranked queue · silence map · agent trace
                          │
     Human approves dispatch ─► team assigned ─► CONFIRMED SAFE ─► claim draft
```

---

## 2. Demo script (3 minutes) — build exactly what this needs

1. **(0:00) Hook.** "During Hurricane Harvey, tens of thousands of Houstonians needed rescue
   (look up and cite an exact figure). The people who needed help most often couldn't
   ask for it."
2. **(0:20) Flood hits.** Click "Start scenario". A flood polygon appears over a fake
   Houston neighborhood. **312 households** inside light up from four sources:
   policyholders, the utility's medical-device list, app users and census estimates.
3. **(0:40) Reach everyone.** Click "Check in all". Photon sends texts. Simulated replies
   stream in (SAFE / HELP / free text); the map turns green, yellow and red.
4. **(1:00) Live judge moment.** A judge texts: *"water coming in, my mom is on oxygen and
   the power is out."* The **agent trace** panel shows Nemotron's steps: look up
   household → check hazard → extract needs → compute score → match shelter → draft
   reply. The judge's case jumps into the **top 3**, with reasons, and the judge gets a
   reply on their phone. Point out what's *above* it: high-need households (oxygen,
   insulin) who haven't replied. "The system doesn't just rank whoever texts. It knows
   who's at risk and still silent."
5. **(1:40) No one overlooked.** Toggle the **silence map**. One block sent 2 replies when
   about 14 were expected, so it's flagged. Inside it is an elderly couple who never had
   the app (on the utility medical list only). Click "Send sweep team".
6. **(2:10) Dispatch and close.** Approve the boat assignment (a human approves). Mark the
   couple **Confirmed safe**. Their case closes.
7. **(2:30) Recover.** Open the claim draft: a verified timeline (texts, GPS, rescue time)
   is attached, so it's ready to pay fast. Show one **flagged** claim: a claim filed from
   a location that never flooded, by someone whose phone checked in safe 40 miles away.
8. **(2:50) Close.** "Lifeline ranks need, not noise, and treats silence as a signal."

---

## 3. MUST WORK for the demo vs NICE TO HAVE

### MUST WORK (build this first, in this order)
1. **Fake data generator.** Households, blocks, hazard zone, teams, shelters (see §4).
2. **Urgency score + reasons.** A deterministic formula (§5), unit-tested.
3. **Dashboard:** Leaflet map with colored pins and flood polygon, plus a ranked queue
   with score and reasons. Polls the API every 2s (simple, reliable).
4. **Photon inbound webhook → agent → case update.** The live judge text works end to end.
5. **Photon outbound reply** to the person who texted.
6. **Nemotron agent with at least 4 real tool calls** and a visible **agent trace** panel.
7. **Silence map:** block shading plus a "flagged blocks" list.
8. **Case lifecycle:** unreached → contacted → needs help → assigned → **confirmed safe**,
   with a human "Approve dispatch" button.
9. **Claim draft screen** with a verified timeline, plus **one** flagged-fraud example.
10. **Demo mode switch** (`DEMO_MODE=1`): simulated replies stream in on a timer, and if
    Photon or Nemotron is down, a mock messenger and rule-based agent take over so the
    demo never dies.

### NICE TO HAVE (only after every MUST works end to end)
- Photon **voice call** to silent households (text-to-speech: "Press 1 if safe, 2 if you
  need help").
- **Spanish** detection and replies (Houston is about 45% Hispanic).
- **"Report someone else"**: "my neighbor at 412 Elm uses a wheelchair" creates a new case.
- **Drift cone** for a person last seen in water: current direction × speed × time, drawn
  as a widening cone at 30/60/120 minutes.
- Shelter matching UI with capacity bars (wheelchair access, power, infant supplies, pets).
- Team auto-suggestion (nearest team with capacity, by type).
- Medication countdown ("insulin runs out in 14h"), which raises the score as time passes.
- Calm mode reply: a short reassurance text while help is coming (no medical advice).
- Audit log viewer (who saw or changed which case): the cyber/privacy story.
- Role-based view: responders see location + needs only; policy details are hidden.

### CUT (say so if judges ask; it shows judgment)
Real satellite or computer-vision detection, disaster prediction models, go-bag checklist,
full medication scheduler, video for kids. "Hazard data is simulated; in production it
comes from NWS, USGS and flood-gauge feeds. We built the decision layer that's missing."

---

## 4. Fake data (Python seed script → SQLite)

Generate around a real-looking Houston area (e.g. centered near 29.76, -95.37), all
names and numbers fake (`Faker`, phone numbers in the 555 range).

**blocks** (~25): `id, polygon, population, svi (0–1 social vulnerability), flood_depth_ft`

**households** (~400 total, ~312 inside the zone):
`id, name, address, lat, lng, block_id, phone, language (en/es), source
(policyholder | utility_medical | app | census_estimate), consent (bool), policy_number?,
members[] {age, mobility, oxygen, dialysis, insulin_hours_left, infant}, pets`

- About 8% have power-dependent medical needs and about 10% have an infant.
- About 15% are age 75+. About 20% speak Spanish.
- Plant **one flagged block** with low replies, high SVI and deep water, holding the
  elderly couple from the demo (source = `utility_medical` only, no app, no reply).

**teams** (~8): `id, type (boat | medical | supply), lat, lng, capacity, status`
**shelters** (~4): `id, lat, lng, capacity, occupancy, wheelchair, backup_power, infant_supplies, pets`
**cases:** `household_id, status, score, reasons[], last_contact, assigned_team, needs{}`
**messages:** `household_id, direction, channel, body, ts`
**claims** (~6): a timeline built from messages and cases; one planted suspicious claim.
**audit_log:** `ts, actor, action, case_id`

**Live judge path:** an inbound text from an **unknown number** creates a new household
at a demo address inside the flood zone. Pre-register the team's own phones as known
households for rehearsal.

> Only real team or judge phones (who opt in on the spot) ever get messages. Every seeded
> number is fake and routes to the mock messenger.

---

## 5. Urgency score (0–100, deterministic, explainable)

The model **extracts facts**; the **formula scores**. Never let the language model invent
a number. That's the "explainable, human in the loop" answer.

| Factor | Points | Example reason string |
|---|---|---|
| Flood depth at location | 0–25 (depth_ft × 5, cap 25) | "Water ~4 ft at address" |
| Power-dependent device + power out | +30 | "Oxygen concentrator, power out" |
| Insulin / dialysis running out < 24h | +20 | "Insulin runs out in 14h" |
| Infant / age 75+ / mobility limit | +10 each, cap 20 | "Wheelchair user, age 81" |
| Life-threatening danger reported ("trapped", "water rising", "on roof", medical emergency) | +30 | "Reported: water coming in" |
| Generic "HELP" | +15 | "Asked for help" |
| Silence (outreach sent, no reply), or no phone on file at all | +4/hour, cap 20 | "No reply for 3h" |
| In a flagged quiet block, no reply | +10 | "In a block that's unusually quiet" |
| Self-reported safe, no danger | capped at 10 | "Self-reported safe, awaiting confirmation" |
| Already assigned a team | −30 | "Boat 2 en route" |

Clamp to 0–100. Store `reasons[]` and show them under every score.
**Fairness rule:** sending more messages never adds points. Need does.

## 6. Silence map

For each block in the hazard zone:
```
expected = households_in_zone × 0.7          # baseline reply rate within 1h
ratio    = replies / expected
priority = (1 − ratio) × (flood_depth_ft / max_depth) × (0.5 + svi)
flag if ratio < 0.4 and households_in_zone ≥ 5
```
Shade blocks by `priority`. A "Flagged blocks" list offers "Send sweep team" and
"Voice-call all silent households" (nice to have). Every unreached household in a flagged
block also gets the silence points in its score.

---

## 7. Nemotron triage agent (multi-step, uses tools)

Triggered by every inbound message (and in demo mode, by simulated replies).
OpenAI-compatible tool-calling loop against the NVIDIA API, max ~6 steps.

**Tools (Python functions the model can call):**
| Tool | Does |
|---|---|
| `lookup_household(phone)` | Finds or creates the household; returns members and needs on file |
| `get_hazard(lat, lng)` | Flood depth, power status and block for a location |
| `update_needs(household_id, needs, danger_signals)` | Saves the facts the model extracted |
| `compute_score(household_id)` | Runs the §5 formula; returns score and reasons |
| `find_shelter(household_id)` | Nearest shelter that fits the needs (wheelchair, power, infant, pets) |
| `create_report(about_address, description)` | *(nice)* "Report someone else" creates a new case |
| `send_reply(household_id, text)` | Sends via Photon; safety info and status only |

**Guardrails**
- The agent **cannot dispatch teams**. It can only recommend; a human clicks Approve.
- Replies: short, calm, no medical advice; "If in immediate danger, call 911."
- Every tool call is written to `agent_trace` and `audit_log`, and shown live in the UI.
  This panel is how you prove "beyond a chatbot" to the Nemotron judges.
- Fallback: if the API errors, use a keyword-based extractor plus a template reply.

## 8. Photon integration

- **Outbound check-in** ("Check in all" button): *"State Farm Lifeline: flooding reported
  near you. Reply SAFE, HELP, or tell us what you need. If in immediate danger call 911."*
- **Inbound webhook** `POST /photon/inbound` → store message → run agent → reply.
- Wrap Photon behind one interface so a mock can swap in:
  `messenger.send(to, text, channel)` and `messenger.call(to, script)` (nice).
  Fill in the real calls from Photon 2.0's docs at the booth. Don't guess the API.

## 9. API (FastAPI)

```
POST /scenario/start         seed + activate flood zone
POST /outreach/checkin_all   bulk Photon send (mock for fake numbers)
POST /photon/inbound         webhook → agent
GET  /cases?sort=score       ranked queue (score, reasons, status)
GET  /blocks                 silence-map data
GET  /agent_trace?limit=20   live agent steps
POST /cases/{id}/assign      human-approved dispatch {team_id}
POST /cases/{id}/safe        confirmed safe → closes case, builds claim draft
GET  /claims, /claims/{id}   claim drafts + fraud flags
```

## 10. Claims and fraud (small, in the demo) — owner: accounting/cyber teammate

- **Verified timeline** per household: outreach sent → reply (with time) → location →
  team assigned → confirmed safe. Shown as a vertical timeline on the claim draft.
- **Three fraud rules** (simple, explainable):
  1. Claim address is outside the hazard zone or has flood depth 0.
  2. The policyholder's phone checked in "SAFE" from more than 25 miles away during the event.
  3. Duplicate claim: same address or phone across two policies.
- Pitch line: "Honest claims arrive pre-verified and get paid faster; suspicious ones get
  a second look. Verification is a side effect of rescuing people."

## 11. Who builds what

| CS teammate | You (accounting + cyber) |
|---|---|
| FastAPI skeleton, SQLite models | Seed data generator (§4) |
| Photon webhook + messenger wrapper | Score + silence formulas with tests (§5–6) |
| Nemotron agent loop + tools (§7) | Claims, timeline and fraud rules (§10) |
| Agent trace endpoint | Dashboard queue + claim screen (React, with Claude Code) |
| Leaflet map + polygons | Pitch deck, demo script, judge Q&A prep (`JUDGES.md`) |

## 12. Timeline (~16h; if you have 12, cut the nice-to-haves entirely)

| Hours | Milestone |
|---|---|
| 0–1 | Credentials, repo, `.env`, tunnel. **A Photon test text reaches a phone.** |
| 1–4 | Seed data, DB, `/cases`, score formula; map + queue render from fake data |
| 4–7 | Inbound webhook → agent (tools) → score → reply. **Judge-text path works.** |
| 7–9 | Silence map, case lifecycle, approve dispatch, confirmed safe |
| 9–11 | Claim draft + fraud flags; demo mode with streaming simulated replies |
| 11–13 | Nice-to-haves by value: voice call → Spanish → report-a-neighbor → drift cone |
| **T-3h** | **Feature freeze.** Fix bugs, polish UI, rehearse 3× end to end |
| T-2h | **Record a backup demo video** in case Wi-Fi or Photon fails on stage |
| T-1h | Devpost write-up: name both sponsors, explain the agent trace and silence map |

## 13. Risks → fallbacks

| Risk | Fallback |
|---|---|
| Photon setup is slow | Mock messenger with a fake phone UI on screen; keep working on Photon in parallel |
| Nemotron tool calling is flaky | Keyword extractor + templates; show the trace from a recorded run |
| Venue Wi-Fi dies | Phone hotspot; backup video |
| Judge texts something weird | The agent's default path still creates a case and asks a follow-up |
| "Isn't this FEMA's job?" | "Cat teams already check on policyholders after events; Lifeline makes that fast, complete and shareable with responders, with consent." |
