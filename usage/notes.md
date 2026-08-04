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
| Is `CHECKPOINT_AT` right? | 4 correlated `cleared` outcomes at the old 50,000 default (nudge_age_min 0.9–4.7 — user cleared within minutes every time), contexts 71,675–113,950 | lowered the default to 35,000 (2026-08-04, a guess — see `checkpoint_stop.py`'s docstring) to bracket the range below 50,000; watching for whether nudges there still get a quick `cleared`, or start going unanswered |
| Is `MARGIN_CALLS=5` the right tool-gate headroom? | 1 forced trial: denied at `calls_remaining ≈ 1.0`, ahead of the prompt gate | an unforced, natural ceiling crossing |

## Cost of not clearing (transcript scan, 2026-08-04)

The nudge→`cleared` pairs above only measure whether a nudge got obeyed, not what continuing would
have cost — that counterfactual doesn't need a nudge to exist: a session that's never cleared just
keeps writing to the same transcript file, so its later turns are directly visible. Scanned every
transcript under `~/.claude/projects/*/*.jsonl` (68 sessions with ≥2 real requests, all 4 projects
on this machine, not filtered to sessions the `CHECKPOINT_AT` hook ever saw — most predate it).

For each session, found the first turn where context crossed 35,000 (and separately, 50,000) and
measured what happened afterward:

- **Stopping right after crossing is rare.** 65/68 sessions that reached 35,000 kept running
  afterward (2 never reached it, 1 ended on the crossing turn). At 50,000: 62/68 continued.
- **The continuation is never small.** Even the smallest continuations past 35,000 still ran 7+
  more turns and 300,000+ more tokens before the session ended. Median: 51 more turns, +101,863
  tokens of context growth, 4.6M tokens spent, 39 minutes of wall clock.
- **Rough excess estimate**: summing `context − 30,258` (this repo's measured floor, used as a
  stand-in for every project scanned) over every turn after the 35,000 crossing, across all 65
  continuing sessions: **882M tokens** over 6,071 turns, median 3.07M tokens/session. This is an
  upper bound, not a clean savings number — it assumes a cleared session's context stays pinned at
  the floor for the rest of those turns, when a real session keeps growing from the lower start too
  — but per-session average context after crossing ranged 40,975–270,812, wide enough that the
  direction isn't in doubt.
- One session (`07a1a4d4…`) showed *negative* growth after crossing 50,000 — a mid-session
  `/compact`, not a session that stopped early; excluded from the "continued" read above.

This fills in the side the nudge/clear timing data couldn't reach: continuing is expensive and
consistently so. It still doesn't locate the `CHECKPOINT_AT` knee by itself, because the other side
of that tradeoff — the cost of interrupting *before* it was needed — has no token-denominated
measurement yet, only the acceptance/timing data already in the table above.

## Calibration: tokens-per-percent by window

`pct = intercept + tokens/per_pct`, fit by `calibrate()` in `hooks/usage_common.py`. Four windows
measured so far:

| window | readings | per_pct | intercept | max residual | cache-write share | true per_pct | vs true |
|---|---:|---:|---:|---:|---:|---:|---:|
| A (08-03 14:11) | 7 | 821,796 | 4.0 | 9.0pp | 1.9% | 708,593 | +16.0% |
| B (08-03 19:12) | 3 | 941,707 | 14.8 | 0.9pp | 2.4% | 619,291 | +52.1% |
| C (08-04 00:13) | 9 | 1,080,381 | 21.4 | 7.7pp | 2.2% | 822,662 | +31.3% |
| D (08-04 05:14) | 9 | 1,140,912 | 19.7 | 6.6pp | 4.0% | n/a | — |

`true per_pct` only exists for windows the user confirmed running to exhaustion (A, B, C — see the
`exhausted?` column below): its final transcript total *is* the 100% point, so `true per_pct =
final total / 100` needs no fit at all. D has no such ground truth — it never reached 100%, so
there's nothing to divide by.

**The fitted `per_pct` overshoots true per_pct in every exhausted window, by a lot (+16–52%).**
This isn't the residual the fit already reports against its own readings (the `max residual`
column) — it's checked against the one number in each window that isn't a fit at all. Per-reading,
the gap widens and narrows unevenly rather than shrinking as the window goes on: window A's readings
run from +6.1pp too high early on to −14.2pp too low mid-window before landing at −1.5pp at the very
last reading; C swings from +8.9pp to +17.3pp and back down to −2.2pp. A systematic overshoot in
`per_pct` of this size means `estimate ~X% used` (what `usage_report.py` prints at every
`SessionStart`) understates real usage in exactly the windows where understating it matters most —
the ones about to run out. Not yet root-caused; the `intercept` term (assumed pre-window spend the
scan can't see) is the leading suspect, since a too-high intercept is exactly what would need a
too-high `per_pct` to keep fitting the same readings.

(D's row moved from 6 readings/752,323/12.5 to 9 readings/1,140,912/19.7 as more of that window's
own readings came in — a 52% swing in `per_pct` from within one window, not between windows. That
motivated the convergence check below.)

### Does cost-weighting fix it?

Refit `calibrate()` on the same readings, but using the cost-weighted token totals from "Total
tokens spent per window" (cache-write ×1.25, cache-read ×0.1, output ×5 — the same guessed
list-price ratios, not a measurement) instead of raw tokens:

| window | raw max residual | weighted max residual | raw per-reading CV | weighted CV | raw vs true | weighted vs true |
|---|---:|---:|---:|---:|---:|---:|
| A | 9.0pp | 6.3pp | 14.2% | 8.5% | +16.0% | +7.5% |
| B | 0.9pp | 0.7pp | 26.4% | 14.1% | +52.1% | +30.0% |
| C | 7.7pp | 5.6pp | 14.6% | 8.5% | +31.3% | +19.1% |
| D | 6.6pp | 4.5pp | 33.3% | 17.4% | n/a | n/a |

(CV = coefficient of variation, `stdev/mean`, of each window's per-reading `tokens/pct` ratios — how
scattered a single window's own readings are around their own average, independent of any fit.)

**Yes to both questions, and consistently across all four windows.** Weighting tokens by their
list-price ratio instead of counting them flat:

- **Makes it more linear.** The fit's own max residual drops in every window (largest: C's 7.7pp →
  5.6pp), and the per-reading CV — how much a window's own readings disagree about tokens/pct
  among themselves, with no fit involved — roughly halves in every window (D: 33.3% → 17.4%, still
  the noisiest window but much less so).
- **Brings it closer to true per_pct.** In all three exhausted windows the overshoot against the
  ground-truth `final total / 100` roughly halves too (B: +52.1% → +30.0%; A and C similarly).

It doesn't close the gap, though — weighted `per_pct` still overshoots true per_pct by 7.5–30%, worst
in B in both versions. So token-type mix explains a real share of the earlier overshoot, but not all
of it; something else (the `intercept` term is still the leading suspect) accounts for the rest. This
is one more point toward the cost-denominated-cap hypothesis in "Total tokens spent per window," using
the same unverified weights — it doesn't confirm the exact ratios, only that weighting in this
direction moves every window the same way.

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

## Total tokens spent per window (2026-08-04)

Every *completed* window logged in `events.jsonl`, summed directly from transcripts (the same
`scan_transcripts` used everywhere else) rather than read off `usage-report` pct — those readings
don't reliably land right at the boundary, so a transcript sum is the more exact number:

| window | start | tokens spent | requests | sessions touched | last token used | exhausted? |
|---|---|---:|---:|---:|---|---|
| A | 08-03 14:11 | 70,859,292 | 425 | 54 | 3h20m in (67% of the window) | yes |
| B | 08-03 19:12 | 61,929,136 | 544 | 46 | 3h42m in (74% of the window) | yes |
| C | 08-04 00:13 | 82,266,244 | 391 | 33 | 2h49m in (56% of the window) | yes |
| D | 08-04 05:14 | 65,889,854 | 408 | 15 | 5h00m in (100% of the window) | **no** |

`exhausted?` is the user's own account of which windows they ran out of credit in, not something
derived from the scan — it's the ground truth the rest of this section is checked against.

**"Last token used" predicts it correctly.** A, B, C all stopped spending well before their 5-hour
mark (56–74%) and then show no further tokens until the *next* window's first request — that gap is
the idle-until-renewal shape a hard cap produces, and all three are confirmed exhausted. D's last
token lands right at the 5h00m boundary with no idle gap before it — continuous work that was still
running when the window happened to roll over — and it's the one confirmed *not* exhausted. Directly
corroborated for A and C by a `usage-report` reading next to the stop (A: 98% two minutes before its
last token; C: 97% seven minutes before). B's last reading (60%, 49 minutes before its last token)
doesn't confirm it as tightly, but the shape and the ground truth agree regardless.

**Raw token totals do not order the same way exhaustion does — the first sign the cap isn't a flat
token count.** D spent *more* raw tokens (65.9M) than B did before B hit its cap (61.9M), yet D
didn't exhaust. So excluding D, the three confirmed-exhausted windows give mean 71.7M, range
61.9M–82.3M (±8.3M, ~12% — one standard deviation) as the token-count estimate of the cap, but D's
65.9M sitting *inside* that range while not exhausting means token count alone can't be what the cap
is measured in.

A cost-weighted total resolves the ordering, though the weights are a guess, not a measurement: using
published list-price ratios for this token type relative to base input (cache-write ×1.25, cache-read
×0.1, output ×5 — not verified against whatever this plan's cap actually charges) —

| window | weighted total | exhausted? |
|---|---:|---|
| C | 12.70M | yes |
| A | 11.40M | yes |
| B | 10.68M | yes |
| D | 10.07M | **no** |

— and now D sits *below* all three exhausted windows instead of inside their range, right under B's
10.68M. That reordering is consistent with a cost-denominated cap somewhere around 10.7M–12.7M
(weighted) that D simply hadn't reached before its 5 hours ran out. What would confirm this over the
guessed weights: more non-exhausted windows to see whether their weighted totals keep landing below
every exhausted one, or the actual pricing ratios this plan's cap uses, if that's ever published.

Conditions: every transcript on the machine, across all 4 projects — this is an account-wide window,
not a per-repo one. 100% `claude-sonnet-5` in every window, so model mix isn't hiding in this number.
Covers back to the start of `events.jsonl`: its first line is window A's own `renewed` record, so
there's no earlier window this log can reconstruct. Window E (started 08-04 10:14) is still open and
excluded from both tables; it stood at 75.4M raw tokens over 487 requests after 1h18m elapsed, last
token at 11:32.

Four points — three exhausted, one not — isn't enough to confirm either the token-count range or the
cost-weighted reordering, but the weighted version is the one worth extending: the next non-exhausted
window is the test of whether it lands below 10.68M too.

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
