# GAPS: Good Neighbor Triage spec vs. the Lifeline codebase

Compares **Tier A** of `good-neighbor-triage-spec.md` against the code in this folder as of
2026-11-07. No code was changed to write this.

**Summary:** 2 DONE · 7 PARTIAL · 6 MISSING

| # | Tier A item | Status | What exists |
|---|---|---|---|
| 1 | Inbound text → case + instant acknowledgment in sender's language | **PARTIAL** | `POST /api/photon/inbound` and `/api/dev/inbound` create or update a case by exact phone match. But the reply is sent at the **end** of the agent run, not before it, and templates exist only in English and Spanish. |
| 2 | Agent extraction (§5.1 JSON) + translation to English | **PARTIAL** | Nemotron tool loop exists (`agent.py`), untested without a key. Its `update_needs` tool takes booleans (oxygen, dialysis, insulin_low, infant, elderly, mobility, power_out), danger enum and self_reported_safe. Missing §5.1 fields: `english_text`, `injury` level, `people_count`, `other_person`, `location_text`, `is_claim_related`. No translation, no Pydantic validation or retry. Keyword fallback handles English and Spanish only. |
| 3 | Rule-based urgency score with visible "why" | **DONE** | `scoring.py`: deterministic 0–100 score with a reason string per point, shown on every queue card; tested. **Weights differ from §5.2:** flood depth up to +25, oxygen with power out +30, insulin/dialysis +20, vulnerable up to +20, danger +30 (life-threatening) or +15 ("help"), silence +4/h up to +20, quiet block +10, assigned −30. No injury levels, separate "trapped" factor or per-person points. Colors at 70/40/15, but no named Critical/High/Medium/Low bands. |
| 4 | Missing location → policy address "unconfirmed" + one confirm text | **MISSING** | Known phones use the address on file (not marked unconfirmed). Unknown phones get a fake demo address in the deepest-water block. No confirm follow-up. |
| 5 | Linked third-party cases + merge | **MISSING** | No `reported_by` link, no create-case-for-other-person tool, no merge by address or name. Matching is by exact phone only. |
| 6 | Proactive outreach "1 = safe, 2 = need help, 3 = emergency" to policyholders in flood zone | **PARTIAL** | `POST /api/outreach/checkin_all` texts every household with a phone in flooded blocks (all sources, not just policyholders; 277 sent). The wording is "Reply SAFE, HELP, or tell us what you need", and replies of **1/2/3 aren't parsed**. |
| 7 | Escalation ladder + fast-forward demo clock | **MISSING** | No retry text, logged voice call, welfare-check status or double speed for vulnerable people. Related pieces exist: a simulated clock running at 60× (`clock.py`, `SIM_SPEED`), silence points growing +4/h, and a quiet-block flag with "Send sweep team". No fast-forward button. |
| 8 | Three dashboard views (CAT, Responders, Shelters) on one shared queue | **PARTIAL** | **CAT view exists:** queue, map, KPIs (in zone, replied/contacted, need help, no phone, quiet blocks, confirmed safe), agent trace, claims tab. Fraud badges are on the Claims tab, not on queue cards. **Responders view: missing.** There's no filtered view, "Take case" or ETA; dispatch is an "Approve dispatch" button in the CAT queue. **Shelters view: missing.** Shelters are only map pins with capacity, occupancy and features; no intake list, special-needs roster, medication schedule or supplies. |
| 9 | Status text when responder takes case / shelter accepts | **MISSING** | `services.assign()` and `confirm_safe()` don't message the person. There's no shelter-accept action. |
| 10 | Safety instructions matched to hazard | **MISSING** | Replies are generic ("…If in immediate danger call 911"), not per hazard. |
| 11 | Map: urgency pins, flood polygon, click pin opens case | **PARTIAL** | Leaflet with OpenStreetMap: pins colored by score, teams, shelters, silence overlay. Flooding is shown as **shaded grid blocks by depth**, not a polygon. Clicking a pin highlights its queue card and zooms the map, but doesn't scroll to or open the card. |
| 12 | Phone simulator panel using the same intake endpoint | **PARTIAL** | The "💬 Simulate a text" panel posts to `/api/dev/inbound`, which runs the same `handle_inbound()` as the Photon webhook but at a **different URL**. The panel doesn't show the reply thread. |
| 13 | Fake data: ~200 cases, ~500 policyholders, 3 shelters, 4 responder teams | **PARTIAL** | 401 households, each with one case; all start "unreached", and stages come from the live simulator, not the seed. 234 policyholders (181 in zone), 92 app users, 28 on the utility medical list, 47 census estimates with no phone. English and Spanish only, no Vietnamese. **4 shelters** and **8 teams** (4 boat, 2 medical, 2 supply; no welfare-check team). 6 claims, 3 planted for fraud. Fake grid near downtown Houston, not named neighborhoods. |
| 14 | Fraud flags: duplicate claim + out-of-zone, on claim drafts only | **DONE** | `claims.py`: same address under a different policy, out of zone (block flood depth = 0), plus an extra rule for a SAFE check-in more than 25 miles from the property. Shown as a "Review" badge with reasons on the Claims tab only; rescue is never blocked. The label isn't the spec's "for adjuster review". |
| 15 | FNOL draft button on a safe case | **PARTIAL** | "Confirm safe" auto-creates a claim draft for policyholders, with a verified timeline of messages and actions. It lacks FNOL fields (date of loss, peril, damage, injuries, temporary housing, photo placeholder), a claim number, and the "We started your claim" text. There's no separate button. |

