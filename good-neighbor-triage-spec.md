# Good Neighbor Triage — Spec

HackUTD 2026 · State Farm challenge: "The Worst Day, at Scale: Intelligent Catastrophe Response"
Team: 2 people · Time budget: 12–20 hours · **All data is fake.**

Working name only. Rename it if you like.

---

## 0. One-sentence pitch

When a hurricane hits, people text one number in any language. An AI agent pulls out what each person needs and ranks who needs help first. It sends rescue teams and shelters to them, and it keeps texting anyone who goes silent until a human checks on them. **No one is overlooked.**

---

## 1. Pitch notes: what judges care about (reminder you asked for)

> Unverified. This is a read on an insurer's priorities, not the official rubric. Check the challenge page and adjust.

**Lead with these:**
1. **Closed loop.** Request → priority → assignment → confirmation to the person. Show the whole loop live.
2. **"No one overlooked."** Show the escalation ladder for people who don't reply, plus vulnerability flags (insulin, wheelchair, infants). This is the challenge's own phrase, so use it.
3. **It works when infrastructure fails.** Plain SMS, short messages, no app to install.
4. **Insurer fit.** State Farm knows where its policyholders live, so it can contact them *before* they call. After they are safe, the same conversation becomes a claim draft (FNOL, first notice of loss). That means faster payouts.
5. **Ethics.** Everyone gets help, policyholder or not. Fraud checks apply **only to claims, never to rescue.**

**What other teams will get wrong (say this indirectly by showing you avoided it):**
- Disaster *prediction* models. The National Weather Service already predicts disasters.
- Plain chatbots with no structured decisions behind them.
- Dashboards that show problems but assign nothing.
- Assuming power and data work.
- **Never say "reduce payouts."** Say "loss mitigation" and "faster, fairer claims."

---

## 2. Scope decisions from the interview

| Decision | Choice |
|---|---|
| Sponsor prizes | **Photon** (SMS/iMessage) + **NVIDIA Nemotron**. Spacetime dropped. |
| Stack | Python (FastAPI) backend + React dashboard |
| Roles | Three views: **CAT team** (State Farm catastrophe team), **Responders**, **Shelters** |
| Demo | Scripted live texts from your own phones + ~200 pre-seeded fake cases |
| Urgency | **The LLM extracts facts; transparent rules compute the score** |
| No reply | Escalating retries → voice call → in-person welfare check flag |
| Scenario | Category 4 Gulf Coast hurricane, Houston area |
| Fraud / insurance | Fraud flags **and** FNOL claim draft |
| Non-policyholders | Helped equally. Policy status matters only for claims |
| Replies to texter | Instant acknowledgment, status updates, safety instructions |
| Language | Any language in, the reply comes back in the same language, the dashboard shows English |
| Missing address | Guess from policy address (marked "unconfirmed") **and** ask once to confirm |
| Reports about others | Create a linked case for the other person; merge if they already exist |
| Shelter view | Capacity/intake, medication schedule, special-needs roster, food/supply counts |
| Work split | **Teammate:** backend, Photon webhook, Nemotron agent. **You:** React dashboard, fake-data generator, fraud rules, pitch |
| Nemotron access | NVIDIA hosted API (OpenAI-compatible endpoint) |
| Photon fallback | In-app phone simulator that posts to the same intake endpoint |
| Map | Leaflet + OpenStreetMap, pins colored by urgency, fake flood-zone polygon |

---

## 3. Two tiers

### Tier A: MUST WORK for the demo

If something below doesn't work, nothing else matters. Build these first, in this order.

