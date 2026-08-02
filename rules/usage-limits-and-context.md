# Predict the usage window; keep context small

_Several agents share one account. Pool what each learns about the credit window in a shared log, and treat context size as spend._

Credit renews on a rolling window — reported as **5 hours**, starting from the first request sent
after the previous window ended, not from midnight and not per session. Agents run concurrently
against one account, so the window one agent starts is the window all of them are living in, and
no agent can see the whole picture alone. Hence a shared file.

Every number here is provisional and refined by observation, not assumed
(`measure-before-recording.md`). An agent that learns something the log does not say is expected
to write it down.

## The shared log

Both files live in the **rules repository** — its absolute path is in the SessionStart context that
loaded these rules; read that path, never hard-code one (`rules-repo-workflow.md`). Keeping them in
a repo means every change shows up in `git status` and `git log` like any other work.

- `<rules-repo>/usage/events.jsonl` — raw observations. **Gitignored**: machine-local, noisy, and
  appended by concurrent agents.
- `<rules-repo>/usage/notes.md` — what those observations taught you. **Committed**, so a
  conclusion outlives the machine that measured it.

The log is append-only, one JSON object per line, newest last. Create the directory if missing.
**Append; never rewrite.** Concurrent appends of a single short line survive each other; a
read-modify-write loses whatever another agent wrote in between.

```bash
printf '%s\n' '{"t":"2026-07-31T15:04:05Z","kind":"limit-hit","resetAt":"2026-07-31T15:55:00Z"}' \
  >> <rules-repo>/usage/events.jsonl
```

Kinds worth logging, all with a `t` timestamp in UTC:

| kind | fields | when |
|---|---|---|
| `first-request` | — | your first server call of a session, when the log shows no open window |
| `limit-hit` | `resetAt` when the error states one | the moment a request is refused for credit |
| `sleep` | `untilT`, `reason` | before you sleep, so another agent does not duplicate the wait |
| `renewed` | — | a request succeeds after a `limit-hit` |
| `context` | `pct`, `tokens`, `limit` | whenever a `/context` reading is in front of you |
| `usage-report` | `pct`, `renewsInMin`, plus what was running | the user tells you how much credit is spent and when it renews |

## Before a long unattended run, read the log

Reduce it newest-first:

- A `limit-hit` whose `resetAt` is still in the future means credit is out **now**. Sleep until
  then rather than discovering it again — another agent already paid for that information.
- Otherwise a `usage-report` newer than the last `renewed` wins: it states the renewal directly,
  so use it instead of reconstructing one.
- Otherwise take the earliest `first-request` after the last `renewed`. That is the window start;
  the predicted renewal is one window length later.
- A `sleep` event covering the same period means someone is already waiting. Waking a few seconds
  apart is fine and expected; add a small random offset (tens of seconds) so several agents do not
  all fire at the same instant and race for the first request.

Sleep with a background `sleep` command, not a scheduled cloud agent.

## A declared sleep is binding

Once you have said you are sleeping until a time, **do no work until that time** — no tool calls,
no commits, no "one quick local edit". Local edits are not free: every tool call is a separate
round trip that re-sends the whole conversation, so a handful of "cheap" calls during a dead
window costs more than the reply that announced the sleep.

If the user prompts you mid-sleep, the model has already been invoked and that request is spent —
you cannot refuse it back. What you can still control is everything after it: **answer in one
turn, with zero tool calls**, restate when you will resume, and stop. Do not treat a question as
permission to resume, and do not start the queued work because you happen to be awake. Only an
explicit instruction to continue ends the sleep early.

The same applies to a request that looks trivial. "Just add one line to a file" is a tool call, a
commit is two or three more, and the point of the sleep was that none of them can be afforded.

## Sleeping without spending a request at all

An agent cannot decide to sleep for free. Rules and project files are injected into context by
the harness, but acting on them requires the model to run, which is the request you were trying
to avoid — so a freshly started agent always costs at least one round trip before it can conclude
that credit is out.

Only code that runs **outside** the model can prevent that, which is what the rules repo's
`SessionStart` usage hook is for: it reads the shared log before any request is sent, and when the
newest `limit-hit` carries a `resetAt` still in the future it says so at the top of your context.
Seeing that, do not start the work — answer in one turn and stop. If the block is absent, the hook
is not installed on this machine (`install-usage-hook.sh`), and nothing is watching the window for
you.

