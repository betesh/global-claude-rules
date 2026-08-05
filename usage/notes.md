# What we know about the credit window

Add to this as real measurements accumulate — every figure here must come from a measurement, not
a guess (see `rules/measure-before-recording.md`), stating what it was measured under. Skip
anything an implemented hook/rule/script already documents in its own comments; this file is for
knowledge that doesn't live anywhere else. State current knowledge, not the process of arriving at
it: a superseded number, a fixed bug, or a corrected report belongs in git history and commit
messages, not here.

## Goals

1. Map "% used" (only ever reported by the user) to tokens spent in the same window. Tokens are
   recoverable from `~/.claude/projects/*/*.jsonl` transcripts.
2. Reduce token usage by finding what actually spends the most tokens.

The window is rolling, exactly 5 hours, starting at the first tool call after the previous one
ends. Readings toward goal 1 are in `usage/events.jsonl` (`usage-report` and `renewed` lines).

## Still gathering data on

| open question | current evidence | what's needed |
|---|---|---|
| Given that `per_pct` vary ~73% window to window, how many data points for the current window is enough to model per_pct for the remainder of the window? | see "How reliably the fit predicts held-out readings" below: no small, fixed count is reliable | readings taken only while every agent on the machine is idle, to see whether that removes the regime-shift noise |
| Why does even the cost-weighted fit still overshoot true per_pct (by 4.6–28%)? | curve-shaped per-reading ratios (rising through a window's middle, falling near the end) fit poorly by any straight line; missing subagent transcripts, non-CLI usage, a timestamp-parsing bug, and a burst of concurrent cold-starts at window-open are ruled out as causes; a `/compact` call's own invisible token cost is a live, unmeasured candidate | whether pct is genuinely non-linear in tokens over a window, a piecewise/regime-shift model, or spend from `/compact` calls that no local record can measure |
| Where's the `CARRY_AT` knee (below which clearing isn't worth the interruption)? | 4 real TTL crossings, 71,903–231,467 tokens carried — all far above the 50,000 default | a crossing that carries less context, to bracket the knee from below |
| Is `CHECKPOINT_AT` right? | 4 correlated `cleared` outcomes at the old 50,000 default (nudge_age_min 0.9–4.7 — user cleared within minutes every time), contexts 71,675–113,950 | lowered the default to 35,000 (2026-08-04, a guess — see `checkpoint_stop.py`'s docstring) to bracket the range below 50,000; watching for whether nudges there still get a quick `cleared`, or start going unanswered |
| Is `MARGIN_CALLS=5` the right tool-gate headroom? | 1 forced trial: denied at `calls_remaining ≈ 1.0`, ahead of the prompt gate | an unforced, natural ceiling crossing |
| What does the cap actually measure, now that a cost-weighted total still doesn't cleanly separate exhausted from non-exhausted windows ("Total tokens spent per window")? | 6 windows: 4 exhausted (61.9–104.1M raw / 10.68–14.23M weighted), 2 not (D: 65.9M / 10.07M; F: 71.6M / 10.87M) — D sits below every exhausted window on the weighted measure, but F overlaps it (above B, below A) | more exhausted/non-exhausted pairs to test whether it's cadence- or rate-shaped rather than cumulative-spend-shaped, or the actual mechanism if ever published |

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

`pct = intercept + weighted_tokens/per_pct`, fit by `calibrate()` in `hooks/usage_common.py` on
tokens weighted by `TOKEN_WEIGHTS` (cache-write ×1.25, cache-read ×0.1, output ×5 — a guessed
list-price ratio, not a measurement). Token totals include every request in the window: both a
session's own transcript and any subagent transcripts it launched (`scan_transcripts` globs
`projects/*/*.jsonl` and `projects/*/*/subagents/agent-*.jsonl`).

The table below shows the **raw** (unweighted) whole-window fit for comparison against the
cost-weighted one in the next section:

| window | readings | raw per_pct | intercept | max residual | cache-write share | true per_pct | vs true |
|---|---:|---:|---:|---:|---:|---:|---:|
| A (08-03 14:11) | 7 | 821,796 | 4.0 | 9.0pp | 1.9% | 724,404 | +13.4% |
| B (08-03 19:12) | 3 | 941,707 | 14.8 | 0.9pp | 2.4% | 624,564 | +50.8% |
| C (08-04 00:13) | 9 | 1,080,381 | 21.4 | 7.7pp | 2.2% | 822,662 | +31.3% |
| D (08-04 05:14) | 9 | 1,140,912 | 19.7 | 6.6pp | 4.0% | n/a | — |
| E (08-04 10:14) | 7 | 1,148,961 | 4.8 | 3.8pp | 1.1% | 1,041,380 | +10.3% |
| F (08-04 15:16) | 3 | 1,421,011 | 5.5 | 1.5pp | 2.7% | n/a | — |

`true per_pct` only exists for windows the user confirmed running to exhaustion (A, B, C, E — see
the `exhausted?` column in "Total tokens spent per window"): its final transcript total *is* the
100% point, so `true per_pct = final total / 100` needs no fit at all. D and F have no such ground
truth — neither reached 100%, so there's nothing to divide by.

**The raw fit overshoots true per_pct in every exhausted window, by a lot (+10–51%).** This isn't
the residual the fit already reports against its own readings (the `max residual` column) — it's
checked against the one number in each window that isn't a fit at all. Per-reading, the gap widens
and narrows unevenly rather than shrinking as the window goes on: window A's readings run from
+6.1pp too high early on to −14.2pp too low mid-window before landing at −1.5pp at the very last
reading; C swings from +8.9pp to +17.3pp and back down to −2.2pp. A systematic overshoot of this
size means `estimate ~X% used` (what `usage_report.py` prints at every `SessionStart`) understates
real usage in exactly the windows where understating it matters most — the ones about to run out.

Ruled out as causes:

- **Usage against this account outside the CLI** (claude.ai web, mobile, Desktop, direct API key)
  would be invisible to any local transcript scan and would look like a persistent additive
  intercept. Asked the user directly: CLI only, nothing else touches this account. Recheck by
  asking again.
- **A timestamp-extraction bug in `scan_transcripts`'s fast path.** It locates a line's timestamp
  with `line.find('"timestamp":"')` rather than a full JSON parse, on the assumption that's always
  the first such substring in the line — false if a nested field (tool output, embedded content)
  contains that literal text earlier. Checked by comparing the fast-path extraction against a full
  parse's `timestamp` field over every usage-bearing line on the machine: 12,713 lines, 0
  mismatches. Recheck the same way if `scan_transcripts` or transcript content shape changes.
