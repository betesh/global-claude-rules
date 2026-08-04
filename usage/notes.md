# What we know about the credit window

Add to this as real measurements accumulate — every figure here must come from a measurement, not
a guess (see `rules/measure-before-recording.md`), stating what it was measured under. Skip
anything an implemented hook/rule/script already documents in its own comments; this file is for
knowledge that doesn't live anywhere else.

## Goals

1. Map "% used" (only ever reported by the user) to tokens spent in the same window. Tokens are
   recoverable from `~/.claude/projects/*/*.jsonl` transcripts.
2. Reduce token usage by finding what actually spends the most tokens.

The window is rolling, exactly 5 hours, starting at the first tool call after the previous one
ends. Readings toward goal 1 are in `usage/events.jsonl` (`usage-report` and `renewed` lines).

## Still gathering data on

| open question | current evidence | what's needed |
|---|---|---|
| Given that `per_pct` vary ~40% window to window, how many data point for the current window is enough to model per_pct for the remainder of the window? | see "Within-window convergence" below: no small, fixed count is reliable | readings taken only while every agent on the machine is idle, to see whether that removes the regime-shift noise |
| Where's the `CARRY_AT` knee (below which clearing isn't worth the interruption)? | 4 real TTL crossings, 71,903–231,467 tokens carried — all far above the 50,000 default | a crossing that carries less context, to bracket the knee from below |
| Is `CHECKPOINT_AT`'s 50,000 default right? | 1 correlated `cleared` outcome so far | nudge→clear pairs to accumulate |
| Is `MARGIN_CALLS=5` the right tool-gate headroom? | 1 forced trial: denied at `calls_remaining ≈ 1.0`, ahead of the prompt gate | an unforced, natural ceiling crossing |

## Calibration: tokens-per-percent by window

`pct = intercept + tokens/per_pct`, fit by `calibrate()` in `hooks/usage_common.py`. Four windows
measured so far:

| window | readings | per_pct | intercept | max residual | cache-write share |
|---|---:|---:|---:|---:|---:|
| A (08-03 14:11) | 7 | 821,796 | 4.0 | 9.0pp | 1.9% |
| B (08-03 19:12) | 3 | 941,707 | 14.8 | 0.9pp | 2.4% |
| C (08-04 00:13) | 9 | 1,080,381 | 21.4 | 7.7pp | 2.2% |
| D (08-04 05:14) | 9 | 1,140,912 | 19.7 | 6.6pp | 4.0% |

(D's row moved from 6 readings/752,323/12.5 to 9 readings/1,140,912/19.7 as more of that window's
own readings came in — a 52% swing in `per_pct` from within one window, not between windows. That
motivated the convergence check below.)

### Within-window convergence

Fit on just the first *k* readings of a window and check the error against the readings held out
after it (script: refit incrementally, compare predicted vs. reported pct). Result: **the held-out
error does not shrink monotonically with more points** — more early-window readings sometimes made
the forecast worse, not better:

| window | fit on first 2 | fit on first 4 | fit on second-to-last |
|---|---|---|---|
| A (7 readings) | 15.0pp held-out err | 19.2pp | 25.1pp (6 of 7) — got worse throughout |
| B (3 readings) | 5.3pp (only 1 point to hold out) | — | — |
| C (9 readings) | 46.4pp | 15.5pp | 5.0pp (7 of 9) — converged, but only near the end |
| D (9 readings) | 144.0pp | 30.0pp | 10.3pp (7 of 9) — still 5pp off even at 8 of 9 |

Windows A and D each contain a burst partway through (large jumps in reported pct between adjacent
readings — A: 52→98, D: 29→47→68) where the rate visibly changes; a line fit on the calm part of the
window is a bad predictor of the bursty part. **No small, fixed point count reliably bounds the
error** — 2 points was fine in B and off by 144pp in D; even 7–8 of 9 points (most of the window
already spent) still carried 5–10pp of held-out error in C and D. The thing that breaks the fit
looks like an un-modeled regime shift (matches the earlier finding that local rate tracks token
mix, not calendar time), not sample size.

Untested mitigation, to check against future windows: reporting pct only when every agent on the
machine is idle (no concurrent mid-burst spend at the moment of the reading), to see whether that
removes this noise rather than more points averaging over it.

**`per_pct` swings ~40% across these four windows — not a fixed constant.** Within a window the fit
is sometimes tight (B, D: under 2.5pp) and sometimes not (A, C: 7–9pp); the worst residuals in both
A and C land near bursts of fresh, cache-miss-heavy sessions (many short-lived test sessions in C;
a TTL-crossing cache-expiry in A), suggesting the *local* rate shifts with what kind of tokens are
being spent, not just calendar time. Ruled out as the sole cause: model mix (all four windows are
100% `claude-sonnet-5`) and cache-write share alone (1.9–4.1%, doesn't order the same way `per_pct`
does — C has a lower cache-write share than B but a higher `per_pct`); session count doesn't order
consistently with it either.