1. **Inbound text → case.** A message arrives (Photon or the simulator). The backend creates or updates a case and sends an instant acknowledgment in the sender's language.
2. **Agent extraction.** Nemotron returns structured JSON (see §5.1). The agent detects the language and translates to English for the dashboard.
3. **Rule-based urgency score** with a visible "why" breakdown (§5.2).
4. **Missing location:** use the policy address if the phone number matches a policyholder (marked "unconfirmed"), and send one follow-up asking to confirm.
5. **Linked cases for third-party reports** ("my grandma at 123 Elm isn't answering"), with a merge when the address or name matches an existing case.
6. **Proactive outreach:** "Are you safe? Reply 1 = safe, 2 = need help, 3 = emergency" to every fake policyholder inside the flood polygon.
7. **Escalation ladder** for non-responders, with a **demo clock** you can fast-forward (§5.4).
8. **Three dashboard views** built on one shared queue component:
   - **CAT team:** full queue, map, outreach status (reached / unreached / escalated), and fraud badges.
   - **Responders:** filtered to rescue cases. "Take case" assigns it, sets an estimated arrival time (ETA), and triggers a status text to the person.
   - **Shelters:** capacity and intake list, special-needs roster, medication schedule with overdue alerts, and food/supply counts. Simple tables are fine.
9. **Status update text** when a responder takes a case or a shelter accepts someone.
10. **Safety instructions** text matched to the extracted hazard (flood, injury, power out, trapped).
11. **Map:** urgency-colored pins, flood polygon, click a pin to open the case.
12. **Phone simulator panel** (fallback) that uses the exact same intake endpoint.
13. **Fake-data seed:** ~200 cases, ~500 policyholders, 3 shelters, 4 responder teams.
14. **Fraud flags (minimum):** duplicate claim and out-of-zone address, shown as a badge on claim drafts only.
15. **FNOL draft (minimum):** a button on a "safe" case generates a claim draft from the conversation.

### Tier B: NICE TO HAVE if time allows

- Real voice call at the escalation step through Photon voice (Tier A just *logs* "voice call placed").
- The agent proposes the best shelter itself, using capacity + special needs + distance. In Tier A, the coordinator picks.
- Medication reminders texted to people at shelters.
- More fraud signals: claim velocity per phone, damage claimed outside any hazard area, claim text that doesn't match the conversation (§5.6).
- Human override of the urgency score, with an audit log.
- Low-stock alerts that reassign supplies between shelters.
- Agent trace panel that shows each tool call the agent made (good for the Nemotron prize, see §6).
- Clearly labeled "simulated satellite" flood-extent overlay on the map.
- Metrics bar: median time to first contact, % of zone reached, unreached vulnerable count.

### Cut (do not build)

Disaster prediction, real satellite or computer-vision work, river and drowning tracking, GPS navigation, go-bag checklist, the therapist bot and kids' videos.

---

## 4. Architecture

```
Phone (SMS/iMessage) ──► Photon ──webhook──► FastAPI /intake ◄── Phone simulator (React)
                                                │
                                                ▼
                                     Nemotron agent (tool calls)
                                                │
                     ┌──────────────┬───────────┼────────────┬──────────────┐
                     ▼              ▼           ▼            ▼              ▼
              find_or_merge    score_case   lookup_policy  send_message   draft_fnol
                 _case                                     (Photon)
                                                │
                                                ▼
                                     SQLite (fake data)
                                                │
                                   SSE /events (or 2s polling)
                                                ▼
                         React dashboard: CAT · Responders · Shelters (+ Leaflet map)

Background: escalation worker runs on a "demo clock" (fast-forward button)
```

- **Backend:** FastAPI, SQLite (via SQLModel or plain SQL), and one background task for escalations.
- **Real time:** server-sent events (SSE) at `/events`. These push "case created/updated" to the dashboard. If SSE causes trouble, fall back to polling every 2 seconds. Both are fine for a demo.
- **Agent:** Nemotron through NVIDIA's OpenAI-compatible API. One config value holds the model name. **Check the exact model ID on build.nvidia.com and confirm it supports tool calling.**
- **Photon:** **Unverified. Read the Photon 2.0 docs first.** Confirm (a) how inbound messages reach a webhook (venue Wi-Fi may need a tunnel such as ngrok or cloudflared), (b) the outbound send call, (c) whether voice calls are in 2.0, and (d) rate limits. Put all Photon code behind one `messaging.py` module so the simulator can replace it.

