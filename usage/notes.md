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

## Goal 1: % used vs. tokens spent — linear, but not through the origin

Measured over one window (opened 2026-08-03T14:11, 6 `usage-report` readings between 14:24 and
15:58, spanning 15.5M–46.9M cumulative tokens): fitting `pct = intercept + tokens / per_pct` by
least squares gives `per_pct ≈ 1,267,529` and `intercept ≈ 17.3`, and every reading lands within
2.3 points of that line — genuinely linear. Forcing the same points through the origin
(`tokens / last_reading`) fits far worse, up to 10.8 points off, because it ignores spend the
transcript scan can't see (anything before the window's first logged tool call, or outside the
config dir). **The intercept is load-bearing — don't drop it when calibrating.** This is the same
form `calibrate()` in `hooks/usage_common.py` already fits; this measurement confirms the existing
method rather than changing it.

One pair of adjacent readings came back identical (52, then 52 again 33 minutes and 2.9M tokens
later) — still inside the noise band above, but a reminder that the reported percentage is integer
and can lag a burst of spend by a full reading.

## Goal 2: what spends the most tokens

Same window, measured directly from transcripts: 5 sessions, 249 requests, ~51.5M tokens.

| category | tokens | share |
|---|---|---|
| cache-read | 50,367,729 | 97.8% |
| cache-write | 844,761 | 1.6% |
| output | 311,650 | 0.6% |
| input (uncached) | 498 | ~0% |

**Cache-read — re-sending the accumulated conversation on every turn — is essentially the whole
cost. Output tokens (what the model actually generates) are noise by comparison.**

A session's total cache-read is close to `(average context size across its turns) × (number of
turns)`: on one 92-turn session that carried in 231K tokens of context and ended at 376K, that
formula gives ≈27.9M against a measured 28.5M. **Turn count in a long-lived session is the lever,
not the size of what any single turn adds** — because every later turn re-pays for everything
already in context, not just its own addition. The three sessions active this window ranked
exactly by turn count × average context, not by any single large exchange: a 92-turn session
(28.5M, 55% of the window) and a 112-turn session (13.5M, 26%) accounted for over 80% of all
tokens between them.

Per-turn context growth on that same 92-turn session was broad-based, not spiky: the largest
single-turn additions were 4K–12K tokens (a file read, a tool result) against an average of
~1,587/turn — no one addition explained a disproportionate share. This is consistent with the
existing measurement in `rules/usage-limits-and-context.md` that trimming one large tool output
isn't worth doing — and explains *why*: a single large output only costs what it costs once, while
turn count is what compounds.

Cache-write is small in total (1.6%) but arrives in bursts tied to the cache TTL, not to turn
activity. Three long-lived sessions (two other projects, one this repo) had each sat idle ~140
minutes; all three resumed within about a minute of each other and each paid a full cache rebuild
(121K, 213K, and 53K tokens — 387K combined, 46% of the window's entire cache-write total, in three
requests). That simultaneous resumption is what this window's boundary hook logged as one `renewed`
plus two `carried-context` events, all within a minute of each other at the very start of the
window — the window-open event and the carried-context flags were the same real-world event seen
from three sessions, not independent signals. **An idle gap past the cache TTL turns the next
turn's cache-write into roughly the size of the entire carried-forward conversation**, a one-time
cost on top of the steady per-turn growth above.
