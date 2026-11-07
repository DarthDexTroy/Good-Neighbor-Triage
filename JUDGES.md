# What State Farm Judges Care About (and what most teams will get wrong)

Challenge: **"The Worst Day, at Scale — Intelligent Catastrophe Response."**
Identify the most urgent needs, coordinate assistance, ensure **no one is overlooked**.

---

## What the judges care about

1. **Real people, real outcomes.** State Farm's mission is about helping people manage
   risk and *recover from the unexpected*. Judges want to see a person get helped, not a
   tech stack. Every feature should end in "and that's how Mrs. Alvarez got out."

2. **"At scale" means thousands, not one.** A single-user chatbot misses the brief. Show a
   map with hundreds of households and show the system *ranking* them.

3. **Explainable prioritization with a human in the loop.** An insurer won't trust a
   black box deciding who gets rescued first. Every urgency score needs a one-line
   "why", and a human must approve each dispatch.

4. **Works when infrastructure fails.** Power out, cell towers overloaded, phones dying.
   SMS and voice reach people that apps and Wi-Fi can't.

5. **Fits what an insurer actually does.** State Farm is not FEMA or 911. Its catastrophe
   teams check on policyholders, coordinate with responders, and get claims paid fast.
   A solution framed around the **cat team** using it (and sharing with responders, with
   consent) is believable.

6. **Business value, framed right.** Faster recovery, losses prevented by early outreach,
   verified claims paid faster, less fraud, policyholders who stay. **Never say "lower
   payouts."**

7. **Trust, privacy and security.** Medical needs, locations and disability status are
   sensitive data. Consent, minimal data, access control and audit logs all count, and
   that's our accounting and cyber advantage.

---

## What most teams will get wrong

| Mistake | Why it loses | How Lifeline avoids it |
|---|---|---|
| "ChatGPT for disasters" chatbot | Not at scale, doesn't coordinate anything | Agent with real tools feeding a triage dashboard |
| Ranking by who asks loudest or first | The most vulnerable often *can't* ask | Vulnerability-weighted score plus a **silence map** |
| Assuming smartphones, data and power | Exactly what fails in a disaster | Photon SMS, iMessage and voice outreach; no app required |
| Faking satellite or computer-vision AI | Judges see through it; it costs credibility | Hazard data is openly simulated; we built the decision layer |
| Feature sprawl (10 half-features) | No clear story in 3 minutes | One loop: find → reach → rank → dispatch → confirm safe → claim |
| Ignoring the insurer's role | Feels like a FEMA pitch, not a State Farm one | Cat-team user, policyholder roster, verified-timeline claims |
| No answer to "who's missing?" | That's the literal last line of the challenge | Cases close only on a *confirmed* safe; silent households escalate |
| Hand-waving privacy | Medical and location data is sensitive | Consent flag, role-based views, audit log, fake data only |

---

## The one-sentence answer to "how do you make sure no one is overlooked?"

> "We start from a list of **everyone in the flood zone**, not just people who call. We reach
> them over text and voice, and we flag any block that's **quieter than it should be**,
> because in a disaster silence means trouble. A case only closes when a human confirms
> that person is safe."