---

## 5. Core logic

### 5.1 Agent extraction output (JSON)

```json
{
  "language": "es",
  "english_text": "Water is coming into the house, my mother uses oxygen",
  "about_self": true,
  "other_person": null,
  "location_text": null,
  "people_count": 2,
  "hazards": ["flooding"],
  "injury": "none | minor | serious | life_threatening",
  "trapped": false,
  "medical_needs": ["oxygen"],
  "mobility_limited": true,
  "children_under_5": 0,
  "power_out": true,
  "is_claim_related": false,
  "status_reply": "need_help"
}
```

The LLM **only extracts facts.** It never decides the priority. That keeps the ranking explainable and testable.

### 5.2 Urgency score (rules, shown on every case)

| Factor | Points |
|---|---|
| Injury life-threatening / serious / minor | 50 / 30 / 10 |
| Trapped | 30 |
| Time-critical medical need (oxygen, insulin, dialysis) | 25 |
| Mobility limited | 15 |
| Child under 5 present | 10 |
| Age 75+ (from policy record) | 10 |
| Inside flood polygon | 10 |
| Power out + medical device | 10 |
| Unreached after escalation step 2 | 20 |
| Per extra person (max +10) | 2 |

Bands: **Critical ≥ 70**, **High 40–69**, **Medium 20–39**, **Low < 20**.
The dashboard shows the breakdown ("Trapped +30, Oxygen +25, …").

> These weights are made-up placeholders that sound reasonable. In the pitch, say real weights would come from emergency-management triage standards.

### 5.3 Case merging

The agent calls `find_or_merge_case` with phone, normalized address, and name. It merges when the phone matches, or when the address matches and the name is similar. Third-party reports create a case for the other person with `reported_by` → the reporter's case. If that person later texts in themselves, the cases merge.

### 5.4 Escalation ladder (demo clock)

| Sim time since outreach | Action |
|---|---|
| T+0 | "Are you safe?" text |
| T+15 min | Retry text |
| T+30 min | Voice call (Tier A: logged only) |
| T+45 min | Case marked **Unreached → welfare check**, +20 points, appears in Responders queue |

Known vulnerable people (oxygen, mobility, age 75+) go through the ladder at **double speed.**
The demo clock lets one button press skip ahead 15 simulated minutes.

### 5.5 Outbound messages (templates, in the sender's language)

- Acknowledgment: "We got your message. Help is being arranged. Reply with any change."
- Location confirm: "Are you at 1420 Bayou Ln? Reply YES or send your location."
- Status: "A rescue team is assigned. Estimated arrival ~40 min."
- Safety (flood): "Move to the highest floor. Do not walk or drive through floodwater."

Have the LLM translate the templates. Store the English source text next to each translation.

### 5.6 Fraud flags (claims only, never block rescue)

| Flag | Rule | Tier |
|---|---|---|
| Duplicate claim | Same policy or address has another open claim draft | A |
| Out of zone | Claimed address is outside every hazard polygon | A |
| Claim velocity | One phone number linked to claims at 3+ addresses | B |
| Unknown number | Claim-like message from a number with no policy or case history | B |
| Story mismatch | Damage in the claim isn't mentioned anywhere in the conversation | B |

Flags show as a badge plus a reason on the CAT view, with the label "for adjuster review." Nothing is denied automatically.

### 5.7 FNOL draft

It is generated from the case conversation and fills: policy number, date and time of loss, peril (flood/wind), location, damage described, injuries, temporary housing needed, and photos requested (as a placeholder). The person gets one text: "We started your claim, #DEMO-1042. An adjuster will contact you."

---

## 6. Prize fit notes

