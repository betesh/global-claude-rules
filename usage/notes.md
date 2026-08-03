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
- Deriving the window start from when a `renewed` event was *logged* rather than when renewal
  happened makes the window look short. The log trails the event by however long it took someone to
  notice.

## Converting tokens to percent

An agent cannot read remaining credit; a user reporting a percentage is the only direct reading.
Tokens come from the transcripts, and the two are joined by fitting a line:

```
pct = intercept + tokens / per_pct
```

- Current fit across five readings in one window: **667,881 tokens per percent**, intercept
  **7.0%**, worst residual **±2.0 percentage points**.
- **Individual deltas are noisy; the fit is not.** Consecutive deltas measured 558,019, 560,512,
  **760,437**, then 603,400 tokens per point — a spread of 36%. But the fit through all of them is
  converging: the fourth reading moved the slope 21%, the fifth moved it 1.4%. Predictions track
  the same way, from 7 points out at the fourth reading to 1 point out at the fifth.
- So **trust the fit, not any single delta**, and treat it as good to roughly ±2 points. That is
  enough to gate near a ceiling and not enough to pace fine work by.
- The spread is **unexplained**. It is not the model — every interval was 100% Opus. It is not the
  component mix — every interval was ~99% cache-read. Candidates still open: the reported
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

The question is what makes up that context, and the dominant term is **whatever was already in the
session when the window opened**. A session that has been running for hours carries its entire
history across the boundary and pays for all of it on every request of the new window. Two sessions
crossing one boundary carried 168k and 57k tokens in, and that history was the largest single share
of the window's cache-read — larger than everything added during the window put together.

**The magnitude is not settled.** Every figure it was quoted with came from a scan that counted each
streaming transcript line as a request rather than each `requestId`, which inflated request counts
by roughly 1.8x, and every figure in that table is a product with that count. The ordering survives
— carried-in is still the largest term by a wide margin, and it is still an order of magnitude above
tool output — but treat any specific percentage or token saving as unmeasured until a window whose
boundary the hook dated itself has been run through `usage/context-cost.py`.

Of what is added *during* a window, the split is: tool calls ~10%, tool results ~13%, assistant
replies ~2%, user prompts ~0.2%, against carried-in at ~74%. Those five are shares of what the
attribution can see, which is about 73% of measured cache-read; the rest is per-request overhead the
transcripts do not record. So:

- **Session lifetime is the lever, by a wide margin.** The cost of a long-lived session is not the
  work it does but the history it re-reads, and that history is charged again in full by every new
  window it survives into. Clear at a window boundary, and clear before starting unrelated work.
- **`/clear` is powerful but its benefit is timing-dependent**, which is why clearing everything at
  an arbitrary moment can look like it did nothing: the saving is proportional to how much context
  is dropped *and* how many requests follow. Clearing a 168k-token session that then runs a hundred
  more requests saves millions of tokens; clearing a small session, or clearing then immediately
  rebuilding, saves almost nothing.
- **Trimming large tool outputs is not worth doing.** The largest single tool result observed all
  window was 2,606 tokens; capping every result at 2,000 saves under **0.1%** of a window.

Beware measuring this by "what was added during the window" — blocks added *before* it are invisible
to that method and get silently attributed to fixed overhead. An earlier pass here concluded the
system prefix was 79% of spend for exactly that reason, and it was wrong.

**The rules in this repo** are re-read on every request of every session, so they cost roughly
**0.4 points of a window per 1,000 tokens** at two concurrent sessions, and more with more agents.
Real, and worth trimming, but an order of magnitude below session lifetime.

## Refusals have never been observed

Across every window logged here, **not one request has been recorded as refused**. The reported
percentage saturates at 100 and work continues, so there is no measurement of what a refusal looks
like, when it arrives, or what reset time it reports.

So renewal is not something to wait to be told. It is **the window start plus five hours**, and a
launcher or a gate that waits for a refusal to name the time waits forever. Aim a minute past the
derived boundary, plus a few random seconds, since the derivation can be a clock-skew off and
concurrent agents would otherwise race the first request.

## What we still do not know

- **What the non-cache-read components cost.** At 98% cache-read, every reading has the same mix,
  so the per-component weights cannot be separated. Readings taken under a genuinely different mix
  — heavy fresh generation, little re-reading — would settle it.
- **Whether 560,103 tokens/% is stable** across windows, models, and traffic shapes, or whether it
  is a property of this one. It has held to 0.4% across two deltas within a single window.
- **Transcript count is not agent count.** `/clear` opens a new transcript, so file counts
  overstate concurrency and any per-agent figure derived from them is wrong.