---

## API endpoints that exist (`backend/app/main.py`, FastAPI on :8000)

| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/health` | → `{ok, demo_mode, nemotron, photon}` |
| POST | `/api/scenario/start` | → `{blocks, households, in_zone}` (wipes the DB and reseeds) |
| POST | `/api/outreach/checkin_all` | → `{sent}` (starts the simulated reply stream if `DEMO_MODE=1`) |
| POST | `/api/photon/inbound` | `{from or sender or phone, text or body or message, channel?}` → `{ok}`; agent runs as a background task. **Field names are guesses; map to Photon 2.0.** |
| POST | `/api/dev/inbound` | `{phone, text}` → `{ok}` (rehearsal, same handler) |
| GET | `/api/state` | → full dashboard snapshot (shape below); polled every 2s |
| POST | `/api/cases/{case_id}/assign` | `{team_id?}` → `{team}`; picks a suggested team if omitted; 409 if none free |
| POST | `/api/cases/{case_id}/safe` | → `{claim_id or null}` |
| POST | `/api/blocks/{block_id}/sweep` | → `{team}` (nearest free boat to a quiet block) |
| GET | `/api/claims` | → list of claims with `flags[]` and `timeline[]` |
| GET | `/api/cases/{case_id}/messages` | → messages for one case |

No SSE `/events` endpoint (polling only), and no `/intake` route by that name.

## Data shapes (`backend/app/db.py`: JSON documents in SQLite)

Times (`t`, `outreach_at`, `last_reply_at`) are **simulated minutes since the flood**.

```text
household  {id, name, address, lat, lng, block_id, phone|null, language: "en"|"es",
            source: policyholder|app|utility_medical|census_estimate|live,
            consent, policy_number|null, pets, hidden_from_map?,
            members: [{age, infant?, oxygen?, mobility?, insulin_hours_left?, dialysis?}]}

case       {id (= household id), household_id,
            status: unreached|contacted|needs_help|self_reported_safe|assigned|confirmed_safe,
            needs: {oxygen, dialysis, insulin_low, infant, elderly, mobility, power_out},
            danger: [water_rising|trapped|roof|medical_emergency|asked_help],
            outreach_at, last_reply_at, assigned_team, shelter_id, summary?}

block      {id "B<row>-<col>", bounds [s,w,n,e], center [lat,lng], flood_depth_ft, power_out, svi}
           + in /api/state: {households, replies, expected, ratio, priority, flagged}

team       {id, name, type: boat|medical|supply, lat, lng, status: available|busy, case_id}
shelter    {id, name, lat, lng, capacity, occupancy, wheelchair, backup_power, infant_supplies, pets}
claim      {id "C-<household id>", household_id, status: "draft", planted: null|far_checkin|duplicate}
           + in /api/claims: {name, address, policy_number, flood_depth_ft, flags[], timeline[]}
message    {id, household_id, direction: in|out, channel, body, t, lat?, lng?, via?: mock|photon}
trace      {id, t, engine: nemotron|rules|simulated|nemotron→rules, household_id, name, tool, args, result}
audit      {id, t, actor, action, case_id}
```

`GET /api/state` returns:
```text
{now, clock "T+1h02m", phase, outreach_at, sweeps {block_id: team name},
 config {demo_mode, nemotron, photon},
 counts {in_zone, contacted, replied, needs_help, assigned, confirmed_safe,
         self_reported_safe, unreachable, flagged_blocks},
 blocks[], pins[{id, lat, lng, score, status, name, in_zone}],
 queue[top 60 {id, rank, name, address, phone (masked …1234), source, language, block_id,
               status, score, reasons[], summary, last_message, last_reply,
               suggested_team {id, name}|null, assigned_team, shelter, sweep, lat, lng}],
 teams[], shelters[], trace[], audit[]}
```

Agent tools (Nemotron or rule fallback): `lookup_household`, `get_hazard`, `update_needs`,
`compute_score`, `find_shelter`, `send_reply`. The spec's `find_or_merge_case`,
`lookup_policy` and `draft_fnol` don't exist yet.

## Things this code has that the spec's Tier A doesn't ask for

Silence map with quiet-block flags and sweeps (spec has nothing like it), agent trace panel
(spec Tier B), census-estimate households with no phone, the utility medical-device list as a
data source, a far-away check-in fraud rule, demo mode with simulated replies, and 9 backend tests.