- **Photon:** This is the main intake and outreach channel, not an add-on. Show the inbound and outbound messages live. Use voice for escalation if time allows.
- **Nemotron (must be "beyond a chatbot"):** The agent runs several steps and calls tools: extract → look up policy → merge case → score → choose a reply → send → (later) draft FNOL. **Build the agent trace panel (Tier B) if at all possible.** It is the easiest way to prove it's an agent.

---

## 7. Fake data

- **Area:** Houston neighborhoods near bayous (e.g. Meyerland, Kashmere Gardens, Kingwood). Use fake street addresses with roughly correct coordinates.
- **Policyholders:** ~500. Mixed ages, ~15% with medical or mobility flags, ~10% Spanish-preferred, a few Vietnamese-preferred.
- **Cases:** ~200 seeded at various stages, ~30 unreached, plus 5 crafted fraud examples.
- **Shelters:** 3, for example: one with medical capacity, one pet-friendly, one large general shelter.
- **Responders:** 4 teams (boat rescue ×2, EMS, welfare check).
- No real people, real phone numbers (except your team's own phones), or real policy numbers.

---

## 8. Demo script (~3 minutes)

1. **Set the scene (15s):** Category 4 hurricane, Houston, 2 a.m., power out. Map with 200 live cases.
2. **Live text #1 (45s):** A teammate texts in Spanish: "el agua está entrando, mi mamá usa oxígeno". The case appears, ranks **Critical**, the score breakdown is visible, and the reply comes back in Spanish.
3. **Third-party report (30s):** "My grandpa at 88 Oak isn't answering." A linked case appears, then merges with his existing policyholder record (age 81, wheelchair).
4. **No one overlooked (30s):** Fast-forward the demo clock. Unreached vulnerable people climb the queue and show up as welfare checks in the Responders view.
5. **Close the loop (30s):** A responder takes case #1, and the phone receives "Rescue team assigned, ETA 40 min." The shelter view shows the oxygen dose on the medication schedule.
6. **Insurer payoff (30s):** Mark someone safe → FNOL draft. One crafted duplicate claim shows a fraud badge: "flagged for review, help never blocked."

Keep the phone simulator open in a hidden tab as the fallback.

---

## 9. Build plan (~16 hours)

| Hours | Teammate (backend + agent) | You (dashboard + data + fraud + pitch) |
|---|---|---|
| 0–2 | FastAPI skeleton, SQLite schema, `/intake`, Photon hello-world send/receive | Fake-data generator, React skeleton, Leaflet map with seeded pins |
| 2–5 | Nemotron extraction JSON, rule scorer, acknowledgment + translation | Shared queue component, CAT view, SSE/polling hookup |
| 5–8 | Case merging, location confirmation, third-party linking | Responders view + "take case", phone simulator panel |
| 8–11 | Outreach + escalation worker + demo clock | Shelters view (4 tables), score breakdown UI |
| 11–13 | Status + safety texts, FNOL draft tool | Fraud rules (Tier A), FNOL view |
| 13–14 | **Feature freeze.** Full demo run end to end, fix bugs | Same |
| 14–16 | Tier B items only if the demo runs cleanly twice | Slides, pitch rehearsal, backup video |

**Integration checkpoints:** hour 2 (one text reaches the database), hour 5 (a scored case appears on the dashboard), hour 11 (the full loop works).

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| Photon webhook can't reach your laptop on venue Wi-Fi | Tunnel (ngrok or cloudflared); phone simulator fallback |
| Nemotron returns broken JSON | Use JSON/structured output mode; validate with Pydantic; retry once; else fall back to keyword rules |
| Three views are too much work | One shared queue component; Shelters view stays as plain tables |
| Slow LLM calls during the demo | Send the acknowledgment *before* calling the agent; pre-warm one call |
| Scope creep | Freeze features at hour 13, no exceptions |

---

## 11. Open questions to resolve early

- Photon 2.0: webhook setup, voice support, and sandbox limits. Check in the first hour.
- Which Nemotron model ID supports tool calling on the hosted API.
- Whether the State Farm judges want a slide deck, a live demo, or both, and how long each team gets.
