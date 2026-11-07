# SPLIT: who builds what (Lifeline → Good Neighbor Triage)

Based on GAPS.md (2026-11-07). **Lifeline is the base. Change the spec to fit Lifeline, not the other way around.**

**Name:** The product is now **Good Neighbor Triage** ("Good Neighbor" for short). Change only the text people see. **Do not rename the repo, folders, files or code.** It's a concept *for* State Farm, so don't use their logo or make texts look like official State Farm messages.

## Rule 0: keep what already works

Do **not** spend time on these spec details. Lifeline's version is fine or better:

- Score weights: keep `scoring.py` as it is (it's tested). In the UI, just add band names: ≥70 Critical, 40–69 High, 15–39 Medium, <15 Low.
- Flood blocks instead of a polygon: keep the blocks.
- Polling every 2s instead of SSE: keep polling.
- No `/intake` route: keep `/api/photon/inbound` and `/api/dev/inbound`.
- Fake grid instead of named neighborhoods, no Vietnamese: fine.
- The full §5.1 extraction JSON: only add the fields listed below.
- **Silence map + quiet blocks:** keep them. This is your strongest "no one overlooked" feature, so put it in the pitch.

## Ownership (so the two Claude sessions never edit the same file)

| Teammate owns | You own |
|---|---|
| `backend/app/*`, **except** the new `shelters.py` | `frontend/*` |
| Backend tests | **New** `backend/app/shelters.py` (FastAPI `APIRouter`) |
| `main.py` (adds one line: `app.include_router(shelters.router)`) | Slides, pitch, demo script |

If you need something from the other person's files, ask them. Don't edit their files.

---

## Teammate's lane (backend + agent), in priority order

**P0: sponsor prizes first (first hour)**
1. Get a Nemotron API key and run the agent tool loop for real (`agent.py`). Right now it has never run without the fallback. **No working Nemotron means no Nemotron prize.**
2. Get Photon 2.0 sending and receiving for real. Fix the guessed field names in `/api/photon/inbound`. Set up the tunnel.

**P1: the demo script needs these**
3. Send the acknowledgment **before** the agent runs (GAPS #1).
4. Status text to the person on `assign()`, plus on shelter accept (GAPS #9). Return `eta_min` from `POST /api/cases/{id}/assign`.
5. Safety instructions matched to the hazard: flood, trapped, medical, power out (GAPS #10). Use templates, and let the LLM translate them for languages other than en/es.
6. Parse replies of `1`/`2`/`3` and change the outreach wording to match (GAPS #6).
7. Escalation ladder (GAPS #7): retry text at +15 sim min, log a "voice call placed" message at +30, set `status: welfare_check` at +45, and run it twice as fast for vulnerable people. Add `POST /api/clock/advance {minutes}` → `{now}`.
8. Third-party report (GAPS #5): add `other_person` to the extraction, add a `create_linked_case` tool, set `case.reported_by`, and merge into an existing household when the address or name matches.

**P2**
8b. Rename in message templates: texts start with "Good Neighbor here…". Text change only.
9. FNOL (GAPS #15): add `claim_number` ("DEMO-####") and `fnol {date_of_loss, peril, damage, injuries, temp_housing, photos: []}`. Send the text "We started your claim, #…".
10. Location confirm (GAPS #4): add `location_confirmed: false` for policy-address guesses and send one "Are you at …? Reply YES" text.
11. Add `injury` and `people_count` to the extraction, and feed them to the scorer only if it takes 15 minutes or less.

## Your lane (frontend + shelters + pitch), in priority order

**P1**
1. **Responders view** (GAPS #8): the same queue component, filtered to `needs_help`, `welfare_check` and `assigned`. Its "Take case" button calls the existing `POST /api/cases/{id}/assign`, then shows the ETA.
2. **Fast-forward button** that calls `POST /api/clock/advance {minutes: 15}`, plus a **Welfare check** badge on queue cards. Until the teammate's endpoint exists, the button can be disabled.
3. **Score band labels** (Critical/High/Medium/Low) on queue cards.
4. **Phone simulator shows the reply thread:** poll the existing `GET /api/cases/{id}/messages` (GAPS #12).

**P1: Shelters (you build both the backend and the view)**
5. In `backend/app/shelters.py`, add fake data plus these routes:
   - `GET /api/shelters/{id}` → `{intake[], roster[] (wheelchair, infant, oxygen, pets), meds[{name, drug, due_t, given}], supplies[{item, count, low_at}]}`
   - `POST /api/shelters/{id}/accept {case_id}` → updates the shelter. Call the teammate's send-message function to text the person (ask the teammate for its name).
   - `POST /api/shelters/{id}/meds/{med_id}/given`
6. **Shelters view:** four simple tables. Show medication doses past `due_t` in red, and supplies below `low_at` in yellow.

**P2**
6b. Rename in the UI: dashboard header, page title, browser tab → "Good Neighbor Triage". Text change only.
7. Clicking a map pin scrolls to the queue card and opens it (GAPS #11).
8. Change the fraud badge label to "Flagged for adjuster review" (frontend text only).
9. Show FNOL fields and the claim number on the Claims tab once the teammate's #9 is done.
10. Slides and pitch. Rewrite the demo script around Lifeline: silence map, check-in to all 277 households, the oxygen + Spanish text, fast-forward, the welfare check, "Take case", the status text, and the claim with its fraud flag.

---

## New contract (agree on this before you start; add it to CONTRACT.md)

```text
POST /api/clock/advance            {minutes}            → {now}                [teammate]
POST /api/cases/{id}/assign        {team_id?}           → {team, eta_min}      [teammate, adds eta_min]
case.status                        + "welfare_check"                           [teammate]
case.reported_by                   household_id | null                         [teammate]
case.location_confirmed            bool                                        [teammate]
case.escalation_step               0..3                                        [teammate]
claim.claim_number, claim.fnol     see teammate P2 #9                          [teammate]
GET  /api/shelters/{id}            → {intake, roster, meds, supplies}          [you]
POST /api/shelters/{id}/accept     {case_id} → {ok}                            [you]
POST /api/shelters/{id}/meds/{med_id}/given → {ok}                             [you]
```

## Merge rhythm

- Each person works on their own branch. Merge into `main` every 1–2 hours.
- Checkpoints: (1) Nemotron + Photon real; (2) escalation + Responders view work together; (3) the full demo runs twice in a row → **feature freeze**.
