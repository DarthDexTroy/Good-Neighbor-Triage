# Good Neighbor Triage — Before / During / After Spec

HackUTD 2026 · State Farm challenge · Written 2026-11-07 after State Farm judge feedback
Time left: 12–18 hours · **All data is fake.** This spec **adds to** `good-neighbor-triage-spec.md` and `SPLIT.md`. It does not replace them.

---

## 1. Why we're changing direction

**Feedback from the State Farm judge:** our product sits "in the middle," helping first responders during the storm. State Farm's business lives at the two ends:

- **Before the catastrophe:** prevent losses.
- **After the catastrophe:** handle claims and recover.

**Our answer:** keep everything we built, and turn it into one journey for the policyholder. The same text conversation starts **before** landfall, continues **during** the storm, and ends **after** with the claim paid. The "during" features we already have become the bridge between the two business ends.

| Phase | Business goal | Main feature |
|---|---|---|
| **Before** (T−72h → landfall) | Fewer losses | Exposure dashboard, action texts, pre-storm photos |
| **During** (landfall → T+48h) | Keep people safe (existing Lifeline) | Triage, silence map, escalation |
| **After** (T+48h → T+30d) | Faster, cheaper, fairer claims | Auto FNOL, 3-lane claim routing with auto-pay, contractor fraud, mitigation targets |

**One-sentence pitch:**
> "Good Neighbor Triage turns the worst day into one conversation: we warn you before, find you during, and pay you after, and the scorecard shows what that saves."

---

## 2. Decisions from the interview

| Decision | Choice |
|---|---|
| Structure | Before → During → After, one policyholder journey |
| Headline metric | **Combined scorecard:** avoided losses ($), claim cycle time, cost per claim |
| Main user of new screens | **CAT manager** (State Farm catastrophe manager) watching the whole event |
| Before features | Exposure dashboard, pre-landfall action texts, pre-storm photo inventory |
| Avoided-losses math | Per-action table of fake, clearly labeled assumptions (§5) |
| Photo AI | **Faked.** Seeded photo pairs with stored damage labels. A real vision model is future work |
| After features | Auto FNOL + photo intake, 3-lane claim routing **with auto-pay**, all four contractor fraud rules |
| Auto-pay rule | Estimate ≤ $2,500 **and** pre-storm photos exist **and** damage = minor **and** zero fraud flags |
| Mitigation | Post-event target list at T+30 days |
| Navigation | Before / During / After **tabs** + a **phase banner** that shows simulated time |
| Cuts | **None.** Everything in SPLIT.md stays |
| Split | **By layer, as now:** Phil = all new backend, Cristobal = all new frontend + scorecard UI + pitch |
| Build priority | **Thin slice of all three phases first,** then deepen |
| Demo | **The story of one family** through all three phases, with portfolio numbers updating in the corner |

---

## 3. Build order (this overrides SPLIT.md priorities)

Nothing was cut, so **the order is how we manage risk.** Finish each slice before you start the next.

### Slice 1: thin end-to-end journey (MUST WORK)
Goal: the judge sees all three phases working, even if each one is basic.

1. **Phase clock:** simulated time runs from T−72h to T+30d. `POST /api/phase {phase}` jumps to the start of a phase.
2. **Tabs + phase banner** on the dashboard.
3. **Before:** exposure endpoint + map layer, with the total expected loss in $ in the path.
4. **Before:** send action texts + count replies that confirm an action.
5. **During:** the existing Lifeline dashboard (CAT view), unchanged.
6. **After:** claims queue split into 3 lanes from seeded claims (no auto-pay logic yet; use stored lanes).
7. **Scorecard panel:** 3 numbers (avoided $, cycle time, cost per claim), computed from data.

### Slice 2: make the business case real
8. Pre-storm photo request + seeded photo pairs on each claim.
9. Real lane rules + auto-pay (§6.2).
10. Contractor fraud rules (§6.3) + the warning text to damaged areas.
11. Mitigation target list (§6.4).

### Slice 3: finish SPLIT.md "during" items
12. Everything still open in SPLIT.md, in its own priority order.