## Refine the estimate from a reported reading

**An agent cannot read the account's remaining credit** — there is no tool for it. A user saying
"X% used, renews in Y minutes" is therefore the only direct reading available, and it beats every
inference drawn from the window start. Log it as `usage-report` and get four things out of it:

- **Renewal becomes known rather than derived.** `t + Y minutes` is the window end. Anything the
  window-start reconstruction says is a fallback for when no report exists.
- **Window length falls out of the pair.** Reported end minus observed start. When that disagrees
  with what the notes assume, the notes are what is wrong — correct them.
- **Two reports give a burn rate.** Δpct over the minutes between them, extrapolated to 100%, is a
  projected exhaustion time. Compare it with the renewal time: if exhaustion lands first, the
  remaining work has to be paced, narrowed, or slept through — decide then, not at the refusal.
- **Divided by what happened, it gives a cost.** Δpct over the turns between two reports is a cost
  per turn, and `(100 − pct)` over that is roughly how many turns remain. This only transfers to a
  later situation if you record the conditions with it (`measure-before-recording.md`): how many
  agents were running, how big the contexts were, whether the traffic was long tool outputs or
  short replies. A rate measured with one agent on a small context does not describe four agents
  near a context limit.

Two supporting habits make those numbers sharper:

- **Log `context` readings next to reports.** Cost per turn scales with context size, so a rate
  is only interpretable joined to one. This is the same reason context management belongs to this
  rule and not a separate one.
- **A `limit-hit` pins the ceiling.** Record the last reported pct alongside it. Whether refusal
  arrives at a reported 100% or noticeably earlier is a fact only a hit can establish.

**Ask for a reading when one would change what you do** — before a long unattended run, before
deciding to sleep, before starting something that cannot be resumed halfway. It costs the user one
line and is cheaper than being wrong about the window. Do not ask on a cadence; a reading you
would not act on is spend.

## The transcripts are a local spend proxy

Every session writes a JSONL transcript under the projects directory of the Claude config dir
(`$CLAUDE_CONFIG_DIR`, else `~/.claude`), and each assistant message in it carries a
`message.usage` object — input, output, and cache read/creation token counts — with a timestamp
and model. Summed across **all** transcripts modified since the window start, that is total
traffic for every agent on this machine: the closest thing to measured spend available locally,
and it costs no request to compute.

Tokens are not percent, and a `usage-report` is what converts them. Tokens accumulated since the
window start, divided by the reported pct, gives tokens-per-percent; from then on the running sum
predicts exhaustion by itself until a later report corrects the ratio. Track the components
separately rather than summing them raw — cache reads, fresh input, and output are not priced
alike, so a ratio fitted to one traffic mix will mispredict another.

Code outside the model does the scanning: a `SessionStart` hook in the rules repo already reports
the window state, the tokens spent in it, and a calibrated percentage when a report exists. Read
that block instead of recomputing it — a scan the model performs costs the request it was trying
to save.

Keep the running conclusions in `<rules-repo>/usage/notes.md` — window length when it disagrees
with the assumption, how early limits arrive under N concurrent agents, measured cost per turn and
the conditions it was measured under, anything about renewal that surprised you. Refine what is
there rather than appending a second opinion beside it, and commit it (`rules-repo-workflow.md`).

## Context size is spend

Every request re-sends the whole conversation, so a large context costs credit on **each** turn,
not once. Managing context is therefore part of managing the window, which is why both live here.

- Recommend `/compact` when the work must continue in this session and context is past roughly
  **70%**. Say so plainly rather than waiting to be asked.
- Recommend `/clear` instead — it frees more — when the next task does not depend on this
  conversation. **Before recommending it, make the record durable**: the plan or task file
  reflects the remaining work, anything learned about the repo's own tooling is written into the
  repo rather than held in the conversation, and the backlog is current. Then say what the next
  session should pick up.
- A conversation whose findings are all written down is cheap to clear and expensive to keep.
  Prefer writing them down early, not at the point where context forces it.