- **A burst of concurrent, cold-start sessions right when a window opens** — several agents
  (plausibly ones blocked by the previous window's exhaustion) all firing large, cache-miss-heavy
  requests within the same minute or two once credit renews, which would look like a fixed
  head-start if it fell reliably at every window's open. Checked by measuring session count, raw
  tokens, and the largest single cache-write in the first 10 minutes of windows A–F against each
  window's fitted intercept: no relationship. Window A has the biggest burst measured by every
  metric (3 sessions cold-starting concurrently, 9.9M raw tokens in 10 minutes, one request
  writing 212,567 tokens of fresh cache) but the *smallest* intercept (4.0) of the six; window B
  has almost no burst at all (458K raw tokens over the same 10 minutes, no request over 22,867
  tokens of fresh cache) but the second-largest intercept (14.8). Window E is a second
  counter-example: the largest raw-token total of the six in its first 10 minutes (9.6M, from 5
  concurrent sessions), but all warm cache-reads (no cache-write over 17,476) and one of the
  smallest intercepts (4.8).

Not ruled out — unmeasured, because nothing on this machine can measure it:

- **A `/compact` invocation, successful or failed, spends real tokens that never appear in any
  `usage` field anywhere.** A successful compact is replaced by the isCompactSummary transcript
  line; a failed one leaves only a system/local_command error. Neither carries a token count.
  Found directly: a background session's `/compact` at 2026-08-05 09:12:59 spent 4 minutes
  ingesting ~434K tokens of history before failing with a 529 (server overloaded) — a near-instant
  rejection wouldn't take 4 minutes, so the input tokens were very likely already sent and billed
  before the failure. Checked `~/.claude/debug` and the background job's `timeline.jsonl` for any
  record of the actual cost: neither has one. Checked every `/compact` invocation on the machine,
  not just this one, to see whether the gap is specific to failures: 18 total (16 succeeded, 1
  failed with the 529 above, 1 abandoned mid-compact when its session ended before resolving) — all
  16 successes resolve to an isCompactSummary line with no `usage` field, same as the failure, so
  this is systematic across every compact call rather than a failure-specific gap. The successful
  ones took 125–495 seconds, consistent with cost scaling with context size the same way the
  failure's 4-minute run suggested, but there is still no number to attach to any of them. There is
  currently no way to measure what a compact call, successful or failed, actually costs — not from
  local transcripts, not after the fact. If a `PostCompact` hook or transcript field ever exposes
  it, check it against every window's intercept the way burst-at-open was checked above.

  Fixed the part of this that was independently a bug: `find_window_start`'s roll-forward only
  looked at `usage`-bearing lines, so a `/compact` invocation (which never has one) could be
  invisible to it — the request that opened a window would go unfound, and the fallback estimate
  (`logged + WINDOW`) got permanently persisted as if confirmed, never re-derived even once real
  evidence existed. `scan_compact_attempts()` now feeds the invocation's own timestamp into the
  roll-forward, and an unconfirmed fallback is no longer written to the log — confirmed on the
  window whose boundary prompted this: the SessionStart that computed 06:12:37 had zero evidence
  available yet (correctly `confirmed=False` under the fix), and the very next `/compact`
  invocation two minutes later resolves the roll-forward to 09:12:59, matching what was observed
  directly. This fixes the boundary being *wrong*; it does not make the compact's cost *visible*.

None of these explain the overshoot. The leading remaining explanation: the per-reading `tokens/pct`
ratio *rises through the middle of a window and drops back down near the end* rather than scattering
randomly (window A: 553,618 → 679,648 → 739,844 → 792,002 → 845,982 → 901,671 → 719,610; C is
similarly shaped) — a curve, not noise, which a straight-line fit with a free intercept will absorb
into exactly the kind of offset seen here rather than flag as a bad fit. Untested: whether `pct` is
genuinely non-linear in raw tokens over a window, or this is the same regime-shift effect noted
below, arrived at from the other direction.

### Does cost-weighting fix it?

Refitting on cost-weighted token totals instead of raw ones, same readings:

| window | raw max residual | weighted max residual | raw per-reading CV | weighted CV | raw vs true | weighted vs true |
|---|---:|---:|---:|---:|---:|---:|
| A | 9.0pp | 6.3pp | 14.2% | 8.5% | +13.4% | +4.6% |
| B | 0.9pp | 0.7pp | 26.4% | 14.1% | +50.8% | +27.9% |
| C | 7.7pp | 5.6pp | 14.6% | 8.5% | +31.3% | +19.1% |
| D | 6.6pp | 4.5pp | 33.3% | 17.4% | n/a | n/a |
| E | 3.8pp | 2.8pp | 3.5% | 2.7% | +10.3% | +8.2% |
| F | 1.5pp | 1.1pp | 66.7% | 37.8% | n/a | n/a |

(CV = coefficient of variation, `stdev/mean`, of each window's per-reading `tokens/pct` ratios — how
scattered a single window's own readings are around their own average, independent of any fit. F's
CV is the highest measured by far — only 3 readings, and the first jumps from 6% to 35%, so there's
little in that window to average the noise over, which also makes its very low max residual less
meaningful than the other windows' — three points fit a line almost by construction.)

Weighting tokens by their list-price ratio instead of counting them flat, consistently across all
six windows:

- **Makes it more linear.** The fit's own max residual drops in every window (largest: C's 7.7pp →
  5.6pp), and the per-reading CV drops in every window too, though by less where it was already
  tight to start with (E: 3.5% → 2.7%; D, the noisiest of the group with a real fit: roughly halves
  from 33.3% → 17.4%).
- **Brings it closer to true per_pct.** In all four exhausted windows the overshoot against the
  ground-truth `final total / 100` shrinks (B: +52.1% → +30.0%; A and C similarly; E: +10.3% →
  +8.2%, a smaller absolute move since it started closer to true than any other window).

It doesn't close the gap, though — weighted `per_pct` still overshoots true per_pct by 4.6–28%, worst
in B in both versions. Token-type mix explains a real share of the overshoot, but not all of it —
see the curve-shape note above for the leading remaining explanation.

### How reliably the fit predicts held-out readings

Backtest: fit on just the first *k* readings of a window, measure absolute error against the
readings held out after it, for every *k* from 2 to *n* − 1. **The held-out error does not shrink
monotonically with more points** — window A's error only gets worse as more readings are added
(13.4pp at k=2 growing to 23.8pp at k=6), and D's very first fit (k=2) is off by 144.0pp before
settling down. Windows A and D each contain a burst partway through (large jumps in reported pct
between adjacent readings — A: 52→98, D: 29→47→68) where the rate visibly changes; a line fit on the
calm part of a window is a bad predictor of the bursty part. The thing that breaks the fit looks like
an un-modeled regime shift — local rate tracks token mix, not calendar time — not sample size.

Compares three candidate fits: the raw whole-window least-squares fit above, the same fit on
cost-weighted tokens, and a local-slope model that re-anchors on only the two most recent readings
instead of fitting the whole window. Mean / max absolute error in pp, across every *k*:

| window | current (raw LSQ) | cost-weighted LSQ | local-slope (raw) | local-slope (weighted) |
|---|---:|---:|---:|---:|
| A | 18.2 / 23.8 | 12.9 / 17.2 | 21.9 / 33.2 (1 fit failure) | 16.3 / 27.3 (1 fit failure) |
| B | 5.2 / 5.2 | 4.1 / 4.1 | 5.2 / 5.2 | 4.1 / 4.1 |
| C | 15.1 / 46.4 | 10.8 / 30.0 | 11.0 / 46.4 | 8.2 / 30.0 |
| D | 40.6 / 144.0 | 21.0 / 58.7 | 28.3 / 144.0 | 13.7 / 58.7 |
| E | 15.0 / 29.9 | 10.1 / 19.9 | 13.0 / 29.9 (1 fit failure) | 8.8 / 19.9 (1 fit failure) |
| F | 3.3 / 3.3 | 2.4 / 2.4 | 3.3 / 3.3 | 2.4 / 2.4 |

"Fit failure": window A's readings 5 and 6 report the same pct (52, 52) back to back, so the
two-point local slope is undefined for the split that lands on them — the whole-window fit still
produces an answer where the local-slope model has none. E fails the same way, at the same spot in
its own sequence (readings 5 and 6 both report 79) — two independent occurrences of the same failure
mode. (F has too few readings for this split to arise — its one k=2 backtest is the degenerate case,
same as B, where the local-slope model and the whole-window fit are the same two points.)

Checked against each exhausted window's true per_pct (the weighted candidates against the weighted
version of that same total):

