# What we know about the credit window

Refine these in place as observations accumulate. Provisional until an entry cites a run.

## Assumed, user-reported, not yet confirmed by logged observation

- The window is **5 hours**, rolling.
- It starts at the **first request after the previous window ended**. With several agents running,
  whichever sent that first request started the clock for all of them.
- Renewal is therefore predictable from the window start alone, without knowing spend.

## Observed

- **2026-07-31, one interactive session:** the user reported ~97% consumed, and a sleep to
  2026-07-31T23:34Z was taken on that basis. No refusal was ever observed, so this fixes neither
  the ceiling nor the window length — it only records that a reported percentage was the trigger.

_(append findings here with the date and what was running at the time)_

## Open

- No way found yet for an agent to read remaining credit directly. Percentages therefore arrive
  only when the user reports one; between reports, the estimate is elapsed window time.
- No cost-per-turn figure yet. It needs two reports in one window plus the turn count, context
  size, and agent count between them.
- Unknown whether refusal arrives at a reported 100% or earlier. The next `limit-hit` should be
  logged with the last reported percentage beside it.
