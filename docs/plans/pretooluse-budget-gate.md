# Gate on tool calls, not prompts, using a token budget instead of a rate

The existing `UserPromptSubmit` gate (`hooks/usage_gate.py`) only checks the estimate once per
prompt. A single prompt can dispatch many tool calls — each one its own request, resending the full
context (`usage/notes.md`: cache-read is ~98% of a window) — so a command that starts safely below
`GATE_AT_PCT` can cross it mid-flight, and the next check only comes after it already has.

`PreToolUse` fires before every individual tool call and can deny it with a reason, which closes
that gap. The budget for it doesn't need a token-rate forecast: `remaining = (GATE_AT_PCT -
estimate) × per_pct` is already computable from the existing calibration, and dividing by the
current context size (last request's `input + cache_write + cache_read`, the same figure
`session_carry()` in `hooks/usage_common.py` already reads) gives calls-remaining directly — no
need to guess how fast the session is moving.

## Phase 3 — measure the margin

- [ ] Because context grows every call, calls-remaining computed against the *current* context size
      is an upper bound, not exact. Run the hook live across a window and record in
      `usage/notes.md` how far its denial actually lands from the point `usage_gate.py` would have
      refused anyway — that gap is the margin to set, not a guessed constant.

## Success criteria

- A command that would have been refused mid-flight by `usage_gate.py` is instead stopped by this
  hook first, at least once, observed live.
- The measured margin (Phase 3) leaves single-digit calls of headroom, not tens — a hook that fires
  as soon as the estimate has any headroom left at all is denying calls the budget could have
  afforded.

## Out of scope

- Rate- or time-based forecasting ("cross 97% in N minutes") — rejected: the number of sessions
  sharing the window varies unpredictably, so a time estimate would be wrong by an unmeasured
  factor. Token budget against calls-remaining needs no rate at all.
- Having the hook itself sleep. Hooks are synchronous one-shot processes; blocking one for up to
  hours has no visibility and can't be interrupted. The agent's own foreground sleep already does
  this correctly once told to.