> **Honest risk:** with 12–18 hours and no cuts, Slice 3 will probably be only partly done. That's acceptable, because Slices 1–2 are what the judge asked for. Freeze features once the full demo runs twice in a row.

---

## 4. Before phase

### 4.1 Exposure dashboard (CAT manager)
- A **fake forecast cone** polygon appears at T−72h and narrows at T−48h and T−24h.
- Every policyholder home and car inside the cone counts as **exposed.**
- Panel: policies in the path, total insured value, **expected loss ($)**, and vulnerable households (oxygen, mobility, 75+).
- Map layer: homes shaded by expected loss.

**Expected loss per household** (fake model, show the formula on hover):
`expected_loss = home_value × P(damage at address) × damage_share + Σ car_value × P(flood at address)`
- `P(damage)` and `P(flood)` come from the household's block (existing `flood_depth_ft` → forecast depth).
- `damage_share`: 0.05 minor / 0.25 major / 0.6 total, chosen from forecast depth.

### 4.2 Pre-landfall action texts
- At T−48h, a personalized text with 2–3 actions chosen from the household's data:
  - Has a car in a block that will flood → "Move your car to higher ground. Reply 1 when done."
  - Has no shutters → "Board or shutter windows. Reply 2 when done."
  - Oxygen, dialysis or insulin → "Refill medication and charge your devices. If you use oxygen, plan to evacuate. Reply 3 when ready."
  - Everyone → "Text us 4–6 photos of your home and car today. It makes any claim faster." (feeds §4.3)
- Replies of 1/2/3 mark that action **confirmed** with a timestamp.
- **The demo shows the reply happening live on the phone.**

### 4.3 Pre-storm photo inventory
- Photos are stored per household with `phase: "pre"`.
- **In the demo,** seeded households already have photo sets. The demo family's photos are pre-seeded too, and their phone sends 1 live photo if Photon supports MMS (picture messages). **Unverified:** check Photon 2.0 MMS support. If it doesn't work, use the seeded set.
- Photo images: simple placeholder images (house/car illustrations with a label). No real people's homes.

---

## 5. Avoided-losses table (fake assumptions, shown on screen)

The scorecard must show a **"How we calculate this"** link that opens this table. Judges trust numbers they can see the math for.

| Confirmed action | Avoided loss counted | Assumption (label it) |
|---|---|---|
| Car moved to higher ground | `car_value × P(flood at address)` | Average flooded car is a total loss |
| Windows shuttered/boarded | `$8,000 × P(wind damage)` | Average interior water/glass damage avoided |
| Pre-storm photos sent | `$350` handling cost saved per later claim | ~3 fewer adjuster hours × ~$115/h (made up) |
| Medication/evacuation ready | **No $ value.** Counted as "high-risk people prepared" | Never put a dollar value on people |

Show avoided $ **only for confirmed actions.** Unconfirmed actions count $0.

---

## 6. After phase

### 6.1 Auto FNOL + photo intake
- When a household moves to `confirmed_safe` or `self_reported_safe` and has a policy, the backend creates a claim draft (Lifeline already does this) and fills the FNOL (first notice of loss) fields: `claim_number`, `date_of_loss`, `peril`, `damage`, `injuries`, `temp_housing`.
- Text to the person: "We started your claim #DEMO-1042. Text photos of the damage."
- Post-storm photos are stored with `phase: "post"`. **The comparison is faked:** each seeded claim has a stored `damage_label` (minor/major/total) and `estimate`. The UI shows the before and after photos side by side with the label: "Simulated damage assessment."

### 6.2 Three-lane claim routing
| Lane | Rule | Handled by |
|---|---|---|
| **Auto-pay** | estimate ≤ $2,500 **and** pre photos exist **and** damage = minor **and** 0 fraud flags | No human. Paid in hours |
| **Desk adjuster** | Everything that isn't auto-pay or field | Remote adjuster with photos |
| **Field adjuster** | damage = total, **or** estimate > $25,000, **or** any fraud flag | In-person inspection |

