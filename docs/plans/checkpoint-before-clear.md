# Make the clear-nudge verify safety and fire on more than a plan write

`hooks/plan-written.py` only fires `PostToolUse` on `Write` to `docs/plans/*`, and even then it
only asks the agent to record things and tells the user to `/clear` in the same breath — it never
checks that the recording actually happened before endorsing the clear. Two problems follow: a
session that grows large without ever writing a plan file gets no nudge at all, and a session that
*does* write one can still be told to `/clear` while work sits uncommitted, because nothing
re-checks state after the instruction is issued.

The trigger and the safety check are separable, and should be separated. Firing is about context
size: per `usage/notes.md`, cache-read is ~98% of a window and total ≈ requests × context, so once
context is large, re-establishing the ~22.1K floor a fresh session pays (measured in
`docs/plans/per-request-cost.md`) is cheap next to what one more tool call in *this* session now
costs. Safety is about state: nothing durable is still only in this conversation.

## Phase 1 — ground the trigger in context size, not a specific tool

- [ ] Confirm what a `Stop` hook can see and do: whether it can read the current context size the
      way `session_carry()` in `hooks/usage_common.py` already does, and whether it can block the
      turn from ending — inject `additionalContext` and force another turn — the way `PreToolUse`
      can deny a call.
      - This decides whether `Stop` replaces `PostToolUse`-on-`Write` as the trigger event, or has
        to sit alongside it.
- [ ] Pick the size threshold from observed firing frequency, not from the ratio alone. A threshold
      derived only by reasoning ("context is clearly bigger than the floor") is a guess
      (`rules/measure-before-recording.md`) and would be true almost immediately, nagging on nearly
      every turn. Run a candidate for a session or two and record in `usage/notes.md` how often it
      fired against how often the context had actually grown enough to matter.

## Phase 2 — don't endorse `/clear` until the state is actually durable

- [ ] Replace the single instruction-then-endorse message with a check the hook runs itself:
      `git status --porcelain` in every repo touched this session. While it's dirty, the message
      asks the agent to commit — nothing about `/clear` yet.
      - This mirrors what `rules/auto-commit.md` already asks of every turn; the difference is this
        hook verifies it mechanically instead of trusting the agent read the rule.
- [ ] For what can't be checked mechanically — a plan file trimmed to remaining work, anything
      memory-worthy saved — keep asking the agent to do it, but only surface the "tell the user
      it's safe to `/clear`" text once a *later* firing finds git clean. One firing asks for the
      recording; a later one confirms it landed. Never both claims at once.

## Success criteria

- The nudge fires on a session that never wrote a plan file, once its context crosses the measured
  threshold.
- No firing ever tells the user it's safe to `/clear` while `git status --porcelain` is non-empty
  in a repo the session touched.

## Out of scope

- The carried-context gate (`docs/plans/carried-context-gate.md`) — that fires on window
  boundaries specifically, because history there was paid for at cache-write prices that a new
  window's requests would re-read. This plan's trigger is context size at any moment, independent
  of window timing.
- Verifying plan-file accuracy or memory-worthiness. Neither is mechanically checkable; the hook
  can only keep asking, not confirm.
