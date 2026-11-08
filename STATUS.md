# STATUS (Phil → Cristobal)

Latest push on `main`. Every Build-list item in HANDOFF-PHIL.md is done **except #1 (sponsor check)**. 18 backend tests pass, and the full Reyes journey was clicked through in the browser.

> Note: the frontend is in **`frontend/src/`**, not `src/` at the repo root as HANDOFF-PHIL.md says.

## How to run

```bash
cd backend && uv venv .venv && uv pip install -r requirements.txt   # first time only
backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
npm --prefix frontend install && npm --prefix frontend run dev      # http://localhost:5173
backend/.venv/bin/python -m pytest -q backend                       # 18 tests
```

`DEMO_MODE=1` (the default) turns on simulated replies. The uvicorn command above runs **without `--reload`**, so restart it after editing backend code.

## What works

| # | Item | Where |
|---|---|---|
| 2 | `POST /api/phase {phase}` jumps to T−72h / T+0 / T+48h. Negative time works in the clock, scoring and the silence map (tested). | `clock.py`, `services.set_phase` |
| 3 | Before / During / After tabs (clicking one jumps the clock) and a phase banner with T-time. During is unchanged. | `App.jsx`, `phases.jsx` |
| 4 | Fake forecast cone that narrows at T−48h and T−24h; policies in path, insured value, expected loss (§4.1 formula on hover), vulnerable households; homes shaded by expected loss | `GET /api/exposure` |
| 5 | **Send action texts** jumps to T−48h and sends personalized en/es texts. Replies `1` / `2` / `3` / "foto" confirm car / shutters / meds / photos, with an ack text. Other policyholders confirm on their own over about 20 s. | `POST /api/before/send_actions`, `GET /api/before/actions` |
| 6 | Claims board: Auto-pay / Desk / Field, fake adjuster capacity and backlog, flags, lane reason | `GET /api/recovery/claims` |
| 7 | Scorecard in the banner on every tab: avoided $, cycle time, cost per claim, reached %, $ held for review; "How we calculate this" modal. Every baseline is labeled assumed. | `GET /api/scorecard` |
| 8 | Auto-pay rule (≤ $2,500, pre-storm photos, minor damage, 0 flags). **Run auto-pay** pays and texts the person. Older auto-pay claims are seeded as already paid. | `POST /api/recovery/run_autopay`, `POST /api/claims/{id}/autopay` |
| 9 | All 4 contractor rules plus the contractor list. Gulf Rapid Roofing: 9 claims, all 4 flags, all routed to Field. Scam-warning text button. | `GET /api/contractors`, `POST /api/recovery/warn_scams` |
| 10 | Placeholder before/after SVG photo pairs on claims, labeled "Simulated damage assessment" | `frontend/public/photos/` |
| | Phone simulator (bottom right, every tab) shows the Reyes thread live, with quick-reply chips per phase | `GET /api/thread?phone=` |
| | Message templates now start with "Good Neighbor", not "State Farm Lifeline" | `services.py`, `agent.py` |

## What's broken / not done

- **#1 Sponsor check: DONE, both live (verified 2026-11-08).**
  - **Nemotron:** `nvidia/nemotron-3.5-super-vl-120b-a12b`, thinking off. `scripts/nemotron_check.py --run` passes: the model ran the whole tool loop (lookup → hazard → needs → score → shelter → reply). Replies are forced to start with "Good Neighbor".
  - **Photon 2.0 beta:**
    - Project `good-neighbor`; shared iMessage line **+1 (628) 263-4622**.
    - `app/photon.py` polls received messages; `PhotonMessenger.send` replies into the person's space.
    - Round trip verified with a real iPhone.
    - `DEMO_FAMILY_PHONE` makes that phone the Reyes family.
  - **Before each demo:** restart the backend, then iMessage "hola" from the demo phone to +1 (628) 263-4622. The backend only reads messages sent after it starts, and a shared line can't text first.
  - Keys live in `backend/.env` (git-ignored). `photon-bridge/` (Spectrum) is an unused alternative.
- **Data change to know about:** Rosa Reyes also uses a walker (`mobility`). Without it the family scored 85 and ranked #3–4 behind other simulated households. With it they score 95 and rank #1.
- **Timing caveat (During):** the silent Jenkins couple keeps gaining points and passes the Reyes family at about T+2h30m, roughly 2.5 real minutes after you click During. **Send the Spanish text within about 90 s of opening During.** (Jenkins going to the top later is the "no one overlooked" story.)
- `shelters.py` still isn't mounted in `main.py`. Not on the build list.
- Not built, per the handoff: shelters view, escalation ladder, third-party reports, location confirm, mitigation list (§6.4).
- Numbers are at **our seeded scale**: 226–234 policies, about $17M expected loss. They are not the "18,400 policies / $412M" in the spec's demo table, so say "in this simulated neighborhood."

## Demo steps that are safe to show (tested end to end)

1. **Restart scenario.** Starts at **Before, T−72h**. The cone is up, with policies in the path and expected loss.
2. **Send action texts.** The clock goes to T−48h and the cone narrows. Open **📱 Phone simulator** to see the Reyes family's Spanish text.
3. Tap the **`1`** chip. "¡Gracias! Marcamos: carro movido." appears and *losses avoided* goes up (about $18.5K for their car).
4. Click **During**, then **Check in all**. Right away, tap the chip **"el agua está entrando, mi mamá usa oxígeno"**. The family is **#1 at 95**.
5. After about 30 s, open **Quiet blocks** and sweep B4-2 (unchanged Lifeline flow).
6. Click **After**. The Reyes claim #DEMO-1042 ($1,840, minor, before/after photos) is at the top of **Auto-pay**. Click **Run auto-pay** and the phone shows "su reclamo #DEMO-1042 fue aprobado. $1,840 va en camino."
7. Show the **Gulf Rapid Roofing** card (4 flags, 9 claims, all in Field), then **How we calculate this** on the scorecard.

To get the full scorecard, do Before before After. If you jump straight to After, avoided $ counts only the photo savings.

## New endpoints (also in CONTRACT.md)

```text
POST /api/phase {phase}            → {now, clock, phase}
POST /api/scenario/start {phase?}  → stats (default phase "during" so old tests/scripts behave)
GET  /api/exposure                 → {cone, totals{policies, insured_value, expected_loss, vulnerable, households}, homes[], formula}
POST /api/before/send_actions      → {sent, now}         (409 after landfall)
GET  /api/before/actions           → {households, by_type{car,shutters,meds,photos:{sent,confirmed}}}
GET  /api/recovery/claims          → {lanes{autopay[],desk[],field[]}, capacity{desk,field}, rule}
POST /api/claims/{id}/autopay      → {paid_amount, paid_t}  (409 if not in auto-pay lane)
POST /api/recovery/run_autopay     → {paid, claim_ids}
GET  /api/contractors              → [{id,name,phone,licensed,flags[],claims[],estimate_total}]
POST /api/recovery/warn_scams      → {sent}
GET  /api/scorecard                → {avoided, avoided_by_type, prepared_high_risk, cycle_time_days, cycle_baseline_days,
                                      cost_per_claim, cost_baseline, reached_pct, fraud_held, assumptions{}}
GET  /api/thread?phone=            → {household, messages[]}
```
