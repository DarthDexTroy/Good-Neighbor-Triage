# HANDOFF: Phil, read this first

From Cristobal · 3:30 a.m. · About 8 hours left until submission.

## What changed and why

The State Farm judge said our product sits "in the middle" (helping responders during the storm). State Farm cares most about the two ends: **before** the storm (preventing losses) and **after** it (claims). So the product is now **one conversation across three phases: Before → During → After**, with a business scorecard. The full design is in `before-after-repositioning-spec.md`.

## What changes for you

- **I'm sleeping until about 7:00 a.m.** Until then, **you own the whole repo, frontend included.** The old rule "Phil = backend only" is paused while I'm asleep.
- **Frontend code is in `src/`** at the repo root, not in `frontend/`.
- **Scope is cut** because we lost time. Only build what's on the list below. **Ignore the old SPLIT.md task list** unless the list below names an item.

## Build list (in this order; stop at 9:30 a.m. no matter what)

**1. Sponsor check: timebox to 45 minutes total**
- Get Nemotron running for real in `agent.py`.
- Get Photon sending and receiving for real.
- If either one isn't working after 45 minutes, **drop it and move on.** The demo works with the rules fallback and the phone simulator. We lose that prize, not the whole project.

**2. Slice 1: all three phases at a basic level (MUST WORK)**
1. Phase clock: `POST /api/phase {phase: before|during|after}` jumps the simulated time to T−72h, landfall or T+48h.
2. Dashboard: **Before / During / After tabs** + a banner that shows the phase and simulated time.
3. **Before tab:** fake forecast cone on the map + a panel with policies in the path and total expected loss ($) (formula in spec §4.1).
4. **Before tab:** "Send action texts" button. Replies of `1` (car moved), `2` (shutters) and `3` (meds ready) mark the action confirmed (spec §4.2).
5. **During tab:** the existing dashboard. Don't change it.
6. **After tab:** claims board with 3 columns: Auto-pay, Desk adjuster, Field adjuster (spec §6.2).
7. **Scorecard** in the corner: avoided losses ($), claim cycle time, cost per claim (spec §5 and §7). Label every baseline "assumed."

**3. Slice 2: only these, if Slice 1 is done**
8. Auto-pay rule: ≤ $2,500, pre-storm photos, minor damage, zero fraud flags → paid, and the person gets a text.
9. Contractor fraud flags (spec §6.3) + a contractor list on the After tab.
10. Seeded before/after photo pairs (placeholder images are fine) on claims.

**Not now:** shelters view, escalation ladder, third-party reports, location confirm, mitigation list. Add them only if everything above works before 9:30 a.m.

## The demo needs one family

Seed the **Reyes household** (fictional): Ana (34) and her mother Rosa (71, uses oxygen), a 2019 sedan, a 22-year-old roof, no shutters, Spanish-preferred, policyholders. Make sure the Reyes family:
- gets the Before action text and can reply `1`,
- shows up at the top of the queue During when the Spanish oxygen text comes in,
- has a minor claim of $1,840 After, which lands in **Auto-pay**.

Also seed one contractor, "Gulf Rapid Roofing," on 9 claims, with benefits signed over 6 hours after landfall, so its claims get flagged.

## Rules

- **Commit and push to `main` at least every hour.** When I wake up, I'll pull and start from your latest push.
- Leave a short note in `STATUS.md` at the repo root before I wake up: what works, what's broken, and how to run it.
- **Feature freeze at 9:30 a.m.** After that, only fix bugs.

## Paste this into your Claude Code session

```text
Read HANDOFF-PHIL.md first, then before-after-repositioning-spec.md and CONTRACT.md.
HANDOFF-PHIL.md overrides SPLIT.md and any older task list.
Cristobal is asleep, so for now you may edit both backend/ and src/ (the frontend).
Work through the Build list in order. Commit and push to main after each numbered item.
Don't rename the repo, folders or files. Product name "Good Neighbor Triage" is visible text only.
Start with item 1 (sponsor check), timeboxed to 45 minutes.
```