- Panel shows **adjuster capacity per lane** (fake: e.g. 12 desk, 6 field adjusters) and the backlog in days.
- An auto-paid claim sends the person a text: "Your claim is approved. $1,840 is on the way."
- **Fraud flags always move a claim out of auto-pay.** They never deny it.

### 6.3 Contractor fraud (Cristobal's specialty: write the rules, Phil codes them)
| Rule | Flag when | Why it matters |
|---|---|---|
| **Shared contractor** | Same contractor name or phone on ≥ 5 claims across addresses > 20 miles apart, or listed before the damage was reported | Storm chasers work many claims at once |
| **Inflated estimate** | Contractor estimate > 1.8× the median estimate for the same damage label in the same area | Padding the job |
| **Fast assignment of benefits (AOB)** | AOB signed < 24h after landfall | Classic door-knocker pattern: the homeowner signs over their claim rights to a contractor |
| **Unlicensed** | Contractor not in the (fake) license list | Fake contractors |

- **Proactive warning text** to every policyholder in damaged blocks at T+48h: "Storm repair scams are common. Verify licenses, and never sign over your insurance benefits at the door. Questions? Reply HELP."
- The CAT view shows a **contractor list** sorted by number of flags, with the claims each one touches.

### 6.4 Mitigation target list (T+30 days)
- A list of homes where a **roof or shutter upgrade would have prevented most of the damage** (rule: damage = wind-related, and the home has an old roof (> 15 years) or no shutters).
- Each row: projected next-season expected loss **with** vs **without** the upgrade, and the offered discount (fake, e.g. "Up to 20% wind premium credit").
- Summary line: "Upgrading these 64 homes cuts next season's expected loss by $X."
- **Note:** real roof and shutter discount programs exist in some states (for example, fortified-roof credits), but we didn't check State Farm's actual offers. Label the discount "illustrative."

---

## 7. Scorecard (always visible in the corner)

| Metric | How it's computed | Shown as |
|---|---|---|
| **Avoided losses** | Sum of §5 for confirmed actions | "$1.2M avoided" + "How we calculate this" |
| **Claim cycle time** | Median days from FNOL to payment for paid claims, vs an **assumed** industry baseline (e.g. 30 days, labeled "assumed") | "4.2 days vs ~30 baseline" |
| **Cost per claim** | (adjuster hours × rate) / claims, with auto-pay ≈ $0 handling | "$410 vs ~$1,100 baseline" |
| Also: reached % | Policyholders who replied at least once | Small text |
| Also: fraud $ held for review | Sum of estimates on flagged claims | Small text |

**All baselines are assumptions.** Write "assumed baseline" next to each one. If a judge asks, say the real numbers would come from State Farm's own claims data.

---

## 8. Data model additions (Phil adds these; Cristobal reads them)

```text
household  + home {value, roof_age, shutters: bool, construction}
           + vehicles [{value, year}]
           + expected_loss
           + actions [{type: car|shutters|meds|photos, sent_t, confirmed_t|null}]
           + photos [{phase: pre|post, url, label}]
claim      + claim_number, fnol {...}, estimate, damage_label: minor|major|total
           + lane: autopay|desk|field, contractor_id|null, aob_signed_t|null
           + paid_t|null, paid_amount|null, flags[]
contractor {id, name, phone, licensed: bool}
forecast   {t, cone: polygon, forecast_depth_by_block}
state      + phase: before|during|after, sim time may be negative (T−72h = −4320 min)
```

## 9. New endpoints (add to CONTRACT.md)

```text
POST /api/phase                  {phase: before|during|after} → {now, phase}     [Phil]
GET  /api/exposure               → {cone, totals {policies, insured_value, expected_loss, vulnerable}, homes[]}  [Phil]
POST /api/before/send_actions    → {sent}                                         [Phil]
GET  /api/before/actions         → {by_type {car, shutters, meds, photos: {sent, confirmed}}}  [Phil]
GET  /api/recovery/claims        → {lanes {autopay[], desk[], field[]}, capacity {desk, field, backlog_days}}  [Phil]
POST /api/claims/{id}/autopay    → {paid_amount}                                  [Phil]
GET  /api/contractors            → [{id, name, flags[], claims[]}]                [Phil]
POST /api/recovery/warn_scams    → {sent}                                         [Phil]
GET  /api/mitigation/targets     → {homes[], total_reduction}                     [Phil]
GET  /api/scorecard              → {avoided, cycle_time, cost_per_claim, reached_pct, fraud_held, assumptions{}}  [Phil]
```