**Never drop the intercept** when fitting: forcing the line through the origin pushes pre-window
spend the transcript scan can't see into the slope instead, which is what made an earlier one-shot
ratio disagree with a delta fit by 2x.

## Token categories and the prompt cache

Cache-read is 95–97% of every window's tokens; cache-write 2–4%; output under 1%; input ~0%. Every
turn resends the whole conversation, so a session's total cache-read ≈ `avg context size across its
turns × turn count` (confirmed: a 92-turn session, context 231K→376K, formula gives ≈27.9M vs.
measured 28.5M) — **turn count is the lever, not the size of any one turn's addition.**

The prompt-cache TTL is bracketed between 54 and 141 minutes: a 53.8-min idle gap left cache-read
intact, while every ~140–146-min gap observed (five instances) came back with cache-read reset and
a cache-write ≈ the whole prior conversation. Crossing it turns the next request's cache-write into
a one-time cost ≈ everything carried forward — why cache-write arrives in bursts rather than steadily.

**Rolling into a new 5-hour credit window does not itself expire the cache.** Checked directly: a
session continuously active across the 2026-08-04T10:14:17-06:00 window boundary (last request 4
min before it, next 4 min after — nowhere near the TTL) shows `cache_read` climbing straight through
without a reset (356,306 → 356,797) and a normal small `cache_write` (1,396, in line with ordinary
per-turn growth, not a whole-conversation rewrite). The window itself is real — Anthropic blocks the
account once its quota within a rolling 5 hours is spent, for whatever's left of those 5 hours from
when the block started (hit 100% at 1h in and the block runs the remaining ~4h; hit it at 4h59m and
it's ~1 minute, not necessarily enough on its own to cross the cache TTL either) — but it and the
prompt-cache TTL are simply two unrelated mechanisms: this repo's tooling only estimates where the
window's boundaries fall, since Anthropic exposes no direct token count, and that boundary crossing
has no bearing on the separate, idle-gap-based cache.

`CARRY_AT` in `hooks/usage_common.py` (default 50,000) is still a guess. Four genuine TTL crossings
measured directly from transcripts so far, all well above it:

| idle gap | context carried | outcome |
|---:|---:|---|
| 141.3 min | 231,467 | rewrite paid |
| 146.4 min | 71,903 | rewrite paid |
| 150.8 min | 162,577 | denied, session abandoned rather than retried |
| 178.8 min | 128,855 | denied once, resubmitted 7s later, rewrite paid |

All four are comfortably above 50,000, so the default isn't contradicted, but none is anywhere near
it either.

## The PreToolUse budget gate

One trial (2026-08-03, forced via a temporary `CLAUDE_USAGE_GATE_PCT` override, not a natural
ceiling crossing): `usage_tool_gate.py` denied before `usage_gate.py` would have, at
`calls_remaining ≈ 1.0` — single-digit, matching the design target. The slack traced mostly to
*other concurrent sessions'* spend against the shared window between checks, not this session's own
context growth (own calls move the estimate ~0.07pp each, far too little to explain the jump
observed). `MARGIN_CALLS=5` still caught it with headroom, so the default stands from this one trial.

## Floor composition (interactive, this repo, 2026-08-04)

| component | tokens | how isolated |
|---|---:|---|
| always-loaded core (system prompt + built-in tools) | 19,033 | identical `cache_read` across full-repo/empty-dir/`--safe-mode` interactive readings |
| this repo's `CLAUDE.md` | ~1,225 | repo dir vs. empty dir, both scripted and interactive |
| `rules/` | ~3,000 | already governed by `CLAUDE.md`'s per-token cost note; an order of magnitude below the floor it sits inside |
| hooks (`SessionStart`'s own report) | ~541 | `~/.claude/settings.json` `hooks` key removed for two scripted runs, restored after |
| skills/agent discovery (residual) | ~6,459 | customization stack (10,071) minus rules minus hooks |

**Interactive costs ~6,450–6,470 tokens more than scripted (`-p`) for the same configuration** —
confirmed three ways (full repo, empty dir, `--safe-mode`), consistent to within 36 tokens each
time; cause not identified, only that it's independent of CLAUDE.md/rules/hooks/skills.

Denying the deferred tools (`ToolSearch`-gated ones) via `permissions.deny` only trims ~890 tokens
scripted, not the 16.7K `/context` attributes to them — the mechanism already keeps just a name and
one-line description in context regardless of deny state. Not adjustable this way.
