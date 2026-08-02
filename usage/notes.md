# What we know about the credit window

Refine these in place as observations accumulate. Every figure here came from a measurement, and
carries the conditions it was measured under — a number without them does not transfer.

## The window

- It is **rolling and exactly 5 hours**, and starts at the first request after the previous window
  ended. With several agents running, whichever sent that request started the clock for all of
  them.
- Because the length is fixed, a reported renewal **fixes the window start by subtraction**, and
  does it better than any event in the log. A `renewed` line is written when an agent noticed
  credit was back, which trails the renewal itself by however long that took — reconstructing the
  start from that lag instead made one window look 19 minutes short.
- Independent readings hours apart agree on the same absolute renewal time to within a couple of
  minutes, which is display rounding.
- A reported "resets in Y" is an **upper bound, not a floor**. A window has renewed nine minutes
  after a reading said 100% used with 3h22m to go. So any later evidence of service — a percentage
  under 100, a request that plainly succeeded — cancels a wait, and waiting one out without
  re-checking wastes an open window. That waste is invisible: nobody notices the agents that idled.
- Deriving the window start from when a `renewed` event was *logged* rather than when renewal
  happened makes the window look short. The log trails the event by however long it took someone to
  notice.

## Converting tokens to percent

An agent cannot read remaining credit; a user reporting a percentage is the only direct reading.
Tokens come from the transcripts, and the two are joined by fitting a line:

```
pct = intercept + tokens / per_pct
```

- Current fit across four readings in one window: **677,216 tokens per percent**, intercept
  **7.1%**, worst residual **±2.1 percentage points**.
- **The ratio is not constant, and this is the main open problem.** Consecutive deltas in a single
  window measured 558,019, then 560,512, then **760,437** tokens per point. The first two agreeing
  to 0.4% was luck, not precision: three readings against two parameters leaves one degree of
  freedom, so residuals of ±0.01 meant nothing, and the fourth reading moved the slope 21%.
  Treat any fitted ratio as good to roughly ±2 points, not better.
- The 36% jump is **unexplained**. It is not the model — every interval was 100% Opus. It is not
  the component mix — every interval was ~99% cache-read. Candidates still open: the reported
  percentages are coarse, or some spend is invisible to a transcript scan.
- **The intercept is not noise.** It is spend the scan cannot see: traffic before the window start,
  or transcripts outside the config dir. Forcing the line through the origin pushes that offset
  into the slope, and that error measured **2x** — in the direction that reports a live window as
  exhausted, so it idles agents that could be working.
- Weighting the components by published price ratios fits better than a raw sum (worst residual
  1.5 vs 2.1 points) but does not rescue it.
- Conditions: one window, two concurrent sessions, Opus throughout, traffic ~98% cache-read.

**Rates per minute are not worth tracking.** A percentage-per-minute figure measures how many
agents were running and how fast someone was issuing commands, not any property of the account. The
same underlying spend produces wildly different numbers depending on idle time. Tokens are the
denominator that transfers.

## What actually spends the credit

**Cache-read is 97–98% of all tokens**, because every request re-sends the whole context and the
cached part is billed at the cache-read rate. So `total cache-read ≈ requests × average context`,
which held to within a percent across two concurrent sessions.

The question is what makes up that context. Charging every block to the requests that came after
it — its size times how many later requests re-read it — gives the only decomposition that matters:

| what put it in context | share of cache-read |
|---|---:|
| **fixed prefix, re-read on every request** | **79.1%** |
| tool calls | 9.1% |
| tool results | 8.5% |
| assistant replies | 3.1% |
| user prompts | 0.2% |

**Four fifths of all spend is the prefix**: the system prompt, the tool definitions, and whatever
is injected at session start. It is re-read on every request of every session and nothing that
happens during a conversation reduces it. Measured at ~76k tokens per request across 287 requests.

Three things follow, and two of them contradict the obvious guesses:

- **Trimming large tool outputs is not worth doing.** The largest single tool result observed all
  window was 2,606 tokens. Capping every result at 2,000 would have saved 51,510 tokens — under
  **0.1%** of a window. There is no fat there to cut.
- **`/clear` has a hard ceiling of about 21%.** It drops the conversation but not the prefix, which
  is re-established for the next session and re-read just as often. That is why clearing every
  agent produces a disappointing result: four fifths of the cost was never in the conversation.
- **The prefix is the only lever with real leverage, and most of it is not ours.** The system
  prompt and tool definitions cannot be edited from here. What can be is whatever the session
  start injects — and that portion is paid by every agent simultaneously.

**The rules in this repo are 10,778 tokens**, read in full at every session start. Across 287
requests that is 3.1M tokens, **11% of all cache-read, about 4.6 points of a window**. Adding to
them is not free and is not small: a 400-token rule costs roughly 0.17 points per window at this
traffic, which is more than capping every oversized tool result would save.

## What we still do not know

- **Whether refusal arrives at a reported 100% or earlier.** No request has ever been observed to
  be actually refused — every "limit hit" so far came from a user-reported percentage. Until one
  is, the ceiling is unpinned. Log the last reported percentage beside the next real refusal.
- **What the non-cache-read components cost.** At 98% cache-read, every reading has the same mix,
  so the per-component weights cannot be separated. Readings taken under a genuinely different mix
  — heavy fresh generation, little re-reading — would settle it.
- **Whether 560,103 tokens/% is stable** across windows, models, and traffic shapes, or whether it
  is a property of this one. It has held to 0.4% across two deltas within a single window.
- **Transcript count is not agent count.** `/clear` opens a new transcript, so file counts
  overstate concurrency and any per-agent figure derived from them is wrong.