| window | current | cost-weighted LSQ | local-slope (raw) | local-slope (weighted) |
|---|---:|---:|---:|---:|
| A | +15.9% | +8.2% | −24.3% | −14.9% |
| B | +51.1% | +28.8% | +44.9% | +24.9% |
| C | +31.3% | +19.1% | −87.5% | −82.9% |
| E | +10.3% | +8.2% | +65.2% | +49.6% |

**Cost-weighted least squares beats both alternatives on held-out error in every window (A–F) and on
true-value accuracy in every exhausted window (A, B, C, E).** Local-slope is not a consistent
alternative: it beats cost-weighted LSQ's held-out error in some windows (C, D) but loses in others
(A, E) or ties (B, F), and its true-value accuracy is erratic in both direction and magnitude —
undershoots by 24–88% in A and C, overshoots by 25–65% in B and E — worse than even the raw
whole-window fit in most of these, and it can fail to produce a fit at all when two consecutive
readings tie.

`per_pct` (raw fit) ranges 821,796–1,421,011 across the six windows measured — not a fixed constant.
Within a window the raw fit is sometimes tight (B, D: under 2.5pp) and sometimes not (A, C: 7–9pp);
the worst residuals in both A and C land near bursts of fresh, cache-miss-heavy sessions (many
short-lived test sessions in C; a TTL-crossing cache-expiry in A), suggesting the *local* rate shifts
with what kind of tokens are being spent, not just calendar time. Ruled out as the sole cause: model
mix (all six windows are 100% `claude-sonnet-5`) and cache-write share alone (1.1–4.0%, doesn't order
the same way `per_pct` does — C has a lower cache-write share than B but a higher `per_pct`); session
count doesn't order consistently with it either.

