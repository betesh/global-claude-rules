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

`~/.claude/usage/events.jsonl` — append-only, one JSON object per line, newest last. Create the
directory if missing. **Append; never rewrite.** Concurrent appends of a single short line survive
each other; a read-modify-write loses whatever another agent wrote in between.

```bash
printf '%s\n' '{"t":"2026-07-31T15:04:05Z","kind":"limit-hit","resetAt":"2026-07-31T15:55:00Z"}' \
  >> ~/.claude/usage/events.jsonl
```

Kinds worth logging, all with a `t` timestamp in UTC:

| kind | fields | when |
|---|---|---|
| `first-request` | — | your first server call of a session, when the log shows no open window |
| `limit-hit` | `resetAt` when the error states one | the moment a request is refused for credit |
| `sleep` | `untilT`, `reason` | before you sleep, so another agent does not duplicate the wait |
| `renewed` | — | a request succeeds after a `limit-hit` |
| `context` | `pct`, `tokens`, `limit` | whenever a `/context` reading is in front of you |

## Before a long unattended run, read the log

Reduce it newest-first:

- A `limit-hit` whose `resetAt` is still in the future means credit is out **now**. Sleep until
  then rather than discovering it again — another agent already paid for that information.
- Otherwise take the earliest `first-request` after the last `renewed`. That is the window start;
  the predicted renewal is one window length later.
- A `sleep` event covering the same period means someone is already waiting. Waking a few seconds
  apart is fine and expected; add a small random offset (tens of seconds) so several agents do not
  all fire at the same instant and race for the first request.

Sleep with a background `sleep` command, not a scheduled cloud agent.

## What is not measurable, and what to record instead

**An agent cannot read the account's remaining credit.** There is no tool for it, so a "95% spent,
sleep now" trigger cannot be computed directly today, and inventing one produces false precision.
What can be accumulated is empirical: how long a window actually lasted, how many agents were
running, and roughly how much traffic they moved. Log `limit-hit` faithfully and the picture
sharpens on its own.

Keep the running conclusions in `~/.claude/usage/notes.md` — window length when it disagrees with
the assumption, how early limits arrive under N concurrent agents, anything about renewal that
surprised you. Refine what is there rather than appending a second opinion beside it.

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
