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

- **2026-08-02, two reports in one window — and the from-zero ratio was badly wrong.** Window
  opened 03:30Z. Report A: 03:54Z, **59%**, 14,142,892 tokens, three agents running. Report B:
  04:11Z, **80%**, 28,194,877 tokens, taken just after two of the three were cleared. Traffic was
  ~98% cache-read in both scans.

  - **Marginal cost is ≈670k tokens per percent** (Δ14.05M / Δ21pct). Dividing report A's total by
    its own percentage gave **240k/pct** — off by 2.8×, and it over-predicted spend, so it fails
    in the dangerous direction. **Calibrate on the delta between two reports, never on one report
    divided by tokens-since-window-start**; the from-zero form assumes the window opened at zero
    tokens and that every transcript the scan sees is billed to this account's window, and at
    least one of those is false.
  - **The error was in shape, not magnitude.** From report A alone, straight-lining
    "59% in 24 minutes" predicted exhaustion at 04:07Z. At 04:11Z the account was at 80% and still
    serving. An average since window start is not a marginal rate: it embeds a burst that has
    already stopped, and it cannot see agents starting or stopping.
  - **Measured burn: ≈1.2%/min with three agents**, roughly half the straight-lined guess. Still
    fast enough to consume a 5h window in well under an hour, so with several agents on large
    contexts elapsed window time remains useless as a predictor — but predict from the two-report
    delta, and re-read after the agent count changes, because that rate is a property of how many
    agents are running, not of the window.
  - **Cost is dominated by context size, not turn count.** ~150k tokens per request across 185
    requests; a turn that adds nothing to the conversation still re-sends all of it. This is the
    measured case for `/compact` and `/clear` being spend decisions rather than tidiness.

_(append findings here with the date and what was running at the time)_

## Open

- No way found yet for an agent to read remaining credit directly. Percentages therefore arrive
  only when the user reports one; between reports, the estimate is elapsed window time.
- The 670k tokens/pct above is one delta, measured while the agent count was falling. Whether that
  ratio is stable, or itself moves with the traffic mix, needs a third and fourth report.
- Transcript count is not agent count: `/clear` opens a new transcript, so nine files in this
  window came from far fewer concurrent agents. Any per-agent figure derived from file count is
  wrong.
- Unknown whether refusal arrives at a reported 100% or earlier. The next `limit-hit` should be
  logged with the last reported percentage beside it.
