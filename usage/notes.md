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

## Tokens-per-percent varies window to window; cause not yet identified

`pct = intercept + tokens/per_pct`, fit by `calibrate()` in `hooks/usage_common.py`. Four windows
measured so far:

| window | readings | per_pct | intercept | max residual | cache-write share |
|---|---:|---:|---:|---:|---:|
| A (08-03 14:11) | 7 | 821,796 | 4.0 | 9.0pp | 1.9% |
| B (08-03 19:12) | 3 | 941,707 | 14.8 | 0.9pp | 2.4% |
| C (08-04 00:13) | 9 | 1,080,381 | 21.4 | 7.7pp | 2.2% |
| D (08-04 05:14) | 6 | 752,323 | 12.5 | 2.5pp | 4.0% |

**`per_pct` swings ~40% across these four windows — not a fixed constant.** Within a window the fit
is sometimes tight (B, D: under 2.5pp) and sometimes not (A, C: 7–9pp); the worst residuals in both
A and C land near bursts of fresh, cache-miss-heavy sessions (many short-lived test sessions in C;
a TTL-crossing cache-expiry in A), suggesting the *local* rate shifts with what kind of tokens are
being spent, not just calendar time. Tested and ruled out as the sole explanation: model mix (all
four windows are 100% `claude-sonnet-5`) and cache-write share alone (1.9–4.1%, doesn't order the
same way `per_pct` does — C has a lower cache-write share than B but a higher `per_pct`). Session
count also doesn't order consistently with `per_pct`. **No pattern identified yet** — keep reporting
% readings until one window's internal rate can be checked against another's directly (e.g. by
comparing `per_pct` fit over just the bursty sub-interval against the window's overall fit).

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

`CARRY_AT` in `hooks/usage_common.py` and `CHECKPOINT_AT` in `hooks/checkpoint_stop.py` are both
still guesses. Two genuine TTL crossings carried 231,467 and 71,903 tokens respectively — both
comfortably above `CARRY_AT`'s 50,000 default, so it isn't contradicted, but two points can't locate
the real knee below which clearing saves less than the interruption costs.

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
| `rules/` | ~3,000 | see "Shrinking `rules/`" in the plan's Out of scope |
| hooks (`SessionStart`'s own report) | ~541 | `~/.claude/settings.json` `hooks` key removed for two scripted runs, restored after |
| skills/agent discovery (residual) | ~6,459 | customization stack (10,071) minus rules minus hooks |

**Interactive costs ~6,450–6,470 tokens more than scripted (`-p`) for the same configuration** —
confirmed three ways (full repo, empty dir, `--safe-mode`), consistent to within 36 tokens each
time; cause not identified, only that it's independent of CLAUDE.md/rules/hooks/skills.

Denying the deferred tools (`ToolSearch`-gated ones) via `permissions.deny` only trims ~890 tokens
scripted, not the 16.7K `/context` attributes to them — the mechanism already keeps just a name and
one-line description in context regardless of deny state. Not adjustable this way.
