# What we know about the credit window

Add to this as real measurements accumulate — every figure here must come from a measurement, not
a guess (see `rules/measure-before-recording.md`), and should say what it was measured under.

## The window

Rolling, exactly 5 hours. Starts at the first tool call after the previous window ended.

## Goals

1. Map "% used" (only ever reported by the user) to tokens spent in the same window. Tokens are
   recoverable from `~/.claude/projects/*/*.jsonl` transcripts.
2. Reduce token usage by finding what actually spends the most tokens.

Readings toward goal 1 are in `usage/events.jsonl` (`usage-report` and `renewed` lines).

## % used maps linearly to tokens, with a nonzero intercept

`pct = intercept + tokens / per_pct`, fit by `calibrate()` in `hooks/usage_common.py`, fits well;
a ratio through the origin doesn't (up to 10.8pp off), because it forces pre-window spend the
transcript scan can't see into the slope. **Never drop the intercept.** Best fit so far — one
window, 6 readings, 15.5M–46.9M tokens — is `per_pct ≈ 1,267,529`, `intercept ≈ 17.3`, all readings
within 2.3pp. The reported percentage is integer-only and can lag a burst of spend by a full
reading — one flat repeat isn't grounds to distrust the fit.

## Cache-read of the accumulated conversation is nearly the entire cost

Category share of a window's tokens (one window measured): cache-read 97.8%, cache-write 1.6%,
output 0.6%, uncached input ~0%. Every turn resends the whole conversation, so **output tokens are
noise next to what's being re-read.**

A session's total cache-read ≈ `avg context size across its turns × turn count` (confirmed on a
92-turn session: context grew 231K→376K, formula gives ≈27.9M vs. measured 28.5M). **Turn count is
the lever, not the size of any one turn's addition** — every later turn re-pays for everything
already in context. Per-turn growth is broad-based, not spiky (largest single additions 4K–12K
tokens vs. a ~1,587 average) — confirms why trimming one large tool output doesn't move the number
(also measured independently in `rules/usage-limits-and-context.md`, <0.1% of a window).

## The prompt-cache TTL is between 54 and 141 minutes

Bracketed directly: a 53.8-min gap left cache-read intact; ~140–141-min gaps (three sessions,
independently) always came back with cache-read reset to baseline and a cache-write ≈ the entire
prior context. Rules out a 5-minute TTL; consistent with a 1-hour tier. Bracket only — should
tighten as more gaps get observed.

**Crossing the TTL turns the next cache-write into ≈ the whole carried-forward conversation** — a
one-time cost on top of steady per-turn growth, and why cache-write (1.6% of tokens) arrives in
bursts. One clean instance: the same idle stretch that let a credit window lapse also aged out
three sessions' caches at once — one `renewed` + two `carried-context` events within a minute of
each other were one real-world gap, not three independent signals.

## Carried-in size at real TTL crossings

Two of the three `carried-context` firings recorded so far were genuine TTL crossings — idle gaps
of 141.3 and 146.3 minutes, read directly from the transcripts, matching the bracket above — and
carried 231,467 and 71,903 tokens respectively. The third (idle gap 0.24 minutes) was not a TTL
crossing at all: it fired only because that session's very first request predated the window
boundary, with no idle gap anywhere near it, which is why that trigger now gates on the idle gap
itself rather than on where a session's history sits relative to the window. Both genuine points
sit well above the 50,000-token `CARRY_AT` default, so it isn't contradicted, but two points can't
locate a knee — more real crossings, via `usage/context-cost.py`, are needed before moving it.

CARRY_AT is still a guess. Both reading we have so far are comfortably above the current 50,000
default, so it isn’t contradicted, but two points can’t locate the knee below which clearing
saves less than the interruption costs. As more TTL are observed, we'll be able to refine that number.

CHECKPOINT_AT in hooks/checkpoint_stop.py is a guess. As more data is collected, it needs to be refined
based a measured value of how much context is enough justify the cost of clearing.
