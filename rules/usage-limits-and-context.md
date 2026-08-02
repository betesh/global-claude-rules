# Usage window and context size

_Several agents share one account, on a rolling 5-hour window. Hooks watch it; you log what only
you can see, and treat context as spend._

## The hooks watch the window, not you

`install-usage-hook.sh` installs both halves, and neither costs a request:

- **SessionStart** prints where the window stands at the top of your context.
- **UserPromptSubmit** refuses the prompt outright when the window is spent, so nothing is sent.

If no window block appears at session start, they are not installed here and nothing is watching.
Do not reimplement them by hand: scanning transcripts yourself costs the request you were saving.

## Log only what the transcripts cannot show

The log is `<rules-repo>/usage/events.jsonl` (gitignored); conclusions go in `usage/notes.md`
(committed). Append one JSON line, never rewrite — concurrent agents share it. Tag every line with
the `session` id the SessionStart block reports.

| kind | fields | when |
|---|---|---|
| `usage-report` | `pct`, `renewsInMin`, `agents` | the user states how much is spent and when it renews |
| `limit-hit` | `resetAt`, `pctAtHit` | a request is actually refused |
| `sleep` | `untilT`, `reason` | before you wait, so another agent does not duplicate it |

Nothing else. Token counts, request counts, when the window opened, which sessions ran — all of it
is in the transcripts already and can be reconstructed for any past moment, so a reported
percentage needs no token count taken beside it.

**Ask for a reading when it would change what you do** — before a long unattended run, or anything
that cannot resume halfway. An agent cannot read remaining credit; a user reporting it is the only
direct measurement, and it is what calibrates every estimate. Do not ask on a cadence.

## A declared sleep is binding

Once you say you are waiting until a time, do no work until then — no tool calls, no commits, no
"one quick edit". Each is a round trip that re-sends the whole conversation.

If the user prompts you mid-wait, that request is already spent: answer in one turn with **zero
tool calls**, restate when you resume, stop. A question is not permission to resume. Two things do
end a wait early: an instruction to continue, and evidence credit returned — a reported percentage
under 100, or a request that plainly succeeded. Waiting out an open window is invisible waste.

## Context size is spend

Every request re-sends the whole context, so its size is charged on **every** turn.

Measured: **~79% of all spend is the fixed prefix** — system prompt, tool definitions, and whatever
session start injects — re-read on every request. Only ~21% is the conversation. Two consequences:

- **`/clear` can save at most about a fifth.** It drops the conversation, not the prefix. Recommend
  it when the next task does not depend on this one — but first make the record durable: the plan
  file reflects what is left, and anything learned about the repo is written into the repo.
  Recommend `/compact` instead when the work must continue here and context is past roughly 70%.
- **Trimming large tool outputs is not worth doing.** Measured at under 0.1% of a window. Do not
  contort a command to shrink its output.

Adding to these rules is not free: they are re-read on every request of every session, so a
thousand tokens here costs roughly 0.4 points of a window, more when more agents run.
