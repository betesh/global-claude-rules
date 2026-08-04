# Usage window and context size

_Several agents share one account, on a rolling 5-hour window. Hooks watch it; treat context as
spend._

## The hooks watch the window, not you

`install-hooks.sh` installs both halves, and neither costs a request:

- **SessionStart** prints where the window stands at the top of your context.
- **UserPromptSubmit** refuses the prompt outright, so nothing is sent, when the window is spent or
  this session is carrying a large history into a window it did not open. Re-sending it accepts.

If no window block appears at session start, they are not installed here and nothing is watching.
Do not reimplement them by hand: scanning transcripts yourself costs the request you were saving.

## Log only what the transcripts cannot show

The log is `<rules-repo>/usage/events.jsonl` (gitignored); conclusions go in `usage/notes.md`
(committed). Append one JSON line, never rewrite — concurrent agents share it. Tag every line with
`t` (local time, with a numeric UTC offset — the log is gitignored, so it never leaves the machine
it was written on), then `kind`, then the `session` id the SessionStart block reports, then
whatever else that kind carries — that order is what makes rows comparable at a glance.

| kind | fields | written by | when |
|---|---|---|---|
| `usage-report` | `pct`, `renewsInMin` | the user, via `python3 usage/log-pct.py PCT [RENEWS_IN_MIN]` | a fresh reading exists — no agent or request needed |
| `renewed` | `startedT` | the hook, automatically | the first session to notice the current boundary isn't logged yet |
| `cache-expired` | `claude_pid` | the hook, automatically | a session idle past the prompt-cache TTL resumes holding enough context to be worth clearing |
| `checkpoint-nudged` | `context`, `claude_pid` | the hook, automatically | a continuously-active session (no idle gap) crosses the same context threshold |
| `cleared` | `context`, `claude_pid`, `nudge_kind`, `nudge_age_min` | the hook, automatically | a session's `SessionStart` fires with source `clear` — links the `/clear` back to whichever nudge preceded it (by `claude_pid`, not `session_id` — `/clear` issues a fresh one), if any |

Never write `usage-report`, `renewed`, `cache-expired`, `checkpoint-nudged`, or `cleared` yourself —
all five exist to be read, not appended by you. Token counts, request counts, when the window opened, which
sessions ran — all
of it is in the transcripts already and can be reconstructed for any past moment, so a reported
percentage needs no token count taken beside it.

**Ask for a reading when it would change what you do** — before a long unattended run, or anything
that cannot resume halfway. An agent cannot read remaining credit; a user reporting it is the only
direct measurement, and it is what calibrates every estimate. Point them at `usage/log-pct.py`
rather than logging what they tell you yourself — it needs no agent request and guarantees the
right format. Do not ask on a cadence.

## A declared sleep is binding

Once you say you are waiting until a time, do no work until then — no tool calls, no commits, no
"one quick edit". Each is a round trip that re-sends the whole conversation.

Sleep in the foreground (a plain blocking `sleep`), never `run_in_background`. Observed here: a
backgrounded wait's completion did not resume an idle session by itself — every agent needed an
explicit "continue" despite the wait finishing on schedule, because the harness only surfaces a
background task's notification on the next externally-driven turn. A foreground `sleep` blocks the
same turn and hands control straight back when it returns, so the wait actually resolves unattended.
When one wait outlasts a single blocking call, chain foreground `sleep` calls back to back rather
than backgrounding — this is the wait itself, not a polling loop working around a limit, since each
call still blocks until its own end and the session is never idle in between.

If the user prompts you mid-wait, that request is already spent: answer in one turn with **zero
tool calls**, restate when you resume, stop. A question is not permission to resume. Two things do
end a wait early: an instruction to continue, and evidence credit returned — a reported percentage
under 100, or a request that plainly succeeded. Waiting out an open window is invisible waste.

## Context size is spend

Every request re-sends the whole context, so its size is charged on **every** turn.

Measured: **the biggest single cost is context a long-lived session carries across a window
boundary** — 59% of all spend in one window, because everything already in context is re-read by
every request that follows. Two consequences:

- **Recommend `/clear` when the next task does not depend on this conversation**, and say so
  plainly rather than waiting to be asked — most of all when a session has been running a long
  time. First make the record durable: the plan file reflects what is left, and anything learned
  about the repo is written into the repo. Recommend `/compact` instead when the work must
  continue here and context is past roughly 70%.
- **Trimming large tool outputs is not worth doing.** Measured at under 0.1% of a window. Do not
  contort a command to shrink its output.

Adding to these rules is not free: they are re-read on every request of every session, so a
thousand tokens here costs roughly 0.4 points of a window, more when more agents run.