**Never drop the intercept** when fitting: forcing the line through the origin pushes pre-window
spend the transcript scan can't see into the slope instead, which is what made an earlier one-shot
ratio disagree with a delta fit by 2x.

**Adopted**: `calibrate()` in `hooks/usage_common.py` fits on tokens weighted by `TOKEN_WEIGHTS`
instead of a flat count. `usage_report.py`'s estimate line, `usage_gate.py`'s gate math, and
`usage_tool_gate.py`'s calls-remaining math (whose carried-context denominator is weighted the same
way, so it isn't divided by a differently-scaled number) all read the one fit through
`window_state()`. Local-slope is not used anywhere.

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
| E | 08-04 10:14 | 104,138,036 | 625 | 13 | 1h47m in (35% of the window) | yes |
| F | 08-04 15:16 | 71,583,169 | 393 | 6 | 4h51m in (95% of the window) | **no** |

`exhausted?` is the user's own account of which windows they ran out of credit in, not something
derived from the scan — it's the ground truth the rest of this section is checked against.

**"Last token used" predicts it correctly across all six windows measured so far.** A, B, C, E all
stopped spending well before their 5-hour mark (35–74%) and then show no further tokens until the
*next* window's first request — the idle-until-renewal shape a hard cap produces — and all four are
confirmed exhausted. D and F's last tokens both land late (95–100% of the window) with only a short
gap before the next window's first request — continuous work still running when the window happened
to roll over — and both are confirmed not exhausted. Directly corroborated for A and C by a
`usage-report` reading next to the stop (A: 98% two minutes before its last token; C: 97% seven
minutes before); B's last reading (60%, 49 minutes before its last token) is looser but agrees in
shape. This is a correlation over six self-reported labels, not a proven mechanism — an idle window
with nobody working would leave the same trace as a capped one — so it's a useful prior, not a
substitute for asking.

**Raw token totals do not order the same way exhaustion does — the first sign the cap isn't a flat
token count.** D spent *more* raw tokens (65.9M) than B did before B hit its cap (61.9M), yet D
didn't exhaust. The four confirmed-exhausted windows (A, B, C, E) give mean 79.8M, range
61.9M–104.1M, and both non-exhausted windows (D: 65.9M, F: 71.6M) sit comfortably inside that range
rather than outside it — the clearest sign yet that raw token count alone can't be what the cap is
measured in.

A cost-weighted total (same guessed list-price ratios as above) narrows this:

| window | weighted total | exhausted? |
|---|---:|---|
| A | 11.40M | yes |
| B | 10.68M | yes |
| C | 12.70M | yes |
| D | 10.07M | **no** |
| E | 14.23M | yes |
| F | 10.87M | **no** |

**Weighting helps, but a single threshold still doesn't separate the two groups.** D (10.07M) sits
below every exhausted window. E, exhausted at 14.23M, is the largest total measured and extends the
exhausted range upward without breaking it. But F (10.87M) lands *between* B (10.68M, exhausted) and
A (11.40M, exhausted) instead of below the whole range: one non-exhausted window (D) sits cleanly
under every exhausted one, the other (F) overlaps them. So cost-weighting narrows the overlap the raw
count left wide open, but these particular weights still don't give a clean cap threshold. Either the
guessed list-price ratios need adjusting, or exhaustion isn't a pure cumulative-spend threshold at
all — burst rate or request cadence could matter alongside total spend — and nothing measured so far
distinguishes those.

Conditions: every transcript on the machine, across all 4 projects — this is an account-wide window,
not a per-repo one. 100% `claude-sonnet-5` in every window, so model mix isn't hiding in this number.
Covers back to the start of `events.jsonl`: its first line is window A's own `renewed` record, so
there's no earlier window this log can reconstruct. The window open at the time of writing (started
08-04 20:24) is excluded from both tables.

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
