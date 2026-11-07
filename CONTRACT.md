# CONTRACT: API both lanes build against

From SPLIT.md. **Teammate** owns `backend/app/*` except `shelters.py`; **you** own `frontend/*`
and `backend/app/shelters.py`. Change this file only after agreeing with each other.

## New / changed endpoints and fields

```text
POST /api/clock/advance            {minutes}            → {now}                [teammate]
POST /api/cases/{id}/assign        {team_id?}           → {team, eta_min}      [teammate, adds eta_min]
case.status                        + "welfare_check"                           [teammate]
case.reported_by                   household_id | null                         [teammate]
case.location_confirmed            bool                                        [teammate]
case.escalation_step               0..3                                        [teammate]
claim.claim_number, claim.fnol     see below                                   [teammate]
GET  /api/shelters/{id}            → {intake, roster, meds, supplies}          [you]
POST /api/shelters/{id}/accept     {case_id} → {ok}                            [you]
POST /api/shelters/{id}/meds/{med_id}/given → {ok}                             [you]
```

`claim.fnol` = `{date_of_loss, peril, damage, injuries, temp_housing, photos: []}`,
`claim.claim_number` = `"DEMO-####"`. The Claims tab shows them once they exist.

## Shelters API in detail (implemented in `backend/app/shelters.py`)

```text
GET /api/shelters/{id} → {
  shelter:  {id, name, capacity, occupancy, wheelchair, backup_power, infant_supplies, pets, lat, lng},
  now:      sim minutes,
  intake:   [{case_id|null, name, party_size, arrived_t, needs: [str]}],
  roster:   [{name, wheelchair, infant, oxygen, pets}]      # only people with a special need
  meds:     [{id, name, drug, due_t, given, given_t|null}], # overdue = !given && due_t < now
  supplies: [{item, count, low_at}],                        # low = count < low_at
  pending:  [{case_id, name, status, needs: [str]}]         # ADDITIVE: cases the agent routed here
                                                            # (case.shelter_id == id) not yet accepted
}
POST /api/shelters/{id}/accept {case_id} → {ok: true}
  409 if already accepted or shelter full; 404 if unknown case/shelter.
  Effects: intake + roster + meds updated, shelter.occupancy += party_size, case.shelter_id = id,
           texts the person via messenger.deliver(), writes an audit entry.
POST /api/shelters/{id}/meds/{med_id}/given → {ok: true}
```

Shelter detail data lives in the `meta` table under `shelter:<id>` and is generated on first
read, so a scenario restart resets it.

## Wiring needed from the teammate (one line)

```python
# backend/app/main.py, after `app = FastAPI(...)`
from . import shelters
app.include_router(shelters.router)
```

## Functions from the teammate's code that `shelters.py` calls (not edits)

`messenger.deliver(household, text)`, `services.audit(actor, action, case_id)`, `clock.now()`,
`scoring.effective_needs(household, case)`, `db.get / put / all_docs`.
If any of these get renamed, tell the other person.
