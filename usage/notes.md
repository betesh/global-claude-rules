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

- **2026-08-02, first tokens-per-percent calibration.** Conditions: window opened 03:30Z, three
  agents running concurrently, two of them long-lived (73 requests logged in 24 minutes). At
  03:54Z the user reported **59% used**; the hook's scan at 03:53Z showed **14,142,892 tokens**
  (in 135, cache-write 150,447, cache-read 13,930,775, out 61,535).

  - **≈240k tokens per percent**, overwhelmingly cache-read — 98.5% of the traffic was re-sending
    existing context, not new input or output. The ratio is fitted to that mix and should not be
    trusted for a session doing mostly fresh generation.
  - **Burn rate ≈2.4%/min under three concurrent agents**, i.e. the whole window consumed in
    ~42 minutes of wall clock. Renewal was still ~4h35m away. So with several agents on large
    contexts, **elapsed window time predicts nothing** — the limit arrives an order of magnitude
    before renewal, and pacing decisions cannot wait for the clock.
  - **Cost is dominated by context size, not by turn count.** 73 requests spending 14M tokens is
    ~194k tokens per request; a turn that adds nothing to context still costs the whole
    conversation again. This is the measured case for `/compact` and `/clear` being spend
    decisions rather than tidiness.

_(append findings here with the date and what was running at the time)_

## Open

- No way found yet for an agent to read remaining credit directly. Percentages therefore arrive
  only when the user reports one; between reports, the estimate is elapsed window time.
- Only one report exists in the 2026-08-02 window, so the burn rate above is an average since the
  window start, not a rate between two readings. A second report would show whether burn is flat
  or accelerating as the running agents' contexts grow.
- Unknown whether refusal arrives at a reported 100% or earlier. The next `limit-hit` should be
  logged with the last reported percentage beside it.
