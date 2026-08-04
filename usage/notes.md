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

## The PreToolUse budget gate fires ahead of the prompt-level gate — one trial, gap dominated by concurrent sessions

Measured by temporarily overriding `CLAUDE_USAGE_GATE_PCT` to 70.4 (just above the live estimate of
69.7% at the time) and invoking `hooks/usage_tool_gate.py` and `hooks/usage_gate.py` directly as
subprocesses against the real live transcript and event log — not a natural crossing of the real
97% ceiling. One trial, 2026-08-03, several other sessions concurrently active in the same window.

`usage_tool_gate.py` denied first, at the same transcript snapshot where `usage_gate.py` did not yet
(estimate 70.33% < the 70.4% test ceiling), with `calls_remaining` already down to ~1.0 — single-digit,
not tens, matching the plan's success criterion. By the next check moments later the estimate had
jumped to 73.0%, 2.6 points past where the PreToolUse hook had already intervened.

That 2.6-point jump was not from this session's own calls: at ~68,929 tokens/call and 941,707
tokens/%, one session's own calls move the estimate only ~0.07 points each — far too little to
explain it across the handful of tool calls between checks. The `MARGIN_CALLS` comment in
`usage_tool_gate.py` had attributed the slack in `calls_remaining` to *this session's* context
growing between calls; that measurement contradicts it — most of the drift this trial came from
*other* concurrent sessions spending against the same shared window, not from this session's own
growth. `MARGIN_CALLS=5` still caught the crossing with single-digit headroom, so the default
stands from this trial, but the reason to treat `calls_remaining` as an upper bound is concurrent
sessions first, own-context growth second.

## A scripted `claude -p` run is not a stand-in for the interactive floor

Measured 2026-08-04, this repo's directory, default settings, three separate `claude -p "Reply
with exactly: ok" --output-format json` runs: floor (`cache_creation_input_tokens +
cache_read_input_tokens` on the single request) came back 29,213 / 29,205 / 29,206 — tight
variance, but ~7,000 tokens (32%) above the interactive baseline of 21,905–22,188 recorded above.
Print mode sends a different preamble than an interactive session (fewer interactive-only tools,
by the size of it something else added), so **absolute floor numbers from `-p` don't transfer to
interactive figures** — only deltas between two scripted runs are trustworthy, and only against
each other.

## Denying deferred tools trims ~890 tokens, not the 16.7K candidate

Scripted (`-p`, same repo dir), denying the 21 deferred tools listed in a fresh session's
system-reminder (`CronCreate`, `CronDelete`, `CronList`, `DesignSync`, `EndConversation`,
`EnterPlanMode`, `EnterWorktree`, `ExitPlanMode`, `ExitWorktree`, `Monitor`, `NotebookEdit`,
`PushNotification`, `RemoteTrigger`, `SendMessage`, `TaskCreate`, `TaskGet`, `TaskList`,
`TaskOutput`, `TaskStop`, `TaskUpdate`, `WebFetch`, `WebSearch`) via `--settings
'{"permissions":{"deny":[...]}}'`: floor 28,317 / 28,320 (two runs) against the 29,205–29,213
baseline above — a ~890-token drop (~3%), not the 16.7K `/context` attributes to deferred tools.
The deferred-tool mechanism already keeps only a name and one-line description in context and
loads full schemas on demand via `ToolSearch`; denying a tool blocks the call but there is no 16.7K
of schema text left to remove this way. **Candidate closed: not adjustable from `permissions.deny`.**

## The "read six files" round trip does not happen in the installed version

`~/.claude/rules` is a symlink to this repo's `rules/`. Read directly from this session's own
transcript (`866ef482-…jsonl`): the first user message is the task prompt, and the very next
assistant message already carries the full rule text in its cached prefix — no preceding
`tool_use`/`tool_result` pair for a `Read` of any rule file. Rule text arrives inlined as a
system-reminder block on the first request, the same way project `CLAUDE.md` does, not through an
instruction to read six files. On Claude Code 2.1.221 with the symlink in place, that concern is
already moot — there is no round trip left to remove.

## Cache-hit vs. cache-miss is already exposed per request

Every request's `usage` already separates them: `cache_read_input_tokens` is the hit,
`cache_creation_input_tokens` is the miss/write, further split into
`cache_creation.ephemeral_1h_input_tokens` / `ephemeral_5m_input_tokens`. `context-cost.py` and
`usage_common.py` already key off these fields. Nothing further to build here.

## `--safe-mode` floor, and what the customization stack costs on top (scripted only)

Scripted, `--safe-mode` (CLAUDE.md, skills, plugins, hooks, MCP, and the `~/.claude/rules` symlink
all disabled): floor 17,948 — the irreducible base for this version (system prompt + always-loaded
tool schemas + deferred-tool names). Against the 29,205–29,213 full-setup scripted floor, the whole
customization stack costs ≈11,260 scripted tokens. Isolating this repo's own `CLAUDE.md` alone
(scripted, this repo's dir vs. an empty scratch dir, rules/hooks unchanged): 29,205–29,213 vs.
27,984 → ≈1,225 tokens for the project `CLAUDE.md` file (3,135 bytes).

Two attempts to isolate hooks alone did not work and are recorded so they aren't retried the same
way: `--settings '{"hooks":{}}'` left the SessionStart hook firing anyway (confirmed in a `-d api`
debug log — the CLI `--settings` JSON does not override the `hooks` key already in
`~/.claude/settings.json`), and `--setting-sources project,local` produced a result polluted by a
partial cross-session cache hit (15,912 of its 30,750 total came from `cache_read`, matching another
run's cached prefix, not a clean miss). Neither isolates hooks' own contribution; a clean figure for
that, and a true interactive (non-scripted) per-configuration sweep to match the 21,905–22,188
baseline, are still open.