## 10. Work split (by layer, as decided)

| Phil (backend) | Cristobal (frontend + pitch) |
|---|---|
| Phase clock + all §9 endpoints | Before / During / After tabs + phase banner |
| Exposure math, avoided-loss math, scorecard math | Exposure view (cone, shaded homes, totals) |
| Action texts + 1/2/3 parsing, photo intake, scam warning text | Action-confirm counters, photo side-by-side viewer |
| Lane rules, auto-pay, contractor rules | Three-lane claims board, contractor list, mitigation list |
| Seed data: homes, cars, photos, contractors, claims | Scorecard panel + "How we calculate this" modal |
| Remaining SPLIT.md backend items | `shelters.py` + remaining SPLIT.md frontend items, pitch |

**Workload warning:** Phil now has much more backend work than before. Two ways to lower the risk:
- **Cristobal writes the contractor fraud rules and the avoided-loss table as plain Python functions** in a new file Cristobal owns, `backend/app/business_rules.py` (pure functions, no database access). Phil's endpoints call them. This uses your fraud expertise and moves work off Phil. **Only do this if Phil agrees.**
- Until Phil's endpoints are ready, build the new tabs against **mock JSON** that matches §9.

---

## 11. Demo: the story of one family (~3 min)

**The Reyes family** (fictional): Ana (34) and her mother Rosa (71), who uses oxygen. They have a 2019 sedan, a 22-year-old roof and no shutters. Spanish-preferred. Policyholders.

| Time | Phase | On screen | Say |
|---|---|---|---|
| 0:00 | Before, T−72h | Cone appears. Exposure: "18,400 policies, $412M expected loss" (fake) | "Three days out, State Farm already knows who's in the path." |
| 0:20 | Before, T−48h | Click **Send action texts**. Ana's phone gets a Spanish text: move car, refill oxygen, send photos | "Every household gets its own plan, in its own language." |
| 0:40 | Before | Ana replies **1** (car moved), sends a photo. Avoided $ ticks up | "That one reply just avoided about a $20,000 total-loss car claim." |
| 1:00 | During, landfall | Switch tab. Ana texts "el agua está entrando, mi mamá usa oxígeno" → top of queue → team assigned | "During the storm, the same conversation becomes a rescue request, ranked by need." |
| 1:30 | During | Silence map: one block lit up → sweep | "And the people who go silent get found." |
| 1:45 | After, T+48h | Switch tab. Ana's claim auto-created; before/after photos; damage = minor, $1,840 → **auto-pay lane** → phone: "approved" | "Claim paid in hours, not weeks, because we had her photos from before the storm." |
| 2:10 | After | Contractor list: "Gulf Rapid Roofing" on 9 claims, AOB signed 6h after landfall → field lane | "Storm chasers hit right after. We catch the pattern, and we warned customers before they knocked." |
| 2:30 | After, T+30d | Mitigation list: Rosa's 22-year-old roof → upgrade offer | "Then we use this storm to make the next one cheaper." |
| 2:45 | All | Scorecard: avoided $, cycle time, cost per claim | "Before, during, after: one conversation, measured in dollars and days." |

**Fallbacks:** the phone simulator replaces Photon. If MMS fails, the seeded photo replaces the live photo. A pre-recorded video of the whole demo is the last resort.

---

## 12. Open questions

- Does Photon 2.0 support MMS (picture messages)? Check this first, or plan on seeded photos.
- Will Phil agree to `business_rules.py` being Cristobal's file?
- Which baselines will we show (cycle time, cost per claim)? Keep them round and labeled "assumed."
- Whether the existing `clock.py` can go negative (before landfall) without breaking the silence-map math. Phil should check.
